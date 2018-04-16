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
import warnings

import h5py
from epics import PV
import numpy as np

# from aps_32id import MicroCT as TXM
from aps_32id import NanoTXM, new_txm
from scanlib import update_variable_dict, tools

__author__ = 'Mark Wolfman'
__copyright__ = 'Copyright (c) 2017, UChicago Argonne, LLC.'
__docformat__ = 'restructuredtext en'
__platform__ = 'Unix'
__version__ = '1.6'
__all__ = ['run_tomo_step_scan', 'getVariableDict']

# Hardcoded values for verifier and TXM
VER_HOST = "txmtwo"
VER_PORT = "5011"
VER_DIR = "/local/usr32idc/conda/data-quality/"
INSTRUMENT = "/home/beams/USR32IDC/.dquality/32id_micro"
IOC_PREFIX = '32idcPG3'

log = logging.getLogger(__name__)

variableDict = {
    'PreDarkImages': 5,
    'PreWhiteImages': 10,
    'Projections': 721,
    'PostDarkImages': 5,
    'PostWhiteImages': 10,
    'SampleXOut': 0.2,
    # 'SampleYOut': 0.1,
    # 'SampleZOut': 0,
    'SampleRotOut': 0.0,
    'SampleXIn': 0.0,
    # 'SampleYIn': 0.1,
    # 'SampleZIn': 0.0,
    'SampleStart_Rot': 0.,
    'SampleEnd_Rot': 180.,
    'StartSleep_min': 0,
    'StabilizeSleep_ms': 10,
    'ExposureTime_sec': 1.0,
    # 'ShutterOpenDelay': 0.05,
    # 'ExternalShutter': 0,
    # 'FileWriteMode': 'Stream',
    'rot_speed_deg_per_s': 0.5,
    'Use_Fast_Shutter': 0,
    # Logging: 0=UNSET, 10=DEBUG, 20=INFO, 30=WARNING, 40=ERROR, 50=CRITICAL
    'Log_Level': logging.INFO,
}


def set_exit_handler(func):
    signal.signal(signal.SIGTERM, func)


def getVariableDict():
    return variableDict


def run_tomo_step_scan(angles, stabilize_sleep_ms=10, exposure=0.5,
                       num_white=(5, 5), num_dark=(5, 0),
                       sample_pos=(None,), out_pos=(None,),
                       rot_speed_deg_per_s=0.5, key=None,
                       log_level=logging.INFO,
                       use_fast_shutter=True,
                       txm=None):
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
    use_fast_shutter : bool, optional
      Whether to open and shut the fast shutter before triggering
      projections.
    log_level : int, optional
      Temporary log level to use. None (default) does not change the logging.
    txm : optional
      An instance of the NanoTXM class. If not given, a new one will
      be created. Mostly used for testing.
    
    """
    # Unpack options
    num_pre_white_images, num_post_white_images = num_white
    num_pre_dark_images, num_post_dark_images = num_dark
    out_pos = tools.expand_position(out_pos, 4)
    sample_pos = tools.expand_position(sample_pos, 4)
    # Some intial logging
    start_time = time.time()
    log.debug('called start_scan()')
    # # Start verifier on remote machine
    # start_verifier(INSTRUMENT, None, variableDict, VER_DIR, VER_HOST, VER_PORT, key)
    # Prepare X-ray microscope
    if txm is None:
        txm = new_txm()
    # Prepare the microscope for collecting data
    with txm.run_scan():
        assert use_fast_shutter
        if use_fast_shutter:
            txm.enable_fast_shutter()
        total_projections = len(angles)
        total_projections += num_pre_white_images + num_post_white_images
        total_projections += num_pre_dark_images + num_post_dark_images
        txm.setup_detector(num_projections=total_projections,
                           exposure=exposure)
        txm.setup_hdf_writer(num_projections=total_projections)
        txm.start_logging(level=log_level)
        # Collect pre-scan dark-field images
        if num_pre_dark_images > 0:
            logging.info("Capturing %d dark-fields at %s", num_pre_dark_images, out_pos)
            txm.close_shutters()
            txm.capture_dark_field(num_projections=num_pre_dark_images)
        # Collect pre-scan white-field images
        if num_pre_white_images > 0:
            logging.info("Capturing %d flat-fields at %s", num_pre_white_images, out_pos)
            # Move the sample out and collect whitefields
            txm.move_sample(theta=out_pos[3]) # So we don't have crashes
            with txm.wait_pvs():
                txm.move_sample(*out_pos)
                txm.open_shutters()
            txm.capture_white_field(num_projections=num_pre_white_images)
        # Capture the actual sample data
        # txm.move_sample(theta=0) # So we don't have crashes
        txm.move_sample(sample_pos[3])
        with txm.wait_pvs():
            txm.move_sample(*sample_pos)
            txm.open_shutters()
        log.debug('Starting tomography scan')
        txm.capture_tomogram(angles=angles,
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
        log.info("Captured %d projections in %d sec.",
                 total_projections, time.time() - start_time)
        # Save hdf filename for storing angles
        hdf_filename = txm.hdf_filename
    # Save metadata
    try:
        with txm.hdf_file(hdf_filename, mode='r+') as f:
            log.debug('Saving angles to file: %s', hdf_filename)
            f.create_dataset('/exchange/theta', data=angles)
    except (OSError, IOError):
        # Could not load HDF file, so raise a warning
        msg = "Could not save angles to file %s" % hdf_filename
        warnings.warn(msg, RuntimeWarning)
        log.warning(msg)
    return txm


def main():
    # Update user settings
    update_variable_dict(variableDict)
    # Set up default stream logging
    # Choices are DEBUG, INFO, WARNING, ERROR, CRITICAL
    # logging.basicConfig(level=logging.DEBUG) # uncomment to get info in the console
    log_level = variableDict['Log_Level']
    tools.loggingConfig(level=log_level)
    # Prepare the exit handler
    key = ''.join(random.choice(string.letters[26:]+string.digits) for _ in range(10))
    def on_exit(sig, func=None):
        cleanup(global_PVs, variableDict, VER_HOST, VER_PORT, key)
        sys.exit(0)
    set_exit_handler(on_exit)
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
    step_size = ((sample_rot_end - sample_rot_start) / (num_projections - 1.0))
    stabilize_sleep_ms = float(variableDict['StabilizeSleep_ms'])
    use_fast_shutter = use_fast_shutter=bool(int(variableDict['Use_Fast_Shutter']))
    # Pre-scan sleep
    log.debug("Sleeping for %d seconds", int(sleep_time))
    time.sleep(sleep_time)
    # Call the main tomography function
    return run_tomo_step_scan(angles=angles,
                              stabilize_sleep_ms=stabilize_sleep_ms,
                              exposure=exposure, key=key,
                              num_white=num_white, num_dark=num_dark,
                              sample_pos=sample_pos, out_pos=out_pos,
                              rot_speed_deg_per_s=rot_speed_deg_per_s,
                              use_fast_shutter=use_fast_shutter,
                              log_level=log_level)


if __name__ == '__main__':
    # Launch the main script portion
    main()
