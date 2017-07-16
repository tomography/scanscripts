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
from tomo_scan_lib import update_variable_dict
from txm import TXM

__author__ = 'Mark Wolf'
__copyright__ = 'Copyright (c) 2017, UChicago Argonne, LLC.'
__docformat__ = 'restructuredtext en'
__platform__ = 'Unix'
__version__ = '1.6'
__all__ = ['energy_scan']

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
    log.debug('start_scan() called')
    start_time = time.time()
    # Stopping the scan in a clean way (currently broken)
    if 'StopTheScan' in variableDict.keys():
        stop_scan(global_PVs, variableDict)
        return
    # Extract scan parameters from the variable dictionary
    exposure = float(variableDict['ExposureTime'])
    n_pre_dark = int(variableDict['PreDarkImages'])
    sleep_min = float(variableDict['StartSleep_min'])
    sample_pos = (variableDict.get('SampleXIn', None),
                  variableDict.get('SampleYIn', None),
                  variableDict.get('SampleZIn', None))
    out_pos = (variableDict.get('SampleXOut', None),
               variableDict.get('SampleYOut', None),
               variableDict.get('SampleZOut', None))
    energy_start = float(variableDict['Energy_Start'])
    energy_end = float(variableDict['Energy_End'])
    energy_step = float(variableDict['Energy_Step'])
    ZP_diameter = float(variableDict['ZP_diameter'])
    offset = float(variableDict['Offset'])
    drn = float(variableDict['drn'])
    StabilizeSleep_ms = float(variableDict['StabilizeSleep_ms'])
    # Start scan sleep in min so min * 60 = sec
    if sleep_min > 0:
        log.debug("Sleeping for %f min", sleep_min)
        time.sleep(sleep_min * 60.0)
    # Prepare TXM for capturing data
    txm.setup_detector()
    txm.setup_hdf_writer()
    # Capture pre dark field images
    if n_pre_dark > 0:
        txm.close_shutters()
        log.info('Capturing %d Pre Dark Field images', n_pre_dark)
        txm.capture_dark_field(num_projections=n_pre_dark, exposure=exposure)
    # Calculate the array of energies that will be scanned
    energies = np.arange(energy_start, energy_end + energy_step, energy_step)
    log.info('Capturing %d energies', len(energies))
    # Collect each energy frame
    for energy in energies:
        log.debug('Preparing to capture energy: %f keV', energy)
        with txm.wait_pvs():
            txm.move_sample(*sample_pos)
            txm.move_energy(energy, gap_offset=offset)
        # Pause for a moment to allow the beam to stabilize
        log.debug('Stabilize Sleep %f ms', StabilizeSleep_ms)
        time.sleep(StabilizeSleep_ms / 1000.0)
        # Sample projection acquisition
        log.info("Acquiring sample position %s at %.4f eV", sample_pos, energy)
        txm.capture_projections(exposure=exposure)
        # Flat-field projection acquisition
        log.debug("Acquiring flat-field position %s at %.4f eV", out_pos, energy)
        with txm.wait_pvs():
            txm.move_sample(*out_pos)
        txm.capture_white_field(exposure=exposure)
    txm.close_shutters()
    # Add the energy array to the active HDF file
    hdf_filename = txm.hdf_filename
    log.debug('Saving energies to file: %s', hdf_filename)
    with h5py.File(hdf_filename) as hdf_f:
        hdf_f.create_dataset('/exchange/energy',
                             (len(energies),),
                             data=energies)
    # Log the duration and output file
    duration = time.time() - start_time
    log.info('Energy scan took %d sec and saved in file %s', duration, hdf_filename)


def main():
    update_variable_dict(variableDict)
    # Create the microscope object
    has_permit = False
    txm = TXM(has_permit=has_permit, is_attached=True,
              ioc_prefix=IOC_PREFIX, use_shutter_A=False,
              use_shutter_B=True)
    # Launch the scan
    energy_scan(txm=txm)


if __name__ == '__main__':
    # Set up default stream logging
    # Choices are DEBUG, INFO, WARNING, ERROR, CRITICAL
    # logging.basicConfig(level=logging.DEBUG)
    logging.basicConfig(level=logging.DEBUG, filename='wolfman-devel.log')
    logging.captureWarnings(True)
    # Enter the main script function
    main()
