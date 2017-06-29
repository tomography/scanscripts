# -*- coding: utf-8 -*-

"""Defines TXM classes for controlling the Transmission X-ray
Microscope at Advanced Photon Source beamline 32-ID-C.

TxmPV
  A decorator for the process variables used by the microscopes.
TXM
  A nano-CT transmission X-ray microscope.
MicroCT
  Similar to the nano-CT but for micro-CT.

"""

import time
import math
import logging
import warnings
from contextlib import contextmanager

from epics import PV as EpicsPV, get_pv

import exceptions_

DEFAULT_TIMEOUT = 20 # PV timeout in seconds

log = logging.getLogger(__name__)

class TxmPV(object):
    """A descriptor representing a process variable in the EPICS system.
    
    This allows accessing process variables as if they were object
    attributes. If the descriptor owner (ie. TXM) is not attached,
    this descriptor performs like a regular attribute. Optionally,
    this can also be done for objects that have no shutter permit.
    
    Attributes
    ----------
    put_complete : bool
      If False, there is a pending put operation.
    
    Parameters
    ----------
    pv_name : str
      The name of the process variable to connect to as defined in the
      EPICS system.
    dtype : optional
      If given, the values returned by `PV.get` will be
      typecast. Example: ``dtype=int`` will return
      ``int(PV[pv].get())``.
    default : optional
      If the owner is not attached, this value is returned instead of
      polling the instrument..
    permit_required : bool, optional
      If truthy, data will only be sent if the owner `has_permit`
      attribute is true. Reading of process variable is still enabled
      either way.
    wait : bool, optional
      If truthy, setting this descriptor will block until the
      operation succeeds.
    
    """
    _epicsPV = None
    put_complete = True
    
    class PVPromise():
        is_complete = False
        result = None
    
    def __init__(self, pv_name, dtype=None, default=None,
                 permit_required=False, wait=True, get_kwargs={}):
        # Make sure the dtype and float are compatible
        if dtype is not None:
            dtype(default)
        # Set default values
        self._namestring = pv_name
        self.curr_value = default
        self.dtype = dtype
        self.permit_required = permit_required
        self.wait = wait
        self.get_kwargs = get_kwargs
    
    def get_epics_PV(self, txm):
        # Only create a PV if one doesn't exist or the IOC prefix has changed
        is_cached = (self._epicsPV is not None and
                     self.ioc_prefix == txm.ioc_prefix)
        if not is_cached:
            self.ioc_prefix = txm.ioc_prefix
            pv_name = self.pv_name(txm)
            self._epicsPV = EpicsPV(pv_name)
        return self._epicsPV
    
    def pv_name(self, txm):
        """Do string formatting on the pv_name and return the result."""
        return self._namestring.format(ioc_prefix=txm.ioc_prefix)
    
    def __get__(self, txm, type=None):
        # Ask the PV for an updated value if possible
        if txm.is_attached:
            pv = self.get_epics_PV(txm)
            self.curr_value = pv.get(**self.get_kwargs)
        # Return the most recently retrieved value
        if self.dtype is not None:
            self.curr_value = self.dtype(self.curr_value)
        return self.curr_value
    
    def complete_put(self, promise, pvname):
        log.debug("Completed put for %s", self)
        promise.is_complete = True
        # txm = data
        # log.debug("Completed put on %s", pvname)
        # if txm.is_attached:
        #     is_not_done = True
        # else:
        #     is_not_done = False
        # while is_not_done and self.wait:
        #     time.sleep(0.01) # Give the PV a chance to settle
        #     curr_val = self.get_epics_PV(txm).get()
        #     is_not_done = (curr_val != self.curr_value)
        # self.put_complete = True
    
    def __set__(self, txm, val):
        log.debug("Setting PV value %s: %s", self, val)
        self.txm = txm
        # Check that the TXM has shutter permit if required for this PV
        if txm.is_attached and self.permit_required and not txm.has_permit:
            # There's a valid TXM but we can't operate this PV
            permit_clear = False
            msg = "PV {pv} was not set because TXM doesn't have permission."
            msg = msg.format(pv=self.pv_name)
            warnings.warn(msg)
        else:
            permit_clear = True
            self.curr_value = val
        # Set the PV (only if the TXM is attached and has permit)
        if txm.is_attached and permit_clear:
            pv = self.get_epics_PV(txm)
            # How should be handle waiting?
            in_context = txm.pv_queue is not None
            if not in_context:
                # Blocking version
                pv.put(val, wait=self.wait)
            else:
                # Non-blocking version
                promise = self.PVPromise()
                txm.pv_queue.append(promise)
                pv.put(val, callback=self.complete_put, callback_data=promise)
        elif not txm.is_attached:
            # Simulate a completed put call, because the callback isn't run
            self.curr_value = val
    
    def __set_name__(self, txm, name):
        self.name = name
    
    def __str__(self):
        return getattr(self, 'name', self._namestring)
    
    def __repr__(self):
        return "<TxmPV: {}>".format(self._namestring)


def permit_required(real_func):
    """Decorates a method so it can only open with a permit.
    
    This method decorator ensures that the decorated method can only
    be called on an object that has a shutter permit. If it doesn't,
    then nothing happens.
    
    Parameters
    ----------
    return_value : optional
      Will be returned if the method is mocked.
    
    """
    def wrapped_func(obj, *args, **kwargs):
        # Inner function that checks the status of permit
        if obj.has_permit:
            ret = real_func(obj, *args, **kwargs)
        else:
            msg = "Shutter permit not granted."
            raise exceptions_.PermitError(msg)
        return ret
    return wrapped_func


class txm_required():
    """Decorates a method so it can only open with an instrument attached.
    
    This method decorator ensures that the decorated method can only
    be called on an object that has a real-world TXM instrument
    attached. If it doesn't, then nothing happens.
    
    Parameters
    ----------
    return_value
      Will be returned if the method is mocked.
    
    """
    def __init__(self, return_value):
        self.return_value = return_value
    
    def __call__(self, real_func):
        def wrapped_func(obj, *args, **kwargs):
            # Inner function that checks the status of permit
            if obj.is_attached:
                ret = real_func(obj, *args, **kwargs)
            else:
                ret = self.return_value
            return ret
        return wrapped_func


############################
# Main TXM Class definition
############################
class TXM(object):
    """A class representing the Transmission X-ray Microscope at sector 32-ID-C.
    
    Attributes
    ----------
    is_attached : bool
      Is this computer able to communicate with the instrument. If
      False, communication methods will be simulated.
    has_permit : bool
      Is the instrument authorized to open shutters and change the
      X-ray source. Could be false for any number of reasons, most
      likely the beamline is set for hutch B to operate.
    ioc_prefix : str, optional
      The prefix to use for the camera's I/O controller when conneting
      certain PV's. PV descriptor's can then use "{ioc_prefix}" in
      their PV nam and have it format automatically.
    use_shutter_A : bool, optional
      Whether shutter A should be used when getting light.
    use_shutter_B : bool, optional
      Whether shutter B should be used when getting light.
    zp_diameter : float, optional
      The diameter (in nanometers) of the zone-plate currently
      installed in the instrument.
    drn : float, optional
      The width of the zoneplate's outermost diffraction zone.
    
    """
    pv_queue = []
    hdf_writer_ready = False
    tiff_writer_ready = False
    pg_external_trigger = True
    shutters_are_open = False
    E_RANGE = (6.4, 30) # How far can the X-ray energy be changed (in keV)
    POLL_INTERVAL = 0.01 # How often to check PV's in seconds.
    # Commonly used flags for PVs
    SHUTTER_OPEN = 0
    SHUTTER_CLOSED = 1
    RECURSIVE_FILTER_TYPE = "RecursiveAve"
    CAPTURE_ENABLED = 1
    CAPTURE_DISABLED = 0
    FRAME_DATA = 0
    FRAME_WHITE = 1
    FRAME_DARK = 2
    DETECTOR_IDLE = 0
    DETECTOR_ACQUIRE = 1
    
    # Process variables
    # -----------------
    #
    # Detector PV's
    Cam1_ImageMode = TxmPV('{ioc_prefix}cam1:ImageMode')
    Cam1_ArrayCallbacks = TxmPV('{ioc_prefix}cam1:ArrayCallbacks')
    Cam1_AcquirePeriod = TxmPV('{ioc_prefix}cam1:AcquirePeriod')
    Cam1_FrameRate_on_off = TxmPV('{ioc_prefix}cam1:FrameRateOnOff')
    Cam1_FrameRate_val = TxmPV('{ioc_prefix}cam1:FrameRateValAbs')
    Cam1_TriggerMode = TxmPV('{ioc_prefix}cam1:TriggerMode')
    Cam1_SoftwareTrigger = TxmPV('{ioc_prefix}cam1:SoftwareTrigger')
    Cam1_AcquireTime = TxmPV('{ioc_prefix}cam1:AcquireTime')
    Cam1_FrameRateOnOff = TxmPV('{ioc_prefix}cam1:FrameRateOnOff')
    Cam1_FrameType = TxmPV('{ioc_prefix}cam1:FrameType')
    Cam1_NumImages = TxmPV('{ioc_prefix}cam1:NumImages')
    Cam1_Acquire = TxmPV('{ioc_prefix}cam1:Acquire')
    Cam1_Display = TxmPV('{ioc_prefix}image1:EnableCallbacks')
    
    # HDF5 writer PV's
    HDF1_AutoSave = TxmPV('{ioc_prefix}HDF1:AutoSave')
    HDF1_DeleteDriverFile = TxmPV('{ioc_prefix}HDF1:DeleteDriverFile')
    HDF1_EnableCallbacks = TxmPV('{ioc_prefix}HDF1:EnableCallbacks')
    HDF1_BlockingCallbacks = TxmPV('{ioc_prefix}HDF1:BlockingCallbacks')
    HDF1_FileWriteMode = TxmPV('{ioc_prefix}HDF1:FileWriteMode')
    HDF1_NumCapture = TxmPV('{ioc_prefix}HDF1:NumCapture')
    HDF1_Capture = TxmPV('{ioc_prefix}HDF1:Capture')
    HDF1_Capture_RBV = TxmPV('{ioc_prefix}HDF1:Capture_RBV')
    HDF1_FileName = TxmPV('{ioc_prefix}HDF1:FileName')
    HDF1_FullFileName_RBV = TxmPV('{ioc_prefix}HDF1:FullFileName_RBV',
                               dtype=str, default='')
    HDF1_FileTemplate = TxmPV('{ioc_prefix}HDF1:FileTemplate')
    HDF1_ArrayPort = TxmPV('{ioc_prefix}HDF1:NDArrayPort')
    HDF1_NextFile = TxmPV('{ioc_prefix}HDF1:FileNumber')
    
    # Tiff writer PV's
    TIFF1_AutoSave = TxmPV('{ioc_prefix}TIFF1:AutoSave')
    TIFF1_DeleteDriverFile = TxmPV('{ioc_prefix}TIFF1:DeleteDriverFile')
    TIFF1_EnableCallbacks = TxmPV('{ioc_prefix}TIFF1:EnableCallbacks')
    TIFF1_BlockingCallbacks = TxmPV('{ioc_prefix}TIFF1:BlockingCallbacks')
    TIFF1_FileWriteMode = TxmPV('{ioc_prefix}TIFF1:FileWriteMode')
    TIFF1_NumCapture = TxmPV('{ioc_prefix}TIFF1:NumCapture')
    TIFF1_Capture = TxmPV('{ioc_prefix}TIFF1:Capture')
    TIFF1_Capture_RBV = TxmPV('{ioc_prefix}TIFF1:Capture_RBV')
    TIFF1_FileName = TxmPV('{ioc_prefix}TIFF1:FileName')
    TIFF1_FullFileName_RBV = TxmPV('{ioc_prefix}TIFF1:FullFileName_RBV')
    TIFF1_FileTemplate = TxmPV('{ioc_prefix}TIFF1:FileTemplate')
    TIFF1_ArrayPort = TxmPV('{ioc_prefix}TIFF1:NDArrayPort')
    
    # Motor PV's
    Motor_SampleX = TxmPV('32idcTXM:nf:c0:m1.VAL')
    Motor_SampleY = TxmPV('32idcTXM:mxv:c1:m1.VAL') # for the TXM
    # Professional Instrument air bearing rotary stage
    Motor_SampleRot = TxmPV('32idcTXM:ens:c1:m1.VAL')
    # Smaract XZ TXM set
    Motor_Sample_Top_X = TxmPV('32idcTXM:mcs:c3:m7.VAL')
    Motor_Sample_Top_Z = TxmPV('32idcTXM:mcs:c1:m8.VAL')
    # # Mosaic scanning axes
    # Motor_X_Tile = TxmPV('32idc01:m33.VAL')
    # Motor_Y_Tile = TxmPV('32idc02:m15.VAL')
    
    # Zone plate:
    zone_plate_x = TxmPV('32idcTXM:mcs:c2:m2.VAL')
    zone_plate_y = TxmPV('32idc01:m110.VAL')
    zone_plate_z = TxmPV('32idcTXM:mcs:c2:m3.VAL')
    # MST2 = vertical axis
    # pv.Smaract_mode.put(':MST3,100,500,100')
    Smaract_mode = TxmPV('32idcTXM:mcsAsyn1.AOUT')
    zone_plate_2_x = TxmPV('32idcTXM:mcs:c0:m3.VAL')
    zone_plate_2_y = TxmPV('32idcTXM:mcs:c0:m1.VAL')
    zone_plate_2_z = TxmPV('32idcTXM:mcs:c0:m2.VAL')
    
    # CCD motors:
    CCD_Motor = TxmPV('32idcTXM:mxv:c1:m6.VAL', float, default=3200)
    
    # Shutter PV's
    ShutterA_Open = TxmPV('32idb:rshtrA:Open', permit_required=True)
    ShutterA_Close = TxmPV('32idb:rshtrA:Close', permit_required=True)
    ShutterA_Move_Status = TxmPV('PB:32ID:STA_A_FES_CLSD_PL', default=0)
    ShutterB_Open = TxmPV('32idb:fbShutter:Open.PROC', permit_required=True)
    ShutterB_Close = TxmPV('32idb:fbShutter:Close.PROC', permit_required=True)
    ShutterB_Move_Status = TxmPV('PB:32ID:STA_B_SBS_CLSD_PL', default=0)
    ExternalShutter_Trigger = TxmPV('32idcTXM:shutCam:go', permit_required=True)
    # State 0 = Close, 1 = Open
    Fast_Shutter_Uniblitz = TxmPV('32idcTXM:uniblitz:control')
    
    # Fly scan PV's for nano-ct TXM using Profession Instrument air-bearing stage
    Fly_ScanDelta = TxmPV('32idcTXM:PSOFly3:scanDelta')
    Fly_StartPos = TxmPV('32idcTXM:PSOFly3:startPos')
    Fly_EndPos = TxmPV('32idcTXM:PSOFly3:endPos')
    Fly_SlewSpeed = TxmPV('32idcTXM:PSOFly3:slewSpeed')
    Fly_Taxi = TxmPV('32idcTXM:PSOFly3:taxi')
    Fly_Run = TxmPV('32idcTXM:PSOFly3:fly')
    Fly_ScanControl = TxmPV('32idcTXM:PSOFly3:scanControl')
    Fly_Calc_Projections = TxmPV('32idcTXM:PSOFly3:numTriggers')
    Theta_Array = TxmPV('32idcTXM:PSOFly3:motorPos.AVAL')
    Fly_Set_Encoder_Pos = TxmPV('32idcTXM:eFly:EncoderPos')
    
    # Theta controls
    Reset_Theta = TxmPV('32idcTXM:SG_RdCntr:reset.PROC')
    Proc_Theta = TxmPV('32idcTXM:SG_RdCntr:cVals.PROC')
    Theta_Array = TxmPV('32idcTXM:eFly:motorPos.AVAL')
    Theta_Cnt = TxmPV('32idcTXM:SG_RdCntr:aSub.VALB')
    
    # Misc PV's
    Image1_Callbacks = TxmPV('{ioc_prefix}image1:EnableCallbacks')
    ExternShutterExposure = TxmPV('32idcTXM:shutCam:tExpose')
    SetSoftGlueForStep = TxmPV('32idcTXM:SG3:MUX2-1_SEL_Signal')
    # ClearTheta = TxmPV('32idcTXM:recPV:PV1_clear')
    ExternShutterDelay = TxmPV('32idcTXM:shutCam:tDly')
    Interferometer = TxmPV('32idcTXM:SG2:UpDnCntr-1_COUNTS_s')
    Interferometer_Update = TxmPV('32idcTXM:SG2:UpDnCntr-1_COUNTS_SCAN.PROC')
    Interferometer_Reset = TxmPV('32idcTXM:SG_RdCntr:reset.PROC')
    Interferometer_Cnt = TxmPV('32idcTXM:SG_RdCntr:aSub.VALB')
    Interferometer_Arr = TxmPV('32idcTXM:SG_RdCntr:cVals.AA')
    Interferometer_Proc_Arr = TxmPV('32idcTXM:SG_RdCntr:cVals.PROC')
    Interferometer_Val = TxmPV('32idcTXM:userAve4.VAL')
    Interferometer_Mode = TxmPV('32idcTXM:userAve4_mode.VAL')
    Interferometer_Acquire = TxmPV('32idcTXM:userAve4_acquire.PROC')
    
    # Proc1 PV's
    Proc1_Callbacks = TxmPV('{ioc_prefix}Proc1:EnableCallbacks')
    Proc1_ArrayPort = TxmPV('{ioc_prefix}Proc1:NDArrayPort')
    Proc1_Filter_Enable = TxmPV('{ioc_prefix}Proc1:EnableFilter')
    Proc1_Filter_Type = TxmPV('{ioc_prefix}Proc1:FilterType')
    Proc1_Num_Filter = TxmPV('{ioc_prefix}Proc1:NumFilter')
    Proc1_Reset_Filter = TxmPV('{ioc_prefix}Proc1:ResetFilter')
    Proc1_AutoReset_Filter = TxmPV('{ioc_prefix}Proc1:AutoResetFilter')
    Proc1_Filter_Callbacks = TxmPV('{ioc_prefix}Proc1:FilterCallbacks')
    
    # Energy PV's
    DCMmvt = TxmPV('32ida:KohzuModeBO.VAL', permit_required=True)
    GAPputEnergy = TxmPV('32id:ID32us_energy', permit_required=True, wait=False)
    EnergyWait = TxmPV('ID32us:Busy')
    DCMputEnergy = TxmPV('32ida:BraggEAO.VAL', float, default=8.6,
                         permit_required=True)
    
    #interlaced
    Interlaced_PROC = TxmPV('32idcTXM:iFly:interlaceFlySub.PROC')
    Interlaced_Theta_Arr = TxmPV('32idcTXM:iFly:interlaceFlySub.VALC')
    Interlaced_Num_Cycles = TxmPV('32idcTXM:iFly:interlaceFlySub.C')
    Interlaced_Num_Cycles_RBV = TxmPV('32idcTXM:iFly:interlaceFlySub.VALH')
    Interlaced_Images_Per_Cycle = TxmPV('32idcTXM:iFly:interlaceFlySub.A')
    Interlaced_Images_Per_Cycle_RBV = TxmPV('32idcTXM:iFly:interlaceFlySub.VALF')
    Interlaced_Num_Sub_Cycles = TxmPV('32idcTXM:iFly:interlaceFlySub.B')
    Interlaced_Num_Sub_Cycles_RBV = TxmPV('32idcTXM:iFly:interlaceFlySub.VALG')
    
    def __init__(self, has_permit=False, is_attached=True, ioc_prefix="",
                 use_shutter_A=False, use_shutter_B=True, zp_diameter=180,
                 drn=60):
        self.is_attached = is_attached
        self.has_permit = has_permit
        self.ioc_prefix = ioc_prefix
        self.use_shutter_A = use_shutter_A
        self.use_shutter_B = use_shutter_B
        self.zp_diameter = zp_diameter
        self.drn = drn
    
    @contextmanager
    def wait_pvs(self, block=True):
        """Context manager that allows for setting multiple PVs
        asynchronously.
        
        This manager creates an empty queue for PV objects. After
        exiting the inner code, it then waits until all the PV's to be
        finished before returning. This method is tightly coupled with
        the settings of the relevant ``TxmPV`` objects.
        
        """
        # Save old queue to resore it later on
        old_queue = self.pv_queue
        # Set up an event loop
        self.pv_queue = []
        # Return execution to the calling script
        yield self.pv_queue
        # Wait for all the PVs to be finished
        num_promises = len(self.pv_queue)
        while block and not all([pv.is_complete for pv in self.pv_queue]):
            time.sleep(0.01)
        log.debug("Completed %d queued PV's", num_promises)
        # Restore the old PV queue
        self.pv_queue = old_queue
    
    def flush_pvs(self):
        """This method blocks until all the PV's in the pv_queue have reached
        their target values, then clears the queue.
        
        """
        self.pv_queue = []
    
    def wait_pv(self, pv_name, target_val, timeout=DEFAULT_TIMEOUT):
        """Wait for a process variable to reach given value.
        
        This function polls the process variable (PV) and blocks until
        the PV reaches the target value or the max timeout, whichever
        comes first. This function immediately returns True if
        self.is_attached is False.
        
        Parameters
        ----------
        pv : str
          The process variable to be monitored, as defined by
          the pyepics system.
        target_val
          The value the PV should acquire before returning.
        timeout : int, optional
          How long to wait, in seconds, before giving up. Negative
          values cause the function to wait forever.
        
        Returns
        -------
        val : bool
          True if value was set properly, False if the timeout expired
          before the target value was reached.
        
        """
        log_msg = "called wait_pv({name}, {val}, timeout={timeout})"
        log.debug(log_msg.format(name=pv_name, val=target_val,
                                 timeout=timeout))
        # Delay for pv to change
        time.sleep(self.POLL_INTERVAL)
        startTime = time.time()
        # Enter into infinite loop polling the PV status
        while(True and self.is_attached):
            real_PV = self.__class__.__dict__[pv_name]
            pv_val = real_PV.__get__(self)
            if (pv_val != target_val):
                if timeout > -1:
                    curTime = time.time()
                    diffTime = curTime - startTime
                    if diffTime >= timeout:
                        msg = "Timed out '{}' ({}) after {}s"
                        msg = msg.format(pv_name, target_val, timeout)
                        raise exceptions_.TimeoutError(msg)
                time.sleep(.01)
            else:
                log.debug("Ended wait_pv()")
                return True
    
    def move_sample(self, x=None, y=None, z=None, theta=None):
        """Move the sample to the given (x, y, z) position.
        
        This method is non-blocking.
        
        Parameters
        ----------
        x, y, z : float, optional
          The new position to move the sample to.
        theta : float, optional
          Rotation axis angle to set to.
        """
        log.debug('Moving sample to (%s, %s, %s)', x, y, z)
        if x is not None:
            self.Motor_Sample_Top_X = float(x)
        if y is not None:
            self.Motor_SampleY = float(y)
        if z is not None:
            self.Motor_Sample_Top_Z = float(z)
        if theta is not None:
            self.Motor_SampleRot = theta
        log.debug("Sample moved to (x=%s, y=%s, z=%s, θ=%s°)", x, y, z, theta)
    
    @permit_required
    def move_energy(self, energy, constant_mag=True, gap_offset=0., 
                    correct_backlash=True):
        """Change the energy of the X-ray source and optics.
        
        The undulator gap, monochromator, zone-plate and (optionally)
        detector will be moved.
        
        Parameters
        ----------
        energy : float
          The new energy (in kEV) for the X-ray source.
        constant_mag : bool, optional
          If truthy, the detector will also be moved to correct for
          the change in focal length.
        gap_offset : float, optional
          Extra energy to add to the value sent to the undulator gap.
        correct_backlash : bool, optional
          If enabled, this method will correct for slop in the GAP
          motors. Only needed for large changes (eg >0.01 keV)
        """
        # Helper function for converting energy to wavelength
        kev_to_nm = lambda kev: 1240. / (kev * 1000.)
        # Check that the energy given is valid for this instrument
        in_range = self.E_RANGE[0] <= energy <= self.E_RANGE[1]
        if not in_range:
            msg = "Energy {energy} keV not in range {lower} - {upper} keV"
            msg = msg.format(energy=energy, lower=self.E_RANGE[0],
                             upper=self.E_RANGE[1])
            raise exceptions_.EnergyError(msg)
        # Get the current values
        old_energy = self.DCMputEnergy
        old_CCD = self.CCD_Motor
        old_wavelength = kev_to_nm(old_energy)
        old_ZP_focal = self.zp_diameter * self.drn / (1000.0 * old_wavelength)
        inner =  math.sqrt(old_CCD**2 - 4.0 * old_CCD * old_ZP_focal)
        old_D = (old_CCD + inner) / 2.0
        # Calculate target values
        new_wavelength = kev_to_nm(energy)
        new_ZP_focal = self.zp_diameter * self.drn / (1000.0 * new_wavelength)
        # Prepare the instrument for moving energy
        old_DCM_mode = self.DCMmvt
        self.DCMmvt = 1
        # Move the detector and objective optics
        if constant_mag:
            # Calculate target values
            mag = (old_D - old_ZP_focal) / old_ZP_focal
            dist_ZP_ccd = mag * new_ZP_focal + new_ZP_focal
            ZP_WD = dist_ZP_ccd * new_ZP_focal / (dist_ZP_ccd - new_ZP_focal)
            new_CCD_position = ZP_WD + dist_ZP_ccd
            # Log new values
            log.debug("Constant magnification: %.2f", mag)
            log.debug("New CCD z-position: %f", new_CCD_position)
            # Execute motor movement
            self.CCD_Motor = new_CCD_position
        else: # Varying magnification
            new_D = (old_CCD + math.sqrt(old_CCD * old_CCD - 4.0 * old_CCD * ZP_focal) ) / 2.0
            ZP_WD = new_D * new_ZP_focal / (new_D - ZP_focal)
            new_mag = (old_D - old_ZP_focal) / old_ZP_focal
            log.debug("New magnification: %.2f", new_mag)
        # Move the zoneplate
        log.debug("New zoneplate z-position: %.5f", ZP_WD)
        self.zone_plate_z = ZP_WD
        # Move the upstream source/optics
        log.debug("New DCM Energy and Gap Energy: %f", energy)
        self.DCMputEnergy = energy
        if correct_backlash:
            # Come up from below to correct for motor slop
            log.debug("Correcting backlash")
            self.GAPputEnergy = energy
        self.GAPputEnergy = energy + gap_offset
        self.DCMmvt = old_DCM_mode
        log.debug("Changed energy to %.4f keV (%.4f nm).", energy, new_wavelength)
    
    def open_shutters(self):
        """Open the shutters to allow light in. The specific shutter(s) that
        opens depends on the values of ``self.use_shutter_A`` and
        ``self.use_shutter_B``.
        
        """
        starttime = time.time()
        if self.use_shutter_A:
            log.debug("Opening shutter A")
            self.ShutterA_Open = 1 # wait=True
            self.wait_pv('ShutterA_Move_Status', self.SHUTTER_OPEN)
        if self.use_shutter_B:
            log.debug("Opening shutter B")
            self.ShutterB_Open = 1
            self.wait_pv('ShutterB_Move_Status', self.SHUTTER_OPEN)
        # Set status flags
        if self.use_shutter_A or self.use_shutter_B:
            self.shutters_are_open = True
        else:
            self.shutters_are_open = False
        # Log results info
        if self.use_shutter_A and self.use_shutter_B:
            which_shutters = "shutters A and B"
        elif self.use_shutter_A:
            which_shutters = "shutter A"
        elif self.use_shutter_B:
            which_shutters = "shutter B"
        else:
            which_shutters = "no shutters"
        if self.use_shutter_A or self.use_shutter_B or not self.is_attached:
            duration = time.time() - starttime
            log.info("Opened %s in %.2f sec", which_shutters, duration)
        else:
            warnings.warn("Neither shutter A nor B enabled.")
    
    def close_shutters(self):
        """Close the shutters to stop light in. The specific shutter(s) that
        closes depends on the values of ``self.use_shutter_A`` and
        ``self.use_shutter_B``.
        
        """
        starttime = time.time()
        if self.use_shutter_A:
            log.debug("Closing shutter A")
            self.ShutterA_Close = 1 # wait=True
            self.wait_pv('ShutterA_Move_Status', self.SHUTTER_CLOSED)
        if self.use_shutter_B:
            log.debug("Closing shutter B")
            self.ShutterB_Close = 1
            self.wait_pv('ShutterB_Move_Status', self.SHUTTER_CLOSED)
        # Set status flags
        self.shutters_are_open = False
        # Log results info
        if self.use_shutter_A and self.use_shutter_B:
            which_shutters = "shutters A and B"
        elif self.use_shutter_A:
            which_shutters = "shutter A"
        elif self.use_shutter_B:
            which_shutters = "shutter B"
        else:
            which_shutters = "no shutters"
        if self.use_shutter_A or self.use_shutter_B or not self.is_attached:
            duration = time.time() - starttime
            log.info("Closed %s in %.2f sec", which_shutters, duration)
        else:
            warnings.warn("Neither shutter A nor B enabled.")
    
    def setup_hdf_writer(self, filename=None, num_projections=1,
                         write_mode="Stream", num_recursive_images=1):
        """Prepare the HDF file writer to accept data.
        
        Parameters
        ----------
        filename : str
          The name of the HDF file to save data to.
        num_projections : int
          Total number of projections to collect at one time.
        write_mode : str, optional
          What mode to use for the HDF writer. Gets passed to a PV.
        num_recursive_images : int, optional
          How many images to use in the recursive filter. If 1
          (default), recursive filtering will be disabled.
        
        """
        log.debug('setup_hdf_writer() called')
        if num_recursive_images > 1:
            # Enable recursive filter
            self.Proc1_Callbacks = 'Enable'
            self.Proc1_Filter_Enable = 'Disable'
            self.HDF1_ArrayPort = 'PROC1'
            self.Proc1_Filter_Type = self.RECURSIVE_FILTER_TYPE
            self.Proc1_Num_Filter = num_recursive_images
            self.Proc1_Reset_Filter = 1
            self.Proc1_AutoReset_Filter = 'Yes'
            self.Proc1_Filter_Callbacks = 'Array N only'
        else:
            # No recursive filter, just 1 image
            # global_PVs['Proc1_Callbacks'].put('Disable')
            self.Proc1_Filter_Enable = 'Disable'
            self.HDF1_ArrayPort = self.Proc1_ArrayPort
        # Other HDF parameters
        # global_PVs['HDF1_AutoSave'].put('Yes')
        # global_PVs['HDF1_DeleteDriverFile'].put('No')
        # global_PVs['HDF1_EnableCallbacks'].put('Enable')
        # global_PVs['HDF1_BlockingCallbacks'].put('No')
        # Count total number of projections needed
        self.HDF1_NumCapture = num_projections
        self.HDF1_FileWriteMode = write_mode
        if filename is not None:
            self.HDF1_FileName = filename
        self.HDF1_Capture = self.CAPTURE_ENABLED
        # ?? Is this wait_pv really necessary?
        self.wait_pv('HDF1_Capture', self.CAPTURE_ENABLED)
        # Clean up and set some status variables
        log.debug("Finished setting up HDF writer for %s.", self.HDF1_FileName)
        self.hdf_writer_ready = True
    
    def setup_tiff_writer(self, filename, num_projections=1,
                          write_mode="Stream", num_recursive_images=1):
        """Prepare the TIFF file writer to accept data.
        
        Parameters
        ----------
        filename : str
          The name of the HDF file to save data to.
        num_projections : int
          Total number of projections to collect at one time.
        write_mode : str, optional
          What mode to use for the HDF writer. Gets passed to a PV.
        num_recursive_images : int, optional
          How many images to use in the recursive filter. If 1
          (default), recursive filtering will be disabled.
        
        """
        log.debug('setup_tiff_writer() called')
        if num_recursive_images > 1:
            # Recursive filter enabled
            self.Proc1_Callbacks = 'Enable'
            self.Proc1_Filter_Enable = 'Disable'
            self.TIFF1_ArrayPort = 'PROC1'
            self.Proc1_Filter_Type = self.RECURSIVE_FILTER_TYPE
            self.Proc1_Num_Filter = num_recursive_images
            self.Proc1_Reset_Filter = 1
            self.Proc1_AutoReset_Filter = 'Yes'
            self.Proc1_Filter_Callbacks = 'Array N only'
        self.TIFF1_AutoSave = 'Yes'
        self.TIFF1_DeleteDriverFile = 'No'
        self.TIFF1_EnableCallbacks = 'Enable'
        self.TIFF1_BlockingCallbacks = 'No'
        self.TIFF1_NumCapture = num_projections
        self.TIFF1_FileWriteMode = write_mode
        self.TIFF1_FileName = filename
        self.TIFF1_Capture = self.CAPTURE_ENABLED
        # ?? Is this wait_pv really necessary?
        self.wait_pv('TIFF1_Capture', self.CAPTURE_ENABLED)
        log.debug("Finished setting up TIFF writer for %s.", filename)
    
    def _trigger_multiple_projections(self, exposure, num_projections):
        """Trigger the detector to capture multiple projections one after
        another."""
        starttime = time.time()
        self.Cam1_ImageMode = 'Multiple'
        if self.pg_external_trigger:
            # Set external trigger mode
            self.Cam1_TriggerMode = 'Overlapped'
            self.Cam1_NumImages = 1
            for i in range(num_projections):
                # Trigger each projection one at a time
                self.Cam1_Acquire = self.DETECTOR_ACQUIRE
                self.wait_pv('Cam1_Acquire', self.DETECTOR_ACQUIRE, timeout=2)
                self.Cam1_SoftwareTrigger = 1
                self.wait_pv('Cam1_Acquire', self.DETECTOR_IDLE, timeout=exposure + 5)
        else:
            # Trigger the projections all at once
            self.Cam1_TriggerMode = 'Internal'
            self.Cam1_NumImages = num_projections
            self.Cam1_Acquire = self.DETECTOR_ACQUIRE
            timeout = num_projections * exposure + 5
            self.wait_pv('Cam1_Acquire', self.DETECTOR_IDLE, timeout=timeout)
        # Log the results
        duration = time.time() - starttime
        log.info("Captured %d projections in %.3f sec", num_projections, duration)
    
    def _trigger_single_projection(self, exposure):
        """Trigger the detector to capture just one projection."""
        # Start detector acquire
        self.Cam1_Acquire = self.DETECTOR_ACQUIRE
        # wait for acquire to finish
        self.wait_pv('Cam1_Acquire', self.DETECTOR_IDLE,
                    timeout=exposure * 2)
    
    def capture_projections(self, num_projections=1, exposure=0.5):
        """Trigger the capturing of projection images from the detector.
        
        Parameters
        ----------
        num_projections : int, optional
          How many projections to acquire.
        exposure : float, optional
          Exposure time for each frame in seconds.
        
        """
        # Raise a warning if the shutters are closed
        if not self.shutters_are_open:
            msg = "Collecting projections with shutters closed."
            warnings.warn(msg, RuntimeWarning)
            log.warning(msg)
        # Set frame type
        self.Cam1_FrameType = self.FRAME_DATA
        # Collect the data
        if num_projections == 1:
            ret = self._trigger_single_projection(exposure=exposure)
        else:
            ret = self._trigger_multiple_projections(
                num_projections=num_projections, exposure=exposure)
        return ret
    
    def capture_white_field(self, num_projections=1, exposure=0.5):
        """Trigger the capturing of projection images from the detector with
        the shutters open and no sample present.
        
        Parameters
        ----------
        num_projections : int, optional
          How many projections to acquire.
        exposure : float, optional
          Exposure time for each frame in seconds.
        
        """
        # Raise a warning if the shutters are closed.
        if not self.shutters_are_open:
            msg = "Collecting white field with shutters closed."
            warnings.warn(msg, RuntimeWarning)
            log.warning(msg)
        self.Cam1_FrameType = self.FRAME_WHITE
        # Collect the data
        if num_projections == 1:
            ret = self._trigger_single_projection(exposure=exposure)
        else:
            ret = self._trigger_multiple_projections(
                num_projections=num_projections, exposure=exposure)
        return ret
    
    def capture_dark_field(self, num_projections=1, exposure=0.5):
        """Trigger the capturing of projection images from the detector with
        the shutters closed.
        
        The shutter should be closed before calling this method.
        
        Parameters
        ----------
        num_projections : int, optional
          How many projections to acquire.
        exposure : float, optional
          Exposure time for each frame in seconds.
        
        """
        # Raise a warning if the shutters are open.
        if self.shutters_are_open:
            msg = "Collecting dark field with shutters open."
            warnings.warn(msg, RuntimeWarning)
            log.warning(msg)
        self.Cam1_FrameType = self.FRAME_DARK
        # Collect the data
        if num_projections == 1:
            ret = self._trigger_single_projection(exposure=exposure)
        else:
            ret = self._trigger_multiple_projections(
                num_projections=num_projections, exposure=exposure)
        return ret


class MicroCT(TXM):
    """TXM operating with the front micro-CT stage."""
    # Flyscan PV's
    Fly_ScanDelta = TxmPV('32idcTXM:eFly:scanDelta')
    Fly_StartPos = TxmPV('32idcTXM:eFly:startPos')
    Fly_EndPos = TxmPV('32idcTXM:eFly:endPos')
    Fly_SlewSpeed = TxmPV('32idcTXM:eFly:slewSpeed')
    Fly_Taxi = TxmPV('32idcTXM:eFly:taxi')
    Fly_Run = TxmPV('32idcTXM:eFly:fly')
    Fly_ScanControl = TxmPV('32idcTXM:eFly:scanControl')
    Fly_Calc_Projections = TxmPV('32idcTXM:eFly:calcNumTriggers')
    Fly_Set_Encoder_Pos = TxmPV('32idcTXM:eFly:EncoderPos')
    Theta_Array = TxmPV('32idcTXM:eFly:motorPos.AVAL')

    # Motor PVs
    Motor_SampleX = TxmPV('32idc01:m33.VAL')
    Motor_SampleY = TxmPV('32idc02:m15.VAL') # for the micro-CT system
    Motor_SampleRot = TxmPV('32idcTXM:hydra:c0:m1.VAL') # PI Micos air bearing rotary stage
    Motor_SampleZ = TxmPV('32idcTXM:mcs:c1:m1.VAL')
    Motor_Sample_Top_X = TxmPV('32idcTXM:mcs:c1:m2.VAL') # Smaract XZ micro-CT set
    Motor_Sample_Top_Z = TxmPV('32idcTXM:mcs:c1:m1.VAL') # Smaract XZ micro-CT set
    Motor_X_Tile = TxmPV('32idc01:m33.VAL')
    Motor_Y_Tile = TxmPV('32idc02:m15.VAL')

