# -*- coding: utf-8 -*-

"""Defines TXM classes for controlling the Transmission X-ray
Microscope at Advanced Photon Source beamline 32-ID-C.

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

import h5py
import tqdm
from epics import PV as EpicsPV, get_pv

import exceptions_
from txm_pv import TxmPV

DEFAULT_TIMEOUT = 20 # PV timeout in seconds

log = logging.getLogger(__name__)


def permit_required(real_func, return_value=None):
    """Decorates a method so it can only open with a permit.
    
    This method decorator ensures that the decorated method can only
    be called on an object that has a shutter permit. If it doesn't,
    then an exceptions is raised.
    
    Parameters
    ----------
    real_func
      The function or method to decorate.
    
    """
    def wrapped_func(obj, *args, **kwargs):
        # Inner function that checks the status of permit
        if obj.has_permit:
            ret = real_func(obj, *args, **kwargs)
        else:
            msg = "Shutter permit not granted."
            warnings.warn(msg, RuntimeWarning)
            ret = None
        return ret
    return wrapped_func


class PVPromise():
    is_complete = False
    result = None
    
    def complete(self):
        self.is_complete = True


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
    zp_diameter = 180
    drn = 60
    gap_offset = 0.15 # Added to undulator gap setting
    pv_queue = None
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
    FRAME_DARK = 1
    FRAME_WHITE = 2
    DETECTOR_IDLE = 0
    DETECTOR_ACQUIRE = 1
    HDF_IDLE = 0
    HDF_WRITING = 1
    
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
    Cam1_Acquire = TxmPV('{ioc_prefix}cam1:Acquire', wait=False)
    Cam1_Display = TxmPV('{ioc_prefix}image1:EnableCallbacks')
    Cam1_Status = TxmPV('{ioc_prefix}cam1:DetectorState_RBV', as_string=True)
    
    # HDF5 writer PV's
    HDF1_AutoSave = TxmPV('{ioc_prefix}HDF1:AutoSave')
    HDF1_DeleteDriverFile = TxmPV('{ioc_prefix}HDF1:DeleteDriverFile')
    HDF1_EnableCallbacks = TxmPV('{ioc_prefix}HDF1:EnableCallbacks')
    HDF1_BlockingCallbacks = TxmPV('{ioc_prefix}HDF1:BlockingCallbacks')
    HDF1_FileWriteMode = TxmPV('{ioc_prefix}HDF1:FileWriteMode')
    HDF1_NumCapture = TxmPV('{ioc_prefix}HDF1:NumCapture')
    HDF1_Capture = TxmPV('{ioc_prefix}HDF1:Capture', wait=False)
    HDF1_Capture_RBV = TxmPV('{ioc_prefix}HDF1:Capture_RBV')
    HDF1_FileName = TxmPV('{ioc_prefix}HDF1:FileName', dtype=str,
                          as_string=True)
    HDF1_FullFileName_RBV = TxmPV('{ioc_prefix}HDF1:FullFileName_RBV',
                                  dtype=str, as_string=True)
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
    Motor_SampleX = TxmPV('32idcTXM:nf:c0:m1.VAL', dtype=float)
    Motor_SampleY = TxmPV('32idcTXM:mxv:c1:m1.VAL', dtype=float)
    # Professional Instrument air bearing rotary stage
    Motor_SampleRot = TxmPV('32idcTXM:ens:c1:m1.VAL', dtype=float)
    # Smaract XZ TXM set
    Motor_Sample_Top_X = TxmPV('32idcTXM:mcs:c3:m7.VAL', dtype=float)
    Motor_Sample_Top_Z = TxmPV('32idcTXM:mcs:c3:m8.VAL', dtype=float)
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
    CCD_Motor = TxmPV('32idcTXM:mxv:c1:m6.VAL', float)
    
    # Shutter PV's
    ShutterA_Open = TxmPV('32idb:rshtrA:Open', permit_required=True)
    ShutterA_Close = TxmPV('32idb:rshtrA:Close', permit_required=True)
    ShutterA_Move_Status = TxmPV('PB:32ID:STA_A_FES_CLSD_PL')
    ShutterB_Open = TxmPV('32idb:fbShutter:Open.PROC', permit_required=True)
    ShutterB_Close = TxmPV('32idb:fbShutter:Close.PROC', permit_required=True)
    ShutterB_Move_Status = TxmPV('PB:32ID:STA_B_SBS_CLSD_PL')
    ExternalShutter_Trigger = TxmPV('32idcTXM:shutCam:go', permit_required=True)
    # State 0 = Close, 1 = Open
    Fast_Shutter_Uniblitz = TxmPV('32idcTXM:uniblitz:control', permit_required=True)
    
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
    DCMputEnergy = TxmPV('32ida:BraggEAO.VAL', dtype=float,
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
    
    def __init__(self, has_permit=False, ioc_prefix="32idcPG3:",
                 use_shutter_A=False, use_shutter_B=True):
        self.has_permit = has_permit
        self.ioc_prefix = ioc_prefix
        self.use_shutter_A = use_shutter_A
        self.use_shutter_B = use_shutter_B
    
    def pv_get(self, pv_name, *args, **kwargs):
        """Retrieve the current process variable value.
        
        Parameters
        ----------
        *args, **kwargs
          Extra arguments that get passed to :py:meth:``epics.PV.get``
        
        """
        epics_pv = EpicsPV(pv_name)
        return epics_pv.get(*args, **kwargs)

    def pv_put(self, pv_name, value, wait, *args, **kwargs):
        """Set the current process variable value.
        
        When ``wait=True``, this method becomes closely linked with
        the concept of deferred PVs. Normally, this method will block
        until the PV has been set. When inside a
        :py:meth:``TXM.wait_pvs`` context, this method adds a promise
        to the queue so the :py:meth:``TXM.wait_pvs`` manager can
        handle the blocking. When ``wait=False``, this method returns
        immediately once the value has been sent and does not alter
        the PV queue.
        
        Parameters
        ----------
        wait : bool, optional
          If true, the method will keep track of when PV has been set.
        *args, **kwargs
          Extra arguments that get passed to :py:meth:``epics.PV.get``
        
        """
        if self.pv_queue is not None:
            # Non-blocking, deferred PV waiting
            promise = PVPromise()
            ret = self._pv_put(pv_name, value, wait=False, callback=promise.complete)
            self.pv_queue.append(promise)
        else:
            # Blocking PV waiting
            ret = self._pv_put(pv_name, value, wait=wait, *args, **kwargs)
        return ret
    
    def _complete_promise(self, promise):
        print(promise)
    
    def _pv_put(self, pv_name, value, wait, *args, **kwargs):
        """Retrieves the epics PV and calls its ``put`` method."""
        print(pv_name, value, wait)
        epics_pv = EpicsPV(pv_name)
        return epics_pv.put(value, wait=wait, *args, **kwargs)
    
    @contextmanager
    def wait_pvs(self, block=True):
        """Context manager that allows for setting multiple PVs
        asynchronously.
        
        This manager creates an empty queue for PV objects. If
        blocking, upon exiting the context it waits for all the PV's
        to finished before moving on. If non-blocking, this basically
        turns off blocking feature on any TxmPVs that have
        ``wait=True`` (so use with caution).
        
        Arguments
        ---------
        block : bool, optional
          If True, this function will wait for all PVs to finish
        before continuing.
        
        """
        # Save old queue to resore it later on
        old_queue = self.pv_queue
        # Prepare a queue for holding PV promises
        self.pv_queue = []
        # Return execution to the inner block
        yield self.pv_queue
        # Wait for all the PVs to be finished
        num_promises = len(self.pv_queue)
        while block and not all([pv.is_complete for pv in self.pv_queue]):
            time.sleep(0.01)
        log.debug("Completed %d queued PV's", num_promises)
        # Restore the old PV queue
        self.pv_queue = old_queue
    
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
        while(True):
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
        
        Parameters
        ----------
        x, y, z : float, optional
          The new position to move the sample to.
        theta : float, optional
          Rotation axis angle to set to.
        """
        log.debug('Moving sample to (%s, %s, %s)', x, y, z)
        if theta is not None:
            self.Motor_SampleRot = theta
        if x is not None:
            self.Motor_Sample_Top_X = float(x)
        if y is not None:
            self.Motor_SampleY = float(y)
        if z is not None:
            self.Motor_Sample_Top_Z = float(z)
        # Log actual x, y, z, θ values
        msg = "Sample moved to (x={x:.2f}, y={y:.2f}, z={z:.2f}, θ={theta:.2f}°)"
        msg = msg.format(x=self.Motor_Sample_Top_X,
                         y=self.Motor_SampleY,
                         z=self.Motor_Sample_Top_Z,
                         theta=self.Motor_SampleRot)
        log.debug(msg)
    
    @permit_required
    def move_energy(self, energy, constant_mag=True,
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
        correct_backlash : bool, optional
          If enabled, this method will correct for slop in the gap
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
            new_D = (old_CCD + math.sqrt(old_CCD * old_CCD - 4.0 * old_CCD * new_ZP_focal) ) / 2.0
            ZP_WD = new_D * new_ZP_focal / (new_D - new_ZP_focal)
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
            self.wait_pv('EnergyWait', 0)
        self.GAPputEnergy = energy + self.gap_offset
        self.DCMmvt = old_DCM_mode
        self.wait_pv('EnergyWait', 0)
        log.debug("Changed energy to %.4f keV (%.4f nm).", energy, new_wavelength)
    
    @permit_required
    def open_shutters(self):
        """Open the shutters to allow light in. The specific shutter(s) that
        opens depends on the values of ``self.use_shutter_A`` and
        ``self.use_shutter_B``.
        
        """
        starttime = time.time()
        if self.use_shutter_A:
            log.debug("Opening shutter A")
            self.ShutterA_Open = 1
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
            log.debug("Opened %s in %.2f sec", which_shutters, duration)
        else:
            warnings.warn("Neither shutter A nor B enabled.")
    
    @permit_required
    def close_shutters(self):
        """Close the shutters to stop light in. The specific shutter(s) that
        closes depends on the values of ``self.use_shutter_A`` and
        ``self.use_shutter_B``.
        
        """
        starttime = time.time()
        if self.use_shutter_A:
            log.debug("Closing shutter A")
            self.ShutterA_Close = 1
            self.wait_pv('ShutteA_Move_Status', self.SHUTTER_CLOSED)
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
    
    @property
    def hdf_filename(self):
        return self.HDF1_FullFileName_RBV
    
    def hdf_file(self, timeout=10, *args, **kwargs):
        start_time = time.time()
        # Wait for the HDF writer to be done using the HDF file
        self.wait_pv('HDF1_Capture_RBV', self.HDF_IDLE, timeout=timeout)
        return h5py.File(self.hdf_filename, *args, **kwargs)
    
    @property
    def exposure_time(self):
        """Exposure time for the CCD in seconds."""
        current_time = max(self.Cam1_AcquireTime, self,Cam1AcquirePeriod)
        return self.Cam1_AcquireTime
    
    @exposure_time.setter
    def exposure_time(self, val):
        self.Cam1_AcquireTime = val
        self.Cam1_AcquirePeriod = val
        
    def setup_detector(self, exposure=0.5, live_display=False):
        log.debug("%s live display.", "Enabled" if live_display else "Disabled")
        # Capture a dummy frame to that the HDF5 plugin will work
        self.Cam1_ImageMode = "Single"
        self.Cam1_TriggerMode = "Internal"
        self.exposure_time = 0.01
        self.Cam1_Acquire = self.DETECTOR_ACQUIRE
        self.wait_pv('Cam1_Acquire', self.DETECTOR_IDLE)

        # Now set the real settings for the detector
        self.Cam1_Display = live_display
        self.Cam1_ArrayCallbacks = 'Enable'
        self.SetSoftGlueForStep = '0'
        self.Cam1_FrameRateOnOff = False
        self.Cam1_TriggerMode = 'Overlapped'
        self.exposure_time = exposure
        # Prepare external shutter if necessary
        external_shutter = False
        if external_shutter:
            global_PVs['ExternShutterExposure'].put(float(variableDict['ExposureTime']))
            global_PVs['ExternShutterDelay'].put(float(variableDict['Ext_ShutterOpenDelay']))
            global_PVs['SetSoftGlueForStep'].put('1')
        log.debug("Finished setting up detector.")
    
    def setup_hdf_writer(self, num_projections=1, write_mode="Stream",
                         num_recursive_images=1):
        """Prepare the HDF file writer to accept data.
        
        Parameters
        ----------
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
            self.Proc1_Filter_Enable = 'Enable'
        else:
            # No recursive filter, just 1 image
            self.Proc1_Filter_Enable = 'Disable'
            self.HDF1_ArrayPort = self.Proc1_ArrayPort
        # Count total number of projections needed
        self.HDF1_NumCapture = num_projections
        self.HDF1_FileWriteMode = write_mode
        self.HDF1_Capture = self.CAPTURE_ENABLED
        self.wait_pv('HDF1_Capture', self.CAPTURE_ENABLED)
        # Clean up and set some status variables
        log.debug("Finished setting up HDF writer for %s.", self.HDF1_FullFileName_RBV)
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
        log.warning("setup_tiff_writer() not tested")
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
    
    def _trigger_projections(self, num_projections=1):
        """Trigger the detector to capture one (or more) projections.
        
        This method should only be used after setup_detector() and
        setup_hdf_writer() have been called. The value for
        num_projections given here should be less than or equal to the
        number given to each of the setup methods.
        
        Parameters
        ==========
        num_projections : int, optional
          How many projections to trigger.
        
        """
        suffix = 's' if num_projections > 1 else ''
        log.debug("Triggering %d projection%s", num_projections, suffix)
        self.Cam1_ImageMode = "Single"
        self.Cam1_NumImages = 1
        for i in range(num_projections):
            self.Cam1_Acquire = self.DETECTOR_ACQUIRE
            self.wait_pv('Cam1_Acquire', self.DETECTOR_ACQUIRE, 5)
            # Wait for the camera to be ready
            while self.Cam1_Acquire != self.DETECTOR_IDLE:
                time.sleep(0.01)
                self.Cam1_SoftwareTrigger = 1
            self.wait_pv('Cam1_Acquire', self.DETECTOR_IDLE, 5)
    
    def capture_projections(self, num_projections=1):
        """Trigger the capturing of projection images from the detector.
        
        Parameters
        ----------
        num_projections : int, optional
          How many projections to acquire.
       
        """
        # Raise a warning if the shutters are closed
        if not self.shutters_are_open:
            msg = "Collecting projections with shutters closed."
            warnings.warn(msg, RuntimeWarning)
        # Set frame collection data
        self.Cam1_FrameType = self.FRAME_DATA
        # Collect the data
        ret = self._trigger_projections(num_projections=num_projections)
        return ret
    
    def capture_white_field(self, num_projections=1):
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
        ret = self._trigger_projections(num_projections=num_projections)
        return ret
    
    def capture_dark_field(self, num_projections=1):
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
        ret = self._trigger_projections(num_projections=num_projections)
        return ret

    def capture_tomogram(self, angles, num_projections=1,
                         stabilize_sleep=10):
        """Collect data frames over a range of angles.
        
        Parameters
        ==========
        angles : np.ndarray
          An array of angles (in degrees) to use for collecting
          projections.
        num_projections : int, optional
          Number of projections to average at each angle.
        stablize_sleep : int, optional
          How long (in milliseconds) to wait after moving the rotation
          stage.
        
        """
        log.warning("capture_tomogram() not tested")
        log.debug('called tomo_scan()')
        # Prepare the instrument for data collection
        self.Cam1_FrameType = self.FRAME_DATA
        self.Cam1_NumImages = 1
        if num_projections > 1:
            old_filter = self.Proc1_Filter_Enable
            self.Proc1_Filter_Enable = 'Enable'
        # Cycle through each angle and collect data
        for sample_rot in tqdm.tqdm(angles, desc="Capturing tomogram", unit='rot'):
            self.move_sample(theta=sample_rot)
            log.debug('Stabilize Sleep: %d ms', stabilize_sleep)
            time.sleep(stabilize_sleep / 1000)
            # Trigger the camera
            self._trigger_projections(num_projections=num_projections)
        # Restore previous filter enabled state
        if num_projections > 1:
            self.Proc1_Filter_Enable = old_filter
    
    def epics_PV(self, pv_name):
        """Retrieve the epics process variable (PV) object for the given
        attribute name.
        
        Parameters
        ==========
        pv_name : str
          The name of the PV object. Should match the attribute on
          this TXM() object.
        
        """
        return self.__class__.__dict__[pv_name].epics_PV(txm=self)
    
    def reset_ccd(self):
        log.debug("Resetting CCD")
        # Sequence Internal / Overlapped / internal because of CCD bug!!
        self.Cam1_TriggerMode = 'Internal'
        self.Cam1_TriggerMode = 'Overlapped'
        self.Cam1_TriggerMode = 'Internal'
        # Other PV settings
        self.Proc1_Filter_Callbacks = 'Every array'
        self.Cam1_ImageMode = 'Continuous'
        self.Cam1_Display = 1
        self.Cam1_Acquire = self.DETECTOR_ACQUIRE
        self.wait_pv('Cam1_Acquire', self.DETECTOR_ACQUIRE, timeout=2)


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
