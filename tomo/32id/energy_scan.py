# -*- coding: utf-8 -*-
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
import tqdm
from epics import PV
from tomo_scan_lib import update_variable_dict
from txm import TXM

# global variableDict
variableDict = {
    'PreDarkImages': 0,
    'SampleXOut': 0.0,
    # 'SampleYOut': 0.0,
    'SampleXIn': 0.0,
    # 'SampleYIn': 0.0,
    'StartSleep_min': 0,
    'StabilizeSleep_ms': 1000,
    'ExposureTime': 0.5,
    'FileWriteMode': 'Stream',
    'Energy_Start': 6.7,
    'Energy_End': 6.8, # Inclusive
    'Energy_Step': 0.001,
    # 'ZP_diameter': 180,
    # 'drn': 60,
    'constant_mag': True, # 1 means CCD will move to maintain constant magnification
    # 'BSC_diameter': 1320,
    # 'BSC_drn': 60
    'Recursive_Filter_N_Images': 1,
}

IOC_PREFIX = '32idcPG3:'
SHUTTER_PERMIT = True
DEFAULT_ENERGIES = np.arange(
    variableDict['Energy_Start'],
    variableDict['Energy_End'] + variableDict['Energy_Step'],
    variableDict['Energy_Step'],
)

log = logging.getLogger(__name__)


def getVariableDict():
    # global variableDict
    return variableDict


def energy_scan(energies, exposure=0.5, n_pre_dark=5,
                is_attached=True, has_permit=False,
                sample_pos=(None,), out_pos=(None,),
                constant_mag=True, stabilize_sleep_ms=1000,
                num_recursive_images=1):
    """Collect a series of 2-dimensional projections across a range of energies.

    At each position, a sample projection and white-field projection
    will be collected by moving the sample along the X direction.

    Parameters
    ----------
    energies : np.ndarray
      An array with the list of energies to scan, in keV.
    exposure : float, optional
      How long to collect each frame for, in seconds.
    n_pre_dark : int, optional
      How many dark-field projections to collect before starting the
      energy scan.
    is_attached : bool, optional
      Determines whether the instrument is available.
    has_permit : bool, optional
      Does the user have permission to open the shutters and change
      source energy.
    sample_pos : 4-tuple, optional
      (x, y, z, θ) tuple for positioning the sample in the beam.
    out_pos : 4-tuple, optional
      (x, y, z, θ) tuple for removing the sample from the beam.
    constant_mag : bool, optional
      Whether to adjust the camera position to maintain a constant
      focus.
    stabilize_sleep_ms : int, optional
      How long, in milliseconds, to wait for the beam to stabilize
      before collecting projections.
    num_recursive_images: int, optional
      If greater than 1, several consecutive images can be collected.
    """
    log.debug('start_scan() called')
    start_time = time.time()
    # Create the TXM object for this scan
    txm = TXM(is_attached=is_attached, has_permit=has_permit,
              ioc_prefix=IOC_PREFIX, use_shutter_A=False,
              use_shutter_B=True)
    # Prepare TXM for capturing data
    txm.setup_detector(exposure=exposure)
    total_projections = n_pre_dark + 2 * len(energies)
    txm.setup_hdf_writer(num_projections=total_projections,
                         num_recursive_images=num_recursive_images)
    # Capture pre dark field images
    if n_pre_dark > 0:
        txm.close_shutters()
        log.info('Capturing %d Pre Dark Field images', n_pre_dark)
        txm.capture_dark_field(num_projections=n_pre_dark * num_recursive_images)
    # Calculate the array of energies that will be scanned
    log.info('Capturing %d energies', len(energies))
    # Collect each energy frame
    txm.open_shutters()
    correct_backlash = True # First energy only
    for idx, energy in enumerate(tqdm.tqdm(energies, "Energy scan")):
        log.debug('Preparing to capture energy: %f keV', energy)
        # Check whether we should collect the sample or white field first 
        sample_first = not bool(idx % 2)
        log.info("Collecting %s first.", "sample" if sample_first else "white-field")
        # Move sample and energy
        # with txm.wait_pvs():
        if sample_first:
            txm.move_sample(*sample_pos)
        else:
            txm.move_sample(*out_pos)
        txm.move_energy(energy, constant_mag=constant_mag,
                        correct_backlash=correct_backlash)
        correct_backlash = False # Needed on first energy only
        # Pause for a moment to allow the beam to stabilize
        log.debug('Stabilize Sleep %f ms', stabilize_sleep_ms)
        time.sleep(stabilize_sleep_ms / 1000.0)
        # Sample projection acquisition (or white-field on odd passes)
        if sample_first:
            log.info("Acquiring sample position %s at %.4f eV", sample_pos, energy)
            txm.capture_projections(num_projections=num_recursive_images)
        else:
            log.info("Acquiring white-field position %s at %.4f eV", out_pos, energy)
            txm.capture_white_field(num_projections=num_recursive_images)
        # Flat-field projection acquisition (or sample on odd passes)
        if sample_first:
            with txm.wait_pvs():
                txm.move_sample(*out_pos)
            log.info("Acquiring white-field position %s at %.4f eV", out_pos, energy)
            txm.capture_white_field(num_projections=num_recursive_images)
        else:
            with txm.wait_pvs():
                txm.move_sample(*sample_pos)
            log.info("Acquiring sample position %s at %.4f eV", sample_pos, energy)
            txm.capture_projections(num_projections=num_recursive_images)
    txm.close_shutters()
    # Add the energy array to the active HDF file
    with txm.hdf_file(mode="r+") as hdf_f:
        log.debug('Saving energies to file: %s', txm.hdf_filename)
        hdf_f.create_dataset('/exchange/energy',
                             data=energies)
    # Log the duration and output file
    duration = time.time() - start_time
    log.info('Energy scan took %d sec and saved in file %s', duration, txm.hdf_filename)
    return txm


def main():
    update_variable_dict(variableDict)
    # Get the requested sample positions
    sample_pos = (variableDict.get('SampleXIn', None),
                  variableDict.get('SampleYIn', None),
                  variableDict.get('SampleZIn', None))
    out_pos = (variableDict.get('SampleXOut', None),
               variableDict.get('SampleYOut', None),
               variableDict.get('SampleZOut', None))
    # Prepare the list of energies requested
    energy_start = float(variableDict['Energy_Start'])
    energy_end = float(variableDict['Energy_End'])
    energy_step = float(variableDict['Energy_Step'])
    energies = np.arange(energy_start, energy_end + energy_step, energy_step)
    # Start scan sleep in min so min * 60 = sec
    sleep_min = float(variableDict.get('StartSleep_min', 0))
    stabilize_sleep_ms = float(variableDict.get("StabilizeSleep_ms"))
    num_recursive_images = int(variableDict['Recursive_Filter_N_Images'])
    constant_mag = bool(variableDict['constant_mag'])
    if sleep_min > 0:
        log.debug("Sleeping for %f min", sleep_min)
        time.sleep(sleep_min * 60.0)
    # Start the energy scan
    energy_scan(energies=energies,
                is_attached=True, has_permit=SHUTTER_PERMIT,
                exposure=float(variableDict['ExposureTime']),
                n_pre_dark=int(variableDict['PreDarkImages']),
                sample_pos=sample_pos, out_pos=out_pos,
                stabilize_sleep_ms=stabilize_sleep_ms,
                constant_mag=constant_mag,
                num_recursive_images=num_recursive_images)


if __name__ == '__main__':
    # Set up default stream logging
    # Choices are DEBUG, INFO, WARNING, ERROR, CRITICAL
    # logging.basicConfig(level=logging.DEBUG)
    logfile = '/home/beams/USR32IDC/wolfman/wolfman-devel.log'
    logging.basicConfig(level=logging.DEBUG, filename=logfile)
    logging.captureWarnings(True)
    # Enter the main script function
    main()
