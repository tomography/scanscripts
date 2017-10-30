# -*- coding: utf-8 -*-
'''
Tomography scan for Sector 32 ID C
'''

import sys
import json
import time
import shutil
import os
import imp
import traceback
import signal
import random
import string
import logging

import h5py
from epics import PV
import numpy as np

from aps_32id import NanoTXM
from scanlib import update_variable_dict

__author__ = 'Mark Wolf'
__copyright__ = 'Copyright (c) 2017, UChicago Argonne, LLC.'
__docformat__ = 'restructuredtext en'
__platform__ = 'Unix'
__version__ = '1.6'
__all__ = ['tomo_step_scan']

# Hardcoded values for verifier and TXM
VER_HOST = "txmtwo"
VER_PORT = "5011"
VER_DIR = "/local/usr32idc/conda/data-quality/"
INSTRUMENT = "/home/beams/USR32IDC/.dquality/32id_micro"
IOC_PREFIX = '32idcPG3'
SHUTTER_PERMIT = True

log = logging.getLogger(__name__)

variableDict = {
    'PreDarkImages': 5,
    'PreWhiteImages': 5,
    'Projections': 1281,
    'PostDarkImages': 5,
    'PostWhiteImages': 5,
    'SampleXOut': 12.25,
    # 'SampleYOut': 0.1,
    # 'SampleZOut': 0,
    'SampleRotOut': 0.0,
    'SampleXIn': 0.0,
    # 'SampleYIn': 0.1,
    # 'SampleZIn': 0.0,
    'SampleStart_Rot': -75.,
    'SampleEnd_Rot': 75.,
    'StartSleep_min': 0,
    'StabilizeSleep_ms': 10,
    'ExposureTime_sec': 1.0,
    # 'ShutterOpenDelay': 0.05,
    # 'ExternalShutter': 0,
    # 'FileWriteMode': 'Stream',
    'rot_speed_deg_per_s': 0.5,
    'Recursive_Filter_N_Images': 1,
}


def set_exit_handler(func):
    signal.signal(signal.SIGTERM, func)


def getVariableDict():
    return variableDict


def tomo_step_scan(angles, stabilize_sleep_ms=1., exposure=0.5,
                   has_permit=False,
                   num_white=(5, 5), num_dark=(5, 0),
                   sample_pos=(None,), out_pos=(None,),
                   rot_speed_deg_per_s=0.5, key=None,
                   num_recursive_images=1):
    """Collect a series of projections at multiple angles.
    
    The given angles should span a range of 180°. The frames will be
    stored in an HDF file as determined by the camera and hdf settings
    on the instrument.
    
    Parameters
    ----------
    angles : np.ndarray
      Numpy array with rotation (θ) angles, in degrees, for the
      projections.
    stabilize_sleep_ms : float, optional
      How long to wait, in milliseconds, at each angle for the
      rotation stage to settle.
    exposure : float, optional
      Exposure time in seconds for each projection.
    has_permit : bool, optional
      Whether the user has a priority for the shutters and source.
    num_white : 2-tuple(int), optional
      (pre, post) tuple for number of white field images to collect.
    num_dark : 2-tuple(int), optional
      (pre, post) tuple for number of dark field images to collect.
    sample_pos : 4-tuple(float), optional
      4 (or less) tuple of (x, y, z, θ°) for the sample position.
    out_pos : 4-tuple(float), optional
      4 (or less) tuple of (x, y, z, θ°) for white field position.
    rot_speed_deg_per_s : float, optional
      Angular speed for the rotation stage.
    key : 
      Used for controlling the verifier instance.
    num_recursive_images : int, optional
      Recurisve averaging filter for combining multiple exposures.
    
    """
    # Unpack options
    num_pre_white_images, num_post_white_images = num_white
    num_pre_dark_images, num_post_dark_images = num_dark
    # Some intial debugging
    start_time = time.time()
    log.debug('called start_scan()')
    # # Start verifier on remote machine
    # start_verifier(INSTRUMENT, None, variableDict, VER_DIR, VER_HOST, VER_PORT, key)
    # Prepare X-ray microscope
    txm = NanoTXM(has_permit=has_permit)
    # Prepare the microscope for collecting data
    txm.setup_detector(exposure=exposure)
    total_projections = len(angles)
    total_projections += num_pre_white_images + num_post_white_images
    total_projections += num_pre_dark_images + num_post_dark_images
    txm.setup_hdf_writer(num_projections=total_projections,
                         num_recursive_images=num_recursive_images)
    # Collect pre-scan dark-field images
    if num_pre_dark_images > 0:
        txm.close_shutters()
        txm.capture_dark_field(num_projections=num_pre_dark_images)
    # Collect pre-scan white-field images
    if num_pre_white_images > 0:
        logging.info("Capturing %d white-fields at %s", num_pre_white_images, out_pos)
        # Move the sample out and collect whitefields
        txm.move_sample(theta=out_pos[3]) # So we don't have crashes
        with txm.wait_pvs():
            txm.move_sample(*out_pos)
            txm.open_shutters()
        txm.capture_white_field(num_projections=num_pre_white_images)
    # Capture the actual sample data
    txm.move_sample(theta=0) # So we don't have crashes
    with txm.wait_pvs():
        txm.move_sample(*sample_pos)
        txm.open_shutters()
    log.debug('Starting tomography scan')
    txm.capture_tomogram(angles=angles, num_projections=num_recursive_images,
                         stabilize_sleep=stabilize_sleep_ms)
    # Capture post-scan white-field images
    if num_post_white_images > 0:
        with txm.wait_pvs():
            txm.move_sample(*out_pos)
        txm.capture_white_field(num_projections=num_post_white_images)
    # Capture post-scan dark-field images
    txm.close_shutters()
    if num_post_dark_images > 0:
        txm.capture_dark_field(num_projections=num_post_dark_images)
    # Save metadata
    with txm.hdf_file() as f:
        f.create_dataset('/exchange/theta', data=angles)
    # Clean up
    txm.reset_ccd()
    log.info("Captured %d projections in %d sec.", total_projections, time.time() - start_time)
    return txm


def main():
    # Prepare the exit handler
    key = ''.join(random.choice(string.letters[26:]+string.digits) for _ in range(10))
    def on_exit(sig, func=None):
        cleanup(global_PVs, variableDict, VER_HOST, VER_PORT, key)
        sys.exit(0)
    set_exit_handler(on_exit)
    # Update user settings
    update_variable_dict(variableDict)
    # Extract variables from the global dictionary
    sleep_time = float(variableDict['StartSleep_min']) * 60.0
    num_pre_dark_images = int(variableDict['PreDarkImages'])
    num_post_dark_images = int(variableDict['PostDarkImages'])
    num_dark = (num_pre_dark_images, num_post_dark_images)
    num_pre_white_images = int(variableDict['PreWhiteImages'])
    num_post_white_images = int(variableDict['PostWhiteImages'])
    num_white = (num_pre_white_images, num_post_white_images)
    exposure = float(variableDict['ExposureTime_sec'])
    sample_rot_end = float(variableDict['SampleEnd_Rot'])
    sample_rot_start = float(variableDict['SampleStart_Rot'])
    num_projections = int(variableDict['Projections'])
    rot_speed_deg_per_s = float(variableDict['rot_speed_deg_per_s'])
    angles = np.linspace(sample_rot_start, sample_rot_end, num=num_projections)
    sample_pos = (variableDict.get('SampleXIn', None),
                  variableDict.get('SampleYIn', None),
                  variableDict.get('SampleZIn', None),
                  sample_rot_start)
    out_pos = (variableDict.get('SampleXOut', None),
               variableDict.get('SampleYOut', None),
               variableDict.get('SampleZOut', None),
               variableDict.get('SampleRotOut', None))
    num_recursive_images = int(variableDict['Recursive_Filter_N_Images'])
    step_size = ((sample_rot_end - sample_rot_start) / (num_projections - 1.0))
    stabilize_sleep_ms = float(variableDict['StabilizeSleep_ms'])
    # Pre-scan sleep
    log.debug("Sleeping for %d seconds", int(sleep_time))
    time.sleep(sleep_time)
    # Call the main tomography function
    return tomo_step_scan(angles=angles,
                          stabilize_sleep_ms=stabilize_sleep_ms,
                          exposure=exposure,
                          has_permit=SHUTTER_PERMIT, key=key,
                          num_white=num_white, num_dark=num_dark,
                          sample_pos=sample_pos, out_pos=out_pos,
                          rot_speed_deg_per_s=rot_speed_deg_per_s,
                          num_recursive_images=num_recursive_images)


if __name__ == '__main__':
    # Set up default stream logging
    # Choices are DEBUG, INFO, WARNING, ERROR, CRITICAL
    logfile = '/home/beams/USR32IDC/wolfman/wolfman-devel.log'
    logging.basicConfig(level=logging.DEBUG, filename=logfile)
    logging.captureWarnings(True)
    # Launch the main script portion
    main()
