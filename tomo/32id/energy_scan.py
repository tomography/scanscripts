#######################
##### To be tested!

'''For each energy step, a projection and then a flat field is being
acquired. The script calls the move_energy method from
the TXM class.

'''

import sys
import json
import time
import shutil
import os
import imp
import traceback
import math
import time
import logging

import numpy as np
import h5py
from epics import PV
# from tomo_scan_lib import *
from txm import TXM

global variableDict
variableDict = {
    'PreDarkImages': 0,
    'SampleXOut': 0.0,
    'SampleYOut': 0.0,
    'SampleXIn': 0.0,
    'SampleYIn': 0.0,
    'StartSleep_min': 0,
    'StabilizeSleep_ms': 1000,
    'ExposureTime': 0.5,
    # 'IOC_Prefix': '32idcPG3:',
    'FileWriteMode': 'Stream',
    'Energy_Start': 6.7,
    'Energy_End': 6.8, # Inclusive
    'Energy_Step': 0.001,
    'ZP_diameter': 180,
    # 'ShutterPermit': 0,
    'drn': 60,
    'constant_mag': 1, # 1 means CCD will move to maintain constant magnification
    'Offset': 0.15,
    # 'BSC_diameter': 1320,
    # 'BSC_drn': 60
}

IOC_PREFIX = '32idcPG3'
SHUTTER_PERMIT = False

log = logging.getLogger(__name__)

global_PVs = {}


def getVariableDict():
    global variableDict
    return variableDict


def energy_scan(txm):
    """Conduct a scan across a range of X-ray energies.
    
    At each energy collect micrographs.

    Returns
    -------
    energy_arr : np.ndarray
      The target energies in keV.
    
    Parameters
    ----------
    txm : TXM
      An instance of the TXM() class.
    """
    log.debug("energy_scan() called.")
    sample_pos = (variableDict.get('SampleXIn', None),
                  variableDict.get('SampleYIn', None),
                  variableDict.get('SampleZIn', None))
    out_pos = (variableDict.get('SampleXOut', None),
               variableDict.get('SampleYOut', None),
               variableDict.get('SampleZOut', None))
    # Extract variables from variableDict:
    Energy_Start = float(variableDict['Energy_Start'])
    Energy_End = float(variableDict['Energy_End'])
    Energy_Step = float(variableDict['Energy_Step'])
    ZP_diameter = float(variableDict['ZP_diameter'])
    offset = float(variableDict['Offset'])
    drn = float(variableDict['drn'])
    exposure = float(variableDict['ExposureTime'])
    StabilizeSleep_ms = float(variableDict['StabilizeSleep_ms'])
    # Prepare the camera and monochromator
    txm.Cam1_NumImages = 1
    txm.DCMmvt = 1
    log.debug("Setting initial energy to %f", Energy_Start)
    log.debug("?? Why do we do this now and again in the loop?")
    txm.GAPputEnergy = Energy_Start
    txm.wait_pv('EnergyWait', 0) # ?? Used to be 0.05
    # Calculate the array of energies that will be scanned
    energies = np.arange(Energy_Start, Energy_End+Energy_Step, Energy_Step)
    log.info('Capturing %d energies', len(energies))
    # Collect each energy frame
    for energy in energies:
        log.debug('Capturing energy: %f keV', energy)
        # Pause for a moment to allow the beam to stabilize
        log.debug('Stabilize Sleep %f ms', StabilizeSleep_ms)
        time.sleep(StabilizeSleep_ms / 1000.0)
        with txm.wait_pvs():
            txm.move_sample(*sample_pos)
            txm.move_energy(energy, gap_offset=offset)
        log.debug('Stabilize Sleep %f ms', StabilizeSleep_ms)
        time.sleep(StabilizeSleep_ms / 1000.0)
     
        # Sample projection acquisition:
        #-------------------------------
        log.info("Acquiring sample position %s at %.4f eV", sample_pos, energy)
        # Prepare datatype for the hdf5 file: next proj will be a sample proj
        txm.capture_projections(exposure=exposure)
        
        # Flat-field projection acquisition:
        #-------------------------------
        log.debug("Acquiring flat-field position %s at %.4f eV", out_pos, energy)
        with txm.wait_pvs():
            txm.move_sample(*out_pos)
        # Prepare datatype for the hdf5 file: next proj will be a flat-field
        txm.Cam1_FrameType = txm.FRAME_WHITE
        # Start detector acquire
        txm.Cam1_Acquire = txm.DETECTOR_ACQUIRE
        # Wait for acquire to finish
        txm.wait_pv('Cam1_Acquire', txm.DETECTOR_IDLE)
        
    txm.DCMmvt = 0
    return energies


def start_scan(txm):
    log.debug('start_scan() called')
    start_time = time.time()
    if 'StopTheScan' in variableDict.keys(): # stopping the scan in a clean way
        stop_scan(global_PVs, variableDict)
        return
    # Extract scan parameters from the variable dictionary
    exposure = float(variableDict['ExposureTime'])
    # Start scan sleep in min so min * 60 = sec
    sleep_min = float(variableDict['StartSleep_min'])
    log.debug("Sleeping for %f min", sleep_min)
    time.sleep(sleep_min * 60.0)
    txm.setup_hdf_writer()
    # Capture pre dark field images
    n_pre_dark = int(variableDict['PreDarkImages'])
    if n_pre_dark > 0:
        txm.close_shutters()
        log.info('Capturing %d Pre Dark Field images', n_pre_dark)
        txm.capture_dark_field(num_projections=n_pre_dark, exposure=exposure)
    sample_pos = (variableDict.get('SampleXIn', None),
                  variableDict.get('SampleYIn', None),
                  variableDict.get('SampleZIn', None))
    txm.move_sample(*sample_pos)
    txm.open_shutters()
    energies = energy_scan(txm)
    # Add the energy array to the active HDF file
    txm.close_shutters()
    log.debug('add_energy_arr() called')
    fullname = txm.HDF1_FullFileName_RBV
    log.debug('Saving energies to file: %s', fullname)
    with h5py.File(fullname) as hdf_f:
        hdf_f.create_dataset('/exchange/energy',
                             (len(energies),),
                             data=energies)
    # Log the duration and output file
    duration = time.time() - start_time
    log.info('Energy scan took %d sec and saved in file %s', duration, fullname)


def main():
    update_variable_dict()
    # Create the microscope object
    has_permit = False # variableDict('ShutterPermit')
    txm = TXM(has_permit=has_permit, is_attached=True,
              ioc_prefix=IOC_PREFIX, use_shutter_A=False,
              use_shutter_B=True)
    # Launch the scan
    start_scan(txm=txm)


if __name__ == '__main__':
    # Set up default stream logging
    # Choices are DEBUG, INFO, WARNING, ERROR, CRITICAL
    logging.basicConfig(level=logging.WARNING)
    logging.captureWarnings(True)
    # Enter the main script function
    main()
