'''
TomoScan for Sector 32 ID C

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

import h5py
from epics import PV
import numpy as np

from tomo_scan_lib import *


# Hardcoded values for verifier and TXM
VER_HOST = "txmtwo"
VER_PORT = "5011"
VER_DIR = "/local/usr32idc/conda/data-quality/"
INSTRUMENT = "/home/beams/USR32IDC/.dquality/32id_micro"
IOC_PREFIX = '32idcPG3'
SHUTTER_PERMIT = False

variableDict = {
    'PreDarkImages': 5,
    'PreWhiteImages': 5,
    'Projections': 361,
    'PostDarkImages': 0,
    'PostWhiteImages': 5,
    'SampleXOut': 0.05,
    # 'SampleYOut': 0.1,
    # 'SampleZOut': 0,
    # 'SampleRotOut': 90.0,
    'SampleXIn': 0.0,
    # 'SampleYIn': 0.1,
    # 'SampleZIn': 0.0,
    'SampleStart_Rot': 0.0,
    'SampleEnd_Rot': 180.0,
    'StartSleep_min': 0,
    'StabilizeSleep_ms': 1,
    'ExposureTime_sec': 3,
    # 'ShutterOpenDelay': 0.05,
    # 'ExternalShutter': 0,
    'FileWriteMode': 'Stream',
    'rot_speed_deg_per_s': 0.5,
    'Recursive_Filter_N_Images': 2,
}


def set_exit_handler(func):
    signal.signal(signal.SIGTERM, func)


def getVariableDict():
    global variableDict
    return variableDict


def full_tomo_scan(txm, key=None):
    # Some intial debugging
    start_time = time.time()
    log.debug('called start_scan()')
    # Stop the scan if requested
    if variableDict.get('StopTheScan'):
        raise NotImplementedError("Stop scan coming soon.")
        cleanup(global_PVs, variableDict, VER_HOST, VER_PORT, key)
        return
    # Start verifier on remote machine
    start_verifier(INSTRUMENT, None, variableDict, VER_DIR, VER_HOST, VER_PORT, key)
    # Extract variables from the global dictionary
    sleep_time = float(variableDict['StartSleep_min']) * 60.0
    num_pre_dark_images = int(variableDict['PreDarkImages'])
    num_post_dark_images = int(variableDict['PostDarkImages'])
    num_pre_white_images = int(variableDict['PreWhiteImages'])
    num_post_white_images = int(variableDict['PostWhiteImages'])
    sample_pos = (variableDict.get('SampleXIn', None),
                  variableDict.get('SampleYIn', None),
                  variableDict.get('SampleZIn', None))
    out_pos = (variableDict.get('SampleXOut', None),
               variableDict.get('SampleYOut', None),
               variableDict.get('SampleZOut', None))
    exposure = float(variableDict['ExposureTime_sec'])
    sample_rot_end = float(variableDict['SampleEnd_Rot'])
    sample_rot_start = float(variableDict['SampleStart_Rot'])
    num_projections = int(variableDict['Projections'])
    num_recursive_filter = int(variableDict['Recursive_Filter_N_Images'])
    step_size = ((sample_rot_end - sample_rot_start) / (num_projections - 1.0))
    stabilize_sleep = float(variableDict['StabilizeSleep_ms'])
    # Setup some PV info
    txm.Cam1_FrameType = txm.FRAME_DATA
    txm.Cam1_NumImages = 1
    # Pre-scan sleep
    time.sleep(sleep_time)
    # Prepare the microscope for collecting data
    txm.setup_tomo_detector()
    txm.setup_hdf_writer()
    # Collect pre-scan dark-field images
    if num_pre_dark_images > 0:
        txm.close_shutters()
        txm.capture_dark_field(num_projections=num_pre_dark_images,
                               exposure=exposure)
    # Collect pre-scan white-field images
    if num_pre_white_images > 0:
        with txm.wait_pvs():
            txm.move_sample(*out_pos)
            txm.open_shutters()
        txm.capture_white_field(num_projections=num_pre_white_images,
                                exposure=exposure)
    # Capture the actual sample data
    with txm.wait_pvs():
        txm.move_sample(*sample_pos)
        txm.open_shutters()
        log.debug('Starting tomography scan')
    thetas = np.linspace(sample_rot_start, sample_rot_end, num_projections)
    txm.capture_tomogram(angles=thetas, num_projections=num_recursive_filter,
                         exposure=exposure, stabilize_sleep=stabilize_sleep)
    # Capture post-scan white-field images
    if num_post_white_images > 0:
        with txm.wait_pvs():
            txm.move_sample(*out_pos)
        txm.capture_white_field(num_projections=num_post_white_images,
                                exposure=exposure)
    # Capture post-scan dark-field images
    txm.close_shutters()
    if num_post_dark_images > 0:
        txm.capture_dark_field(num_projections=num_post_dark_images,
                               exposure=exposure)
    # Save metadata
    with h5py.File(txm.hdf_filename) as f:
        f.create_dataset('/exchange/theta', data=thetas)
    # Clean up
    txm.reset_ccd()
    log.info("Captured %d projections in %d sec.", len(thetas), time.time() - start_time)
    


def main():
    # Prepare the exit handler
    key = ''.join(random.choice(string.letters[26:]+string.digits) for _ in range(10))
    def on_exit(sig, func=None):
        cleanup(global_PVs, variableDict, VER_HOST, VER_PORT, key)
        sys.exit(0)
    set_exit_handler(on_exit)
    # Create the microscope object
    has_permit = False
    txm = TXM(has_permit=SHUTTER_PERMIT,
              is_attached=True,
              use_shutter_A=False,
              use_shutter_B=True,
              ioc_prefix=IOC_PREFIX)
    # Call the main tomography function
    full_tomo_scan(txm=txm, key=key)


if __name__ == '__main__':
    # Set up default stream logging
    # Choices are DEBUG, INFO, WARNING, ERROR, CRITICAL
    logging.basicConfig(level=logging.WARNING)
    logging.captureWarnings(True)
    # Launch the main script portion
    main()
