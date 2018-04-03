# -*- coding: utf-8 -*-

"""Defines TXM classes for controlling the Transmission X-ray
Microscope at Advanced Photon Source beamline 32-ID-C.

NanoTXM
  A nano-CT transmission X-ray microscope.
MicroTXM
  Similar to the nano-CT but for micro-CT.

"""

from __future__ import print_function, division

import os
import datetime as dt
import time
import math
import logging
import warnings
from contextlib import contextmanager
from collections import namedtuple

import numpy as np
import h5py
import tqdm
from epics import PV as EpicsPV, get_pv

from scanlib import TxmPV, permit_required, exceptions_

__author__ = 'Mark Wolf'
__copyright__ = 'Copyright (c) 2017, UChicago Argonne, LLC.'
__docformat__ = 'restructuredtext en'
__platform__ = 'Unix'
__version__ = '1.6'
__all__ = ['NanoTXM',
           'MicroTXM']

DEFAULT_TIMEOUT = 20 # PV timeout in seconds

log = logging.getLogger(__name__)


class PVPromise():
    is_complete = False
    result = None

    def __init__(self, pv_name=""):
        self.pv_name = pv_name
    
    def complete(self, pvname=""):
        self.is_complete = True


############################
# Main TXM Class definition
############################
class NanoTXM(object):
    """A class representing the Transmission X-ray Microscope at sector 32-ID-C.
    
    Attributes
    ----------
    has_permit : bool
      Is the instrument authorized to open shutters and change the
      X-ray source. Could be false for any number of reasons, most
      likely the beamline is set for hutch B to operate.
    use_shutter_A : bool, optional
      Whether shutter A should be used when getting light.
    use_shutter_B : bool, optional
      Whether shutter B should be used when getting light.
    
    """
    zp_diameter = 180
    drn = 60
    gap_offset = 0.17 # Added to undulator gap setting
    pv_queue = None
    ioc_prefix = "32idcPG3:"
    hdf_writer_ready = False
    tiff_writer_ready = False
    pg_external_trigger = True
    shutters_are_open = False
    fast_shutter_enabled = False
    E_RANGE = (6.4, 30) # How far can the X-ray energy be changed (in keV)
    POLL_INTERVAL = 0.01 # How often to check PV's in seconds.
    # Commonly used flags for PVs
    SHUTTER_OPEN = 0
    SHUTTER_CLOSED = 1
    FAST_SHUTTER_CLOSED = 0
    FAST_SHUTTER_OPEN = 1
    FAST_SHUTTER_TRIGGERED = 1
    FAST_SHUTTER_DONE = 0
    FAST_SHUTTER_TRIGGER_MANUAL = 0
    FAST_SHUTTER_TRIGGER_ROTATION = 1
    FAST_SHUTTER_CONTROL_MANUAL = 0
    FAST_SHUTTER_CONTROL_AUTO = 1
    FAST_SHUTTER_RELAY_DIRECT = 0
    FAST_SHUTTER_RELAY_SYNCED = 1
    FAST_SHUTTER_TRIGGER_ENCODER = 1 # TXM Ensemble PSO
    RECURSIVE_FILTER_TYPE = "RecursiveAve"
    CAPTURE_ENABLED = 1
    CAPTURE_DISABLED = 0
    FRAME_DATA = 0
    FRAME_DARK = 1
    FRAME_WHITE = 2
    IMAGE_MODE_MULTIPLE = 'Multiple'
    DETECTOR_IDLE = 0
    DETECTOR_ACQUIRE = 1
    DETECTOR_READOUT = 2
    DETECTOR_CORRECT = 3
    DETECTOR_SAVING = 4
    DETECTOR_ABORTING = 5
    DETECTOR_ERROR = 6
    DETECTOR_WAITING = 7
    DETECTOR_INITIALIZING = 8
    DETECTOR_DISCONNECTED = 9
    DETECTOR_ABORTED = 10
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
    Cam1_NumImagesCounter = TxmPV('{ioc_prefix}cam1:NumImagesCounter_RBV')
    Cam1_Acquire = TxmPV('{ioc_prefix}cam1:Acquire', wait=False)
    Cam1_Display = TxmPV('{ioc_prefix}image1:EnableCallbacks')
    Cam1_Status = TxmPV('{ioc_prefix}cam1:DetectorState_RBV')
    
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
    zone_plate_2_z = TxmPV('32idcTXM:mcs:c2:m3.VAL')
    # MST2 = vertical axis
    # pv.Smaract_mode.put(':MST3,100,500,100')
    Smaract_mode = TxmPV('32idcTXM:mcsAsyn1.AOUT')
    zone_plate_2_x = TxmPV('32idcTXM:mcs:c0:m3.VAL')
    zone_plate_2_y = TxmPV('32idcTXM:mcs:c0:m1.VAL')
    zone_plate_z = TxmPV('32idcTXM:mcs:c0:m2.VAL')
    
    # CCD motors:
    CCD_Motor = TxmPV('32idcTXM:mxv:c1:m6.VAL', float)
    
    # Shutter PV's
    ShutterA_Open = TxmPV('32idb:rshtrA:Open', permit_required=True)
    ShutterA_Close = TxmPV('32idb:rshtrA:Close', permit_required=True)
    ShutterA_Move_Status = TxmPV('PB:32ID:STA_A_FES_CLSD_PL')
    ShutterB_Open = TxmPV('32idb:fbShutter:Open.PROC', permit_required=True)
    ShutterB_Close = TxmPV('32idb:fbShutter:Close.PROC', permit_required=True)
    ShutterB_Move_Status = TxmPV('PB:32ID:STA_B_SBS_CLSD_PL')
    
    # Fast shutter controls
    Fast_Shutter_Open = TxmPV('32idcTXM:shutCam:ShutterManual')
    Fast_Shutter_Delay = TxmPV('32idcTXM:shutCam:tDly')
    Fast_Shutter_Exposure = TxmPV('32idcTXM:shutCam:tExpose')
    Fast_Shutter_Trigger = TxmPV('32idcTXM:shutCam:go', wait=False)
    Fast_Shutter_Trigger_Mode = TxmPV('32idcTXM:shutCam:Triggered')
    Fast_Shutter_Control = TxmPV('32idcTXM:shutCam:ShutterCtrl')
    Fast_Shutter_Relay = TxmPV('32idcTXM:shutCam:Enable')
    Fast_Shutter_Trigger_Source = TxmPV('32idcTXM:flyTriggerSelect')
    
    # Fly scan PV's for nano-ct TXM using Profession Instrument air-bearing stage
    Fly_ScanDelta = TxmPV('32idcTXM:PSOFly3:scanDelta')
    Fly_StartPos = TxmPV('32idcTXM:PSOFly3:startPos')
    Fly_EndPos = TxmPV('32idcTXM:PSOFly3:endPos')
    Fly_SlewSpeed = TxmPV('32idcTXM:PSOFly3:slewSpeed')
    Fly_Taxi = TxmPV('32idcTXM:PSOFly3:taxi')
    Fly_Run = TxmPV('32idcTXM:PSOFly3:fly')
    Fly_ScanControl = TxmPV('32idcTXM:PSOFly3:scanControl')
    Fly_Calc_Projections = TxmPV('32idcTXM:PSOFly3:numTriggers')
    Fly_Set_Encoder_Pos = TxmPV('32idcTXM:eFly:EncoderPos')
    
    # Theta controls
    Reset_Theta = TxmPV('32idcTXM:SG_RdCntr:reset.PROC')
    Proc_Theta = TxmPV('32idcTXM:SG_RdCntr:cVals.PROC')
    Theta_Array = TxmPV('32idcTXM:PSOFly3:motorPos.AVAL')
    # Theta_Array = TxmPV('32idcTXM:eFly:motorPos.AVAL')
    Theta_Cnt = TxmPV('32idcTXM:SG_RdCntr:aSub.VALB')
    
    # Misc PV's
    Image1_Callbacks = TxmPV('{ioc_prefix}image1:EnableCallbacks')
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
    
    def __init__(self, has_permit=False, use_shutter_A=False,
                 use_shutter_B=True):
        self.has_permit = has_permit
        self.use_shutter_A = use_shutter_A
        self.use_shutter_B = use_shutter_B
    
    def pv_get(self, pv_name, *args, **kwargs):
        """Retrieve the current process variable value.
        
        Parameters
        ----------
        args, kwargs
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
        args, kwargs
          Extra arguments that get passed to :py:meth:``epics.PV.get``
        
        """
        if self.pv_queue is not None:
            # Non-blocking, deferred PV waiting
            promise = PVPromise(pv_name=pv_name)
            ret = self._pv_put(pv_name, value, wait=False,
                               callback=promise.complete)
            # Remove any existing promises for this PV
            existing = [p for p in self.pv_queue if p.pv_name == pv_name]
            for old_promise in existing:
                self.pv_queue.remove(old_promise)
            # Add the new promise to the PV queue
            self.pv_queue.append(promise)
        else:
            # Blocking PV waiting
            ret = self._pv_put(pv_name, value, wait=wait, *args, **kwargs)
        return ret
    
    def _pv_put(self, pv_name, value, wait, *args, **kwargs):
        """Retrieves the epics PV and calls its ``put`` method."""
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
        pv_name : str
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
            True if value was set properly.
        
        Raises
        ------
        exceptions_.TimeoutError
            If the PV did not reach the target value before the
            timeout expired.
        
        """
        log_msg = "called wait_pv({name}, {val}, timeout={timeout})"
        log.debug(log_msg.format(name=pv_name, val=target_val,
                                 timeout=timeout))
        # Delay for pv to change
        time.sleep(self.POLL_INTERVAL)
        startTime = time.time()
        # Enter into infinite loop polling the PV status
        while(True):
            real_PV = getattr(type(self), pv_name)
            pv_val = real_PV.__get__(self)
            if (pv_val != target_val):
                if timeout > -1:
                    # Check for timeouts and break out of the loop
                    curTime = time.time()
                    diffTime = curTime - startTime
                    if diffTime >= timeout:
                        msg = ("Timed out '{}' ({}) after {}s"
                               "".format(pv_name, target_val, timeout))
                        warnings.warn(msg, RuntimeWarning)
                        log.warn(msg)
                        break
                time.sleep(0.01)
            else:
                log.debug("Ended wait_pv() after {:.2f} sec."
                          "".format(time.time() - startTime))
                return True
    
    def sample_position(self):
        """Retrieve the x, y, z and theta positions of the sample stage.
        
        Returns
        -------
        position : 4-tuple
          (x, y, z, θ) tuple that is suitable for giving to
          :py:meth:`move_sample`.
        
        """
        Position = namedtuple('Position', ['x', 'y', 'z', 'theta'])
        position = Position(self.Motor_Sample_Top_X,
                            self.Motor_SampleY,
                            self.Motor_Sample_Top_Z,
                            self.Motor_SampleRot)
        return position
    
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
        try:
            msg = msg.format(
                x=self.Motor_Sample_Top_X or 0.,
                y=self.Motor_SampleY or 0.,
                z=self.Motor_Sample_Top_Z or 0.,
                theta=self.Motor_SampleRot or 0.)
        except ValueError:
            # Sometimes incomplete values come back as "None"
            msg = "Sample moved to (x={x}, y={y}, z={z}, θ={theta}°)"
            msg = msg.format(
                x=self.Motor_Sample_Top_X,
                y=self.Motor_SampleY,
                z=self.Motor_Sample_Top_Z,
                theta=self.Motor_SampleRot)
        log.debug(msg)
    
    def energy(self):
        """Get the current beam energy.
        
        Returns
        -------
        energy : float
          Current X-ray energy in keV
        """
        energy = self.DCMputEnergy
        return energy
    
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
            raise exceptions_.EnergyError(
                "Energy {energy} keV not in range {lower} - {upper} keV"
                "".format(energy=energy, lower=self.E_RANGE[0],
                          upper=self.E_RANGE[1]))
        # Get the current values
        old_energy = self.energy()
        old_CCD = self.CCD_Motor
        try:
            old_wavelength = kev_to_nm(old_energy)
            old_ZP_focal = self.zp_diameter * self.drn / (1000.0 * old_wavelength)
            inner = math.sqrt(old_CCD**2 - 4.0 * old_CCD * old_ZP_focal)
            old_D = (old_CCD + inner) / 2.0
            # Calculate target values
            new_wavelength = kev_to_nm(energy)
            new_ZP_focal = self.zp_diameter * self.drn / (1000.0 * new_wavelength)
        except (ValueError, TypeError) as e:
            warnings.warn(str(e), RuntimeWarning)
            return
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
            # self.wait_pv('EnergyWait', 0)
            time.sleep(1)
        self.GAPputEnergy = energy + self.gap_offset
        time.sleep(1)
        self.DCMmvt = old_DCM_mode
        #self.wait_pv('EnergyWait', 0)
        log.debug("Changed energy to %.4f keV (%.4f nm).", energy, new_wavelength)
    
    def enable_fast_shutter(self, rotation_trigger=False, delay=0.02):
        """Enable the hardware-triggered fast shutter.
        
        When this shutter is enabled, actions that capture a
        projection from the CCD will first open the fast shutter, then
        close it again afterwards. With ``rotation_trigger=True``, the
        CCD and shutter are triggered directly by the rotation stage
        (useful for fly scans). This method leaves the shutter closed
        by default.
        
        Parameters
        ----------
        rotation_trigger : bool, optional
          If false (default) the shutter/CCD are controlled by
          software. If true, the rotation stage encoder will trigger
          the shutter/CCD.
        delay : float, optional
          Time (in seconds) to wait for the fast shutter to close.
        
        """
        # Close the shutter to start with
        self.Fast_Shutter_Control = self.FAST_SHUTTER_CONTROL_MANUAL
        self.Fast_Shutter_Open = self.FAST_SHUTTER_CLOSED
        # Determine what trigger the opening/closing of the shutter
        if rotation_trigger:
            # Put the FPGA input under rotary encoder control
            self.Fast_Shutter_Trigger_Mode = self.FAST_SHUTTER_TRIGGER_ROTATION
        else:
            # Put the FPGA input under software control
            self.Fast_Shutter_Trigger_Mode = self.FAST_SHUTTER_TRIGGER_MANUAL
        # Connect the shutter to the FPGA
        self.Fast_Shutter_Control = self.FAST_SHUTTER_CONTROL_AUTO
        # Connect the camera to the fast shutter FPGA
        self.Fast_Shutter_Relay = self.FAST_SHUTTER_RELAY_SYNCED
        # Set the FPGA trigger to the rotary encoder for this TXM
        self.Fast_Shutter_Trigger_Source = self.FAST_SHUTTER_TRIGGER_ENCODER
        # Set the status flag for later use
        self.fast_shutter_enabled = True
        # Set the camera delay
        self.Fast_Shutter_Delay = delay
    
    def disable_fast_shutter(self):
        """Disable the hardware-triggered fast shutter.
        
        This returns the TXM to the conventional software trigger
        mode, with the fast shutter open.
        
        """
        # Connect the trigger to the rotary encoder (to be safe)
        self.Fast_Shutter_Trigger_Mode = self.FAST_SHUTTER_TRIGGER_ROTATION
        # Disconnect the shutter from the FPGA
        self.Fast_Shutter_Control = self.FAST_SHUTTER_CONTROL_MANUAL
        # Connect the camera to the fast shutter FPGA
        self.Fast_Shutter_Relay = self.FAST_SHUTTER_RELAY_DIRECT
        # Set the FPGA trigger to the rotary encoder for this TXM
        self.Fast_Shutter_Trigger_Source = self.FAST_SHUTTER_TRIGGER_ENCODER
        # Set the status flag for later use
        self.fast_shutter_enabled = False
        # Open the shutter so it doesn't interfere with measurements
        self.Fast_Shutter_Open = self.FAST_SHUTTER_OPEN
    
    def open_shutters(self):
        """Open the shutters to allow light in. The specific shutter(s) that
        opens depends on the values of ``self.use_shutter_A`` and
        ``self.use_shutter_B``.
        
        """
        # If not permit enabled, don't do anything
        if not self.has_permit:
            warnings.warn("Shutters not opened because TXM does not have permit",
                          RuntimeWarning)
            return
        # TXM has shutter permit, so open the shutters
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
        if self.use_shutter_A or self.use_shutter_B:
            duration = time.time() - starttime
            log.debug("Opened %s in %.2f sec", which_shutters, duration)
        else:
            warnings.warn("Neither shutter A nor B enabled.")
    
    def close_shutters(self):
        """Close the shutters to stop light in. The specific shutter(s) that
        closes depends on the values of ``self.use_shutter_A`` and
        ``self.use_shutter_B``.
        
        """
        # If not permit enabled, don't do anything
        if not self.has_permit:
            warnings.warn("Shutters not closed because TXM does not have permit",
                          RuntimeWarning)
            return
        # TXM has shutter permit, so open the shutters
        starttime = time.time()
        if self.use_shutter_A:
            log.debug("Closing shutter A")
            self.ShutterA_Close = 1
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
        if self.use_shutter_A or self.use_shutter_B:
            duration = time.time() - starttime
            log.info("Closed %s in %.2f sec", which_shutters, duration)
        else:
            warnings.warn("Neither shutter A nor B enabled.")
    
    @property
    def hdf_filename(self):
        return self.HDF1_FullFileName_RBV
    
    def hdf_file(self, hdf_filename=None, timeout=30, *args, **kwargs):
        # Get current hdf filename
        if hdf_filename is None:
            hdf_filename = self.hdf_filename
        # Wait for the HDF writer to be done using the HDF file
        self.wait_pv('HDF1_Capture_RBV', self.HDF_IDLE, timeout=timeout)
        return h5py.File(self.hdf_filename, *args, **kwargs)
    
    @property
    def exposure_time(self):
        """Exposure time for the CCD in seconds."""
        try:
            current_exposure = max(self.Cam1_AcquireTime, self.Cam1_AcquirePeriod)
        except TypeError:
            current_exposure = None
        return current_exposure
    
    @exposure_time.setter
    def exposure_time(self, val):
        self.Cam1_AcquireTime = val
        self.Cam1_AcquirePeriod = val
        self.Fast_Shutter_Exposure = val
    
    def stop_scan(self):
        log.debug("stop_scan called")
        self.TIFF1_AutoSave = 'No'
        self.TIFF1_Capture = 0
        self.HDF1_Capture = 0
        self.wait_pv('HDF1_Capture', 0)
        self.reset_ccd()
        self.reset_ccd()
        
    def setup_detector(self, exposure=0.5, live_display=True):
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
    
    def _trigger_projections(self, num_projections=1, exposure=None,
                             continued=False):
        """Trigger the detector to capture one (or more) projections.
        
        This method should only be used after setup_detector() and
        setup_hdf_writer() have been called. The value for
        num_projections given here should be less than or equal to the
        number given to each of the setup methods.
        
        Parameters
        ==========
        num_projections : int, optional
          How many projections to trigger.
        exposure : float, optional
          Exposure time, in second. If omitted, the value will be read
          from instrument (takes 10-20 ms)
        continued : bool, optional
          If true, assume that this projection is one in a long series
          that is being handled by some external function (eg
          ``capture_tomogram``)

        """
        if exposure is None:
            exposure = self.exposure_time
        suffix = 's' if num_projections > 1 else ''
        log.debug("Triggering %d projection%s", num_projections, suffix)
        if not continued:
            self.Cam1_ImageMode = "Single"
            self.Cam1_NumImages = 1
        # Collect each frame one at a time
        for i in range(num_projections):
            if self.fast_shutter_enabled:
                # Fast shutter triggering
                self.Fast_Shutter_Trigger = self.FAST_SHUTTER_TRIGGERED
                self.wait_pv('Fast_Shutter_Trigger', self.FAST_SHUTTER_DONE)
            elif self.Cam1_TriggerMode == "Internal":
                # Faster, but less reliable exposure times
                self.Cam1_Acquire = self.DETECTOR_ACQUIRE
                time.sleep(exposure)
            else:
                # Regular external triggering
                if not continued:
                    self.Cam1_Acquire = self.DETECTOR_ACQUIRE
                self.wait_pv('Cam1_Status', self.DETECTOR_WAITING)
                # Wait for the camera to be ready
                old_num = None
                while old_num is None:
                    old_num = self.Cam1_NumImagesCounter
                init_time = time.time()
                self.Cam1_SoftwareTrigger = 1
                self.wait_pv('Cam1_NumImagesCounter', old_num+1)
                log.debug('Captured projection in %f sec', time.time() - init_time)
                # self.wait_pv('Cam1_Status', self.DETECTOR_IDLE)
    
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
    
    def capture_tomogram_flyscan(self, start_angle, end_angle,
                                 num_projections, ccd_readout=0.270):
        """Capture projections over a range of angles using fly-scan mode.
        
        Parameters
        ==========
        start_angle : float
          Starting angle in degrees.
        end_angle : float
          Ending angle in degrees
        num_projections : int
          Number of projections to average at each angle.
        ccd_readout : float, optional
          Time in seconds that it takes for the CCD to read out the
          data.
        
        """
        # Calculate angle parameters
        delta = (end_angle - start_angle) / (num_projections)
        total_time = num_projections * (self.exposure_time + ccd_readout)
        slew_speed = (end_angle - start_angle) / total_time
        # Set values for fly scan parameters
        self.Fly_ScanControl = "Custom"
        self.Fly_ScanDelta = delta
        self.Fly_StartPos = start_angle
        self.Fly_EndPos = end_angle
        self.Fly_SlewSpeed = slew_speed
        # Pause to let the values update
        time.sleep(0.25)
        # Update the value for the number of projections from instrument
        calc_num_proj = math.ceil(self.Fly_Calc_Projections)
        if calc_num_proj is not None:
            num_projections = calc_num_proj
        # Logging
        # Prepare the instrument for scanning
        self.Reset_Theta = 1
        self.Cam1_TriggerMode = 'Overlapped'
        self.Cam1_NumImages = num_projections
        self.Cam1_ImageMode = self.IMAGE_MODE_MULTIPLE
        self.Cam1_Acquire = self.DETECTOR_ACQUIRE
        self.wait_pv('Cam1_Status', self.DETECTOR_WAITING)
        # Execute the fly scan
        theta = []
        self.Cam1_FrameType = self.FRAME_DATA
        self.Fly_Taxi = 1
        self.wait_pv('Fly_Taxi', 0)
        self.Fly_Run = 1
        self.wait_pv('Fly_Run', 0, timeout=-1)
        # Clean up
        self.wait_pv('Cam1_Status', self.DETECTOR_IDLE)
        time.sleep(0.25)
        self.Proc_Theta = 1
        self.Fly_ScanControl = "Standard"
        # Retrieve the actual theta array to return
        pv_name = getattr(type(self), 'Theta_Array').pv_name(txm=self)
        theta = self.pv_get(pv_name, count=int(num_projections))
        if theta is None:
            # No theta array was retrieved, so calculate the angles instead
            warnings.warn("Could not retrieve actual angles, "
                          "storing predicted values instead.")
            theta = np.linspace(start_angle, end_angle, num=num_projections)
        return theta
    
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
        self.Cam1_ImageMode = "Multiple"
        self.Cam1_NumImages = len(angles)
        self.Cam1_Acquire = self.DETECTOR_ACQUIRE
        # self.Cam1_NumImages = 1
        assert num_projections == 1
        if num_projections > 1:
            old_filter = self.Proc1_Filter_Enable
            self.Proc1_Filter_Enable = 'Enable'
        # Configure detector to be more efficient
        exposure = self.exposure_time
        # self.Cam1_TriggerMode = "Internal"
        # Cycle through each angle and collect data
        for sample_rot in tqdm.tqdm(angles, desc="Capturing tomogram", unit='ang'):
            self.move_sample(theta=sample_rot)
            log.debug('Stabilize Sleep: %d ms', stabilize_sleep)
            time.sleep(stabilize_sleep / 1000.)
            # Trigger the camera
            self._trigger_projections(num_projections=num_projections,
                                      exposure=exposure, continued=True)
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
    
    @contextmanager
    def run_scan(self, loggers=(), log_level=None):
        """A context manager for executing long-running scripts. At the end of
        the context, the CCD gets reset and several motor positions
        get restored.
        
        """
        # Setup logging handler
        log_filename = self.hdf_filename
        basename, ext = os.path.splitext(log_filename)
        if log_level is not None:
            handler = logging.FileHandler(filename=basename + '.log')
            handler.setLevel(log_level)
            formatter = logging.Formatter(
                '%(levelname)s:%(pathname)s:%(message)s (%(asctime)s)')
            handler.setFormatter(formatter)
            root_log = logging.getLogger()
            root_log.addHandler(handler)
            root_log.setLevel(log_level)
        now = dt.datetime.now(dt.timezone.utc).astimezone().isoformat()
        log.info("Scan started at %s", now)
        # Save the initial values
        init_position = self.sample_position()
        init_E = self.energy()
        init_exposure = self.exposure_time
        fast_shutter_was_enabled = self.fast_shutter_enabled
        # Return to the inner code block
        try:
            yield
        except Exception as e:
            print("Aborting scan...")
            log.error("Scan finished with exception: %s", str(e))
            raise
        else:
            log.info("Scan finished.")
            # Stop logging
            if log_level is not None:
                root_log.removeHandler(handler)
                handler.close()
        finally:
            log.debug("Restoring previous state")
            # Disable/re-enable the fast shutter
            if fast_shutter_was_enabled:
                self.enable_fast_shutter()
            else:
                self.disable_fast_shutter()
            # Stop TIFF and HDF collection
            self.TIFF1_AutoSave = 'No'
            self.TIFF1_Capture = 0
            self.HDF1_Capture = 0
            self.wait_pv('HDF1_Capture', 0)
            # Restore the saved initial motor positions
            self.move_sample(*init_position)
            # Restore the initial energy if necessary
            if self.energy() != init_E:
                try:
                    self.move_energy(init_E)
                except exceptions_.EnergyError as e:
                    log.warning(e)
            # Close the shutter
            self.close_shutters()
            # Reset the CCD so it's in continuous mode
            self.reset_ccd()
            self.exposure_time = init_exposure
            # Notify the user of that we're done
            log.debug("Finished shutting down")
    
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


class MicroTXM(NanoTXM):
    """TXM operating with the front micro-CT stage."""
    # Common settings for this TXM
    FAST_SHUTTER_TRIGGER_ENCODER = 0 # Hydra encoder
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
