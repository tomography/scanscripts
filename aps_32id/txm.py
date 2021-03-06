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
import six
if six.PY2:
    import ConfigParser as configparser
else:
    import configparser

import numpy as np
import h5py
import tqdm
import pytz
from epics import PV as EpicsPV, get_pv, poll as epics_poll

from scanlib import TxmPV, permit_required, exceptions_, PVMonitor

__author__ = 'Mark Wolf'
__copyright__ = 'Copyright (c) 2017, UChicago Argonne, LLC.'
__docformat__ = 'restructuredtext en'
__platform__ = 'Unix'
__version__ = '1.6'
__all__ = ['NanoTXM',
           'MicroCT',
           'txm_config',]

DEFAULT_TIMEOUT = 20 # PV timeout in seconds
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


log = logging.getLogger(__name__)


class txm_config():
    """A manager for loading values from the configuration file.
    
    Config Variables
    ----------------
    has_permit : bool
      If ``has_permit`` is false, then the script will not attempt to
      change the X-ray source, monochromator, shutters, etc. This
      allows testing of scripts while the B-hutch is operating without
      risking interferance.
    stage : str
      Controls which stage/optics/shutters to use for manipulating the
      sample. "MicroCT" uses the front stage and "NanoTXM" uses the
      rear stage.
    zone_plate_drift_x : float
      How much to move the zone-plate x-coordinate for each unit
      change zone-plate z. If omitted, the value will be pulled from
      the beamline configuration file (``txm_config()``).
    zone_plate_drift_y : float
      How much to move the zone-plate y-coordinate for each unit
      change zone-plate z. If omitted, the value will be pulled from
      the beamline configuration file (``txm_config()``).
    zone_plate_drn : float
      Outer zone width of the zone plate (in nm).
    zone_plate_diameter : float
      Full diameter of the zone plate (in µm).
    
    """
    section = '32-ID-C'
    def __init__(self, filename=os.path.join(ROOT_DIR, 'beamline_config.conf')):
        self.parser = configparser.ConfigParser()
        self.parser.add_section(self.section)
        # Set default values
        self.parser.set(self.section, 'has_permit', 'False')
        self.parser.set(self.section, 'stage', 'NanoTXM')
        self.parser.set(self.section, 'zone_plate_drift_x', '0')
        self.parser.set(self.section, 'zone_plate_drift_y', '0')
        self.parser.set(self.section, 'zone_plate_drn', '60')
        self.parser.set(self.section, 'zone_plate_diameter', '180')
        # Load from the gloabl config file
        self.parser.read(filename)
    
    def __getitem__(self, key):
        return self.get(key)
    
    def get(self, option):
        return self.parser.get(self.section, option)
    
    def getboolean(self, option):
        return self.parser.getboolean(self.section, option)
    
    def getfloat(self, option):
        return self.parser.getfloat(self.section, option)


class PVPromise():
    is_complete = False
    result = None
    
    def __init__(self, pv_name=""):
        self.pv_name = pv_name
    
    def complete(self, pvname="", *args, **kwargs):
        log.debug("Completed pv %s", self.pv_name)
        self.is_complete = True
    
    def __str__(self):
        return self.pv_name


def new_txm(*args, **kwargs):
    """A factory that creates a instrument object, either MicroCT or NanoTXM.
    
    Parameters
    ----------
    args, kwargs : optional
      Arguments that get passed to the constructor of the TXM.
    
    """
    # Check which setup to use
    conf = txm_config()
    instrument = conf['stage']
    log.debug("Loading instrument stage: %s", instrument)
    if instrument == 'NanoTXM':
        txm = NanoTXM(*args, **kwargs)
    elif instrument == 'MicroCT':
        txm = MicroCT(*args, **kwargs)
    else:
        msg = "Unknown value for '32-ID-C.stage': %s"
        msg += "Options are ('NanoTXM', 'MicroCT')"
        raise exceptions_.ConfigurationError(msg % instrument)
    return txm


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
    
    """
    gap_offset = 0.17 # Added to undulator gap setting
    pv_queue = None
    ioc_prefix = "32idcPG3:"
    hdf_writer_ready = False
    tiff_writer_ready = False
    pg_external_trigger = True
    use_shutter_A = False
    use_shutter_B = True
    shutters_are_open = False
    fast_shutter_enabled = False
    E_RANGE = (6.4, 30) # How far can the X-ray energy be changed (in keV)
    POLL_INTERVAL = 0.01 # How often to check PV's in seconds.
    # XML file values to use
    detector_xml = "nctDetectorAttributes.xml"
    hdf_xml = "nct.xml"
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
    UNIBLITZ_CLOSED = 0
    UNIBLITZ_OPEN = 1
    RECURSIVE_FILTER_TYPE = "RecursiveAve"
    CAPTURE_ENABLED = 1
    CAPTURE_DISABLED = 0
    CALLBACK_DISABLED = 'Disable'
    CALLBACK_ENABLED = 'Enable'
    FRAME_DATA = 0
    FRAME_DARK = 1
    FRAME_WHITE = 2
    IMAGE_MODE_SINGLE = 'Single'
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
    TRIGGER_INTERNAL = 'Internal'
    TRIGGER_EXTERNAL = 'Ext. Standard'
    TRIGGER_OVERLAPPED = 'Overlapped'
    GPIO_0 = 0
    GPIO_2 = 1
    GPIO_3 = 2
    SHAKER_STOP = 0
    SHAKER_RUN = 1
    
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
    Cam1_TriggerSource = TxmPV('{ioc_prefix}cam1:TriggerSource')
    Cam1_SoftwareTrigger = TxmPV('{ioc_prefix}cam1:SoftwareTrigger', wait=False)
    Cam1_AcquireTime = TxmPV('{ioc_prefix}cam1:AcquireTime')
    Cam1_FrameRateOnOff = TxmPV('{ioc_prefix}cam1:FrameRateOnOff')
    Cam1_FrameType = TxmPV('{ioc_prefix}cam1:FrameType')
    Cam1_NumImages = TxmPV('{ioc_prefix}cam1:NumImages')
    Cam1_NumImagesCounter = TxmPV('{ioc_prefix}cam1:NumImagesCounter_RBV')
    Cam1_Acquire = TxmPV('{ioc_prefix}cam1:Acquire', wait=False)
    Cam1_Display = TxmPV('{ioc_prefix}image1:EnableCallbacks')
    Cam1_Status = TxmPV('{ioc_prefix}cam1:DetectorState_RBV')
    Cam1_XMLFile = TxmPV('{ioc_prefix}cam1:NDAttributesFile')
    
    # HDF5 writer PV's
    HDF1_LazyOpen = TxmPV('{ioc_prefix}HDF1:LazyOpen')
    HDF1_AutoSave = TxmPV('{ioc_prefix}HDF1:AutoSave')
    HDF1_DeleteDriverFile = TxmPV('{ioc_prefix}HDF1:DeleteDriverFile')
    HDF1_EnableCallbacks = TxmPV('{ioc_prefix}HDF1:EnableCallbacks')
    HDF1_BlockingCallbacks = TxmPV('{ioc_prefix}HDF1:BlockingCallbacks')
    HDF1_FileWriteMode = TxmPV('{ioc_prefix}HDF1:FileWriteMode')
    HDF1_NumCapture = TxmPV('{ioc_prefix}HDF1:NumCapture')
    HDF1_NumCapture_RBV = TxmPV('{ioc_prefix}HDF1:NumCapture_RBV')
    HDF1_Capture = TxmPV('{ioc_prefix}HDF1:Capture', wait=False)
    HDF1_Capture_RBV = TxmPV('{ioc_prefix}HDF1:Capture_RBV')
    HDF1_WriteFile_RBV = TxmPV('{ioc_prefix}HDF1:WriteFile_RBV')
    HDF1_FileName = TxmPV('{ioc_prefix}HDF1:FileName', dtype=str,
                          as_string=True)
    HDF1_FullFileName_RBV = TxmPV('{ioc_prefix}HDF1:FullFileName_RBV',
                                  dtype=str, as_string=True)
    HDF1_FileTemplate = TxmPV('{ioc_prefix}HDF1:FileTemplate')
    HDF1_ArrayPort = TxmPV('{ioc_prefix}HDF1:NDArrayPort')
    HDF1_NextFile = TxmPV('{ioc_prefix}HDF1:FileNumber')
    HDF1_XMLFile = TxmPV('{ioc_prefix}HDF1:XMLFileName')
    
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
    Motor_SampleRot_Speed = TxmPV('32idcTXM:ens:c1:m1.VELO', dtype=float)
    Motor_SampleRot_Stop = TxmPV('32idcTXM:ens:c1:m1.STOP', wait=False)
    # Smaract XZ TXM set
    Motor_Sample_Top_X = TxmPV('32idcTXM:mcs:c3:m7.VAL', dtype=float)
    Motor_Sample_Top_Z = TxmPV('32idcTXM:mcs:c3:m8.VAL', dtype=float)
    # # Mosaic scanning axes
    # Motor_X_Tile = TxmPV('32idc01:m33.VAL')
    # Motor_Y_Tile = TxmPV('32idc02:m15.VAL')
    
    # Zone plate:
    zone_plate_x = TxmPV('32idcTXM:mcs:c2:m1.VAL')
    zone_plate_y = TxmPV('32idcTXM:mcs:c2:m2.VAL')
    zone_plate_z = TxmPV('32idcTXM:mcs:c2:m3.VAL')
    
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
    Softglue_Shutter = TxmPV('32idcTXM:SG3:DnCntr-1_PRESET') # Should be always 1
    Fast_Shutter_Delay = TxmPV('32idcTXM:shutCam:tDly')
    Fast_Shutter_Exposure = TxmPV('32idcTXM:shutCam:tExpose')
    Fast_Shutter_Trigger = TxmPV('32idcTXM:shutCam:go', wait=False)
    Fast_Shutter_Trigger_Mode = TxmPV('32idcTXM:shutCam:Triggered') # Manual / Triggered synchronization
    Fast_Shutter_Control = TxmPV('32idcTXM:shutCam:ShutterCtrl') # Shutter control: manual or Auto
    Fast_Shutter_Relay = TxmPV('32idcTXM:shutCam:Enable')
    Fast_Shutter_Trigger_Source = TxmPV('32idcTXM:flyTriggerSelect')
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
    Fly_Set_Encoder_Pos = TxmPV('32idcTXM:eFly:EncoderPos')
    
    # Theta controls
    Reset_Theta = TxmPV('32idcTXM:SG_RdCntr:reset.PROC')
    Proc_Theta = TxmPV('32idcTXM:SG_RdCntr:cVals.PROC')
    Theta_Array = TxmPV('32idcTXM:PSOFly3:motorPos.AVAL')
    # Theta_Array = TxmPV('32idcTXM:eFly:motorPos.AVAL')
    Theta_Cnt = TxmPV('32idcTXM:SG_RdCntr:aSub.VALB')
    
    # Misc PV's
    Image1_Callbacks = TxmPV('{ioc_prefix}image1:EnableCallbacks')
    Shaker = TxmPV('32idcMC:shaker:run')
    # SetSoftGlueForStep = TxmPV('32idcTXM:SG3:MUX2-1_SEL_Signal')
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
    
    def __init__(self, has_permit=None):
        config = txm_config()
        if has_permit is None:
            # Load default permit value from config file
            self.has_permit = config.getboolean('has_permit')
        else:
            self.has_permit = has_permit
        # Load beamline configuration from file
        self.zone_plate_drift_x = config.getfloat('zone_plate_drift_x')
        self.zone_plate_drift_y = config.getfloat('zone_plate_drift_y')
        self.drn = config.getfloat('zone_plate_drn')
        self.zp_diameter = config.getfloat('zone_plate_diameter')
    
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
        # Track some performance values
        start_time = time.time()
        num_promises = len(self.pv_queue)
        pv_times = {str(pv): 0 for pv in self.pv_queue}
        # Wait for all the PVs to be finished
        while block and not all([pv.is_complete for pv in self.pv_queue]):
            # Update the timing trackers
            time_diff = time.time() - start_time
            new_times = {str(pv): time_diff for pv in self.pv_queue if not pv.is_complete}
            pv_times.update(new_times)
            time.sleep(0.01)
        log.debug("Completed %d queued PV's: %s", num_promises, pv_times)
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
        
        """
        log_msg = "called wait_pv({name}, {val}, timeout={timeout})"
        log.debug(log_msg.format(name=pv_name, val=target_val,
                                 timeout=timeout))
        # Delay for pv to change
        # time.sleep(self.POLL_INTERVAL)
        startTime = time.time()
        # Enter into infinite loop polling the PV status
        real_PV = getattr(type(self), pv_name)
        pv_name = real_PV.pv_name(self)
        with PVMonitor(pv_name) as mon:
            while(True):
                if (mon.latest_value != target_val):
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
                    epics_poll()
                else:
                    log.debug("Ended wait_pv({}) after {:.2f} sec."
                              "".format(pv_name, time.time() - startTime))
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
            self.Motor_SampleRot = float(theta)
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
        # System hangs if you try and set to the already current energy
        if energy == self.energy():
            log.warning("Already at %f keV. Not changing.", energy)
            return
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
        # Calculate zoneplate x and y based on skew
        delta_z = (ZP_WD - self.zone_plate_z)
        new_x = self.zone_plate_x + delta_z * self.zone_plate_drift_x
        new_y = self.zone_plate_y + delta_z * self.zone_plate_drift_y
        # Move the zoneplate
        log.debug("New zoneplate position: (%.5f, %.5f, %.5f)", new_x, new_y, ZP_WD)
        self.zone_plate_x = new_x
        self.zone_plate_y = new_y
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
        # Make sure Softglue circuit is configure correctly:
        self.Softglue_Shutter = 1
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
        # Disable the "uniblitz" fast shutter safety
        self.Fast_Shutter_Uniblitz = self.UNIBLITZ_CLOSED
    
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
            self.wait_pv('ShutterA_Move_Status', self.SHUTTER_OPEN, timeout=5)
        if self.use_shutter_B:
            log.debug("Opening shutter B")
            self.ShutterB_Open = 1
            self.wait_pv('ShutterB_Move_Status', self.SHUTTER_OPEN, timeout=5)
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
    
    def setup_detector(self, num_projections, exposure=0.5):
        """Prepare the Poing-Grey detector to start collecting projections.
        
        Parameters
        ----------
        num_projections : int
          Total number of projections expected during the
          experiment. After this number is reach, the detector the
          become idle.
        exposure : float, optional
          How long (in sec) to collect each exposure for.
        
        """
        log.debug("Setting up detector for %d (%f s) projections.",
                  num_projections, exposure)
        # Load the correct xml attributes
        self.Cam1_XMLFile = self.detector_xml
        # Capture a dummy frame to that the HDF5 plugin will work
        self.HDF1_EnableCallbacks = self.CALLBACK_DISABLED
        self.Cam1_ImageMode = self.IMAGE_MODE_SINGLE
        self.Cam1_TriggerMode = self.TRIGGER_INTERNAL
        self.exposure_time = 0.01
        self.Cam1_Acquire = self.DETECTOR_ACQUIRE
        self.wait_pv('Cam1_Acquire', self.DETECTOR_IDLE)
        self.HDF1_EnableCallbacks = self.CALLBACK_ENABLED
        # Now set the real settings for the detector
        self.Cam1_ImageMode = self.IMAGE_MODE_MULTIPLE
        self.Cam1_Display = True
        self.Cam1_ArrayCallbacks = 'Enable'
        self.Cam1_FrameRateOnOff = False
        self.Cam1_TriggerSource = self.GPIO_0
        self.Cam1_TriggerMode = self.TRIGGER_EXTERNAL
        # Now enable the detector for acquisition
        self.start_detector(num_projections=num_projections, exposure=exposure)
        # log.debug("Finished setting up detector.")
    
    def start_detector(self, num_projections=1, exposure=None):
        """Starts the detector for however many projections are requested.
        
        This does not change the imaging mode or the trigger setup,
        use :py:meth:`setup_detector` for this.
        
        Parameters
        ----------
        num_projections : int, optional
          How many projections to expect for this round of capture.
        exposure : float, optional
          How long to capture each projection for. If ``None``
          (default), the current exposure time will be used.
        
        """
        self.Cam1_NumImages = num_projections
        # Set exposure
        if exposure is not None:
            self.exposure_time = exposure
        # Make sure the detector is ready for triggering
        self.Cam1_Acquire = self.DETECTOR_ACQUIRE
        self.wait_pv('Cam1_Status', self.DETECTOR_WAITING)        
    
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
        self.HDF1_LazyOpen = 0 # has to be 0 (for some reasons...)
        # Load the correct XML attributes
        self.HDF1_XMLFile = self.hdf_xml
        # Enable recursive filter        
        if num_recursive_images > 1:
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
        self.wait_pv('HDF1_Capture_RBV', self.CAPTURE_ENABLED)
        # Clean up and set some status variables
        try:
            log.debug("Finished setting up HDF writer for %s.", self.HDF1_FullFileName_RBV)
        except:
            pass
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
    
    def _trigger_projection(self):
        """Trigger the detector to capture one projection.
        
        This method should only be used after setup_detector() and
        setup_hdf_writer() have been called.
        
        """
        log.debug("Triggering projection")
        # Retrieve current image counter
        old_num = None
        init_time = time.time()
        while old_num is None:
            old_num = self.Cam1_NumImagesCounter
        # Collect each frame one at a time
        if self.fast_shutter_enabled:
            # Fast shutter triggering
            #self.wait_pv('Cam1_Status', self.DETECTOR_WAITING) # Not needed since we acquire multiple mode
            self.Fast_Shutter_Trigger = self.FAST_SHUTTER_TRIGGERED
            # self.wait_pv('Fast_Shutter_Trigger', self.FAST_SHUTTER_DONE)
        else:
            # Regular external triggering
            #self.wait_pv('Cam1_Status', self.DETECTOR_WAITING) # Not needed since we acquire multiple mode
            # Wait for the camera to be ready
            self.Cam1_SoftwareTrigger = 1
        # Make sure that the projection is done collecting
        self.wait_pv('Cam1_NumImagesCounter', old_num+1)
        log.debug('Captured projection in %f sec', time.time() - init_time)
    
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
        log.debug('Capturing %d projection images', num_projections)
        for i in range(num_projections):
            self._trigger_projection()
    
    def capture_white_field(self, num_projections=1):
        """Trigger the capturing of projection images from the detector with
        the shutters open and no sample present.
        
        This method does NOT actually open the shutters or move the
        sample: these things must be done prior to calling this
        method.
        
        Parameters
        ----------
        num_projections : int, optional
          How many projections to acquire.
        
        """
        # Raise a warning if the shutters are closed.
        if not self.shutters_are_open:
            msg = "Collecting white field with shutters closed."
            warnings.warn(msg, RuntimeWarning)
            log.warning(msg)
        self.Cam1_FrameType = self.FRAME_WHITE
        # Collect the data
        log.debug('Capturing %d flat-field images', num_projections)
        for i in range(num_projections):
            self._trigger_projection()
    
    def capture_dark_field(self, num_projections=1):
        """Trigger the capturing of projection images from the detector with
        the shutters closed.
        
        The shutter should be closed before calling this method.
        
        Parameters
        ----------
        num_projections : int, optional
          How many projections to acquire.
        
        """
        # Raise a warning if the shutters are open.
        if self.shutters_are_open:
            msg = "Collecting dark field with shutters open."
            warnings.warn(msg, RuntimeWarning)
            log.warning(msg)
        self.Cam1_FrameType = self.FRAME_DARK
        # Collect the data
        log.debug('Capturing %d flat-field images', num_projections)
        for i in range(num_projections):
            self._trigger_projection()
    
    def stop_fly_scan(self):
        """Abort and actively running fly scan.
        
        Even if the script is stopped, the motors continue
        turning. This method stops the rotation and restores the
        original speed.
        
        """
        log.debug("Stopping fly scan motors.")
        self.Motor_SampleRot_Stop = 1
        self.Motor_SampleRot_Speed = 40
    
    def capture_tomogram_flyscan(self, start_angle, end_angle,
                                 num_projections, ccd_readout=0.270,
                                 extra_projections=0):
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
        time.sleep(3)
        # Update the value for the number of projections from instrument
        extra_projections = self.HDF1_NumCapture_RBV - num_projections
        log.debug('Acquiring %d extra projections (flat/dark)', extra_projections)
        calc_num_proj = math.ceil(self.Fly_Calc_Projections)
        if calc_num_proj is not None:
            num_projections = calc_num_proj
            log.debug('Fly scan resetting num_projections to %d (%d)',
                      num_projections, extra_projections)
        # Logging
        # Prepare the instrument for scanning
        self.Reset_Theta = 1
        self.Cam1_TriggerMode = 'Overlapped'
        self.Cam1_NumImages = num_projections
        self.HDF1_NumCapture = num_projections + extra_projections
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
    
    def capture_tomogram(self, angles, stabilize_sleep=10):
        """Collect data frames over a range of angles.
        
        Parameters
        ==========
        angles : np.ndarray
          An array of angles (in degrees) to use for collecting
          projections.
        stablize_sleep : int, optional
          How long (in milliseconds) to wait after moving the rotation
          stage.
        
        """
        log.warning("capture_tomogram() not tested")
        log.debug('called tomo_scan()')
        # Prepare the instrument for data collection
        self.Cam1_FrameType = self.FRAME_DATA
        # Configure detector to be more efficient
        exposure = self.exposure_time
        # Cycle through each angle and collect data
        for sample_rot in tqdm.tqdm(angles, desc="Capturing tomogram", unit='ang'):
            self.move_sample(theta=sample_rot)
            log.debug('Stabilize Sleep: %d ms', stabilize_sleep)
            time.sleep(stabilize_sleep / 1000.)
            # Trigger the camera
            self._trigger_projection()
    
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
    
    def start_logging(self, level=logging.NOTSET):
        """Open a handler for logging TXM actions and add it to root logger.
        
        If the HDF plugin has been started, logs will be sent to a
        matching file. Otherwise, logs will be sent to stderr since we
        can't know the HDF filename before it's been set.
        
        This method works best when called inside a ``run_scan()``
        context manager, so the changes get undone once the scan is
        finished.
        
        Parameters
        ----------
        level : int, optional
          Logging level to use for creating the logging.Handler
          object. If None or -1, nothing happens.
        
        Returns
        -------
        handler
          The new logging handler that was added to the root logger.
        
        """
        # Check for poison pill values to not start logging
        if (level is None) or (level < logging.NOTSET):
            log.debug('Logging not started (%s)' % level)
            return
        # Setup logging handler
        if self.HDF1_Capture_RBV == self.HDF_WRITING:
            basename, ext = os.path.splitext(self.hdf_filename)
            handler = logging.FileHandler(filename=basename + '.log')
        else:
            handler = logging.StreamHandler()
            warnings.warn('HDF writer not yet running, logging sent to stderr.'
                          ' Consider calling Txm().``setup_hdf_writer``'
                          ' outside run_scan block')
        handler.setLevel(int(level))
        formatter = logging.Formatter(
            '%(levelname)s:%(name)s:%(message)s (%(asctime)s)')
        handler.setFormatter(formatter)
        root_log = logging.getLogger()
        root_log.addHandler(handler)
        # Make sure the root logger will actually emit the requested level
        if level:
            root_log.setLevel(min(level, root_log.level))
        # Save a timestamp to the logger
        try:
            now = dt.datetime.now(pytz.utc).astimezone()
        except TypeError:
            local_tz = pytz.timezone('America/Chicago')
            warnings.warn("Cannot detect local timezone, assuming %s."
                          " Are you still using python 2?" % str(local_tz))
            now = dt.datetime.now(pytz.utc).astimezone(local_tz)
        log.info("Log started at %s", now.isoformat())
        return handler
    
    @contextmanager
    def run_scan(self):
        """A context manager for executing long-running scripts. At the end of
        the context, the CCD gets reset, several motor positions get
        restored, and extra logging handlers get removed.
        
        """
        # Save logging info for later
        root_logger = logging.getLogger()
        old_log_level = root_logger.level
        old_handlers = tuple(root_logger.handlers)
        # Save the initial values
        init_position = self.sample_position()
        init_E = self.energy()
        init_exposure = self.exposure_time
        fast_shutter_was_enabled = self.fast_shutter_enabled
        uniblitz_status = self.Fast_Shutter_Uniblitz
        # Return to the inner code block
        try:
            yield
        except Exception as e:
            print("Aborting scan...")
            log.error("Scan finished with exception: %s", str(e))
            raise
        else:
            log.info("Scan finished.")
        finally:
            log.debug("Restoring previous state")
            self.stop_fly_scan()
            # Close the shutter
            self.close_shutters()
            # Disable/re-enable the fast shutter
            self.Fast_Shutter_Uniblitz = uniblitz_status
            if fast_shutter_was_enabled:
                self.enable_fast_shutter()
            else:
                self.disable_fast_shutter()
            # Stop TIFF and HDF collection
            self.TIFF1_AutoSave = 'No'
            self.TIFF1_Capture = 0
            self.HDF1_Capture = 0
            self.wait_pv('HDF1_WriteFile_RBV', self.HDF_IDLE)
            # Restore the saved initial motor positions
            self.move_sample(*init_position)
            # Restore the initial energy if necessary
            if self.energy() != init_E:
                try:
                    self.move_energy(init_E)
                except exceptions_.EnergyError as e:
                    log.warning(e)
            # Reset the CCD so it's in continuous mode
            self.reset_ccd()
            self.exposure_time = init_exposure
            # Notify the user that we're done
            log.debug("Finished shutting down")
            # Restore original logging
            root_logger.setLevel(old_log_level)
            # Remove any added logging handlers
            for hndlr in root_logger.handlers:
                if hndlr not in old_handlers:
                    root_logger.removeHandler(hndlr)
    
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


class MicroCT(NanoTXM):
    """TXM operating with the front micro-CT stage."""
    # Common settings for this micro-CT
    FAST_SHUTTER_TRIGGER_ENCODER = 0 # Hydra encoder
    use_shutter_A = True
    use_shutter_B = False
    # XML file values to use
    detector_xml = "mctDetectorAttributes.xml"
    hdf_xml = "mct.xml"
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
