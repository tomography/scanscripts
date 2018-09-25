# -*- coding: utf-8 -*-
'''
FlyScan for Sector 32-ID-C
'''

from __future__ import division, print_function

import logging

import sys
import json
import time
from epics import PV
import h5py
import shutil
import os
import imp
import traceback
import signal
import random
import string

from aps_32id.txm import new_txm
from scanlib.tools import expand_position, loggingConfig
from scanlib.scan_variables import update_variable_dict

__author__ = 'Mark Wolfman'
__copyright__ = 'Copyright (c) 2017, UChicago Argonne, LLC.'
__docformat__ = 'restructuredtext en'
__platform__ = 'Unix'
__version__ = '1.6'
__all__ = ['run_tomo_fly_scan', 'getVariableDict']

log = logging.getLogger(__name__)

# hardcoded values for verifier
VER_HOST = "txmtwo"
VER_PORT = "5011"
VER_DIR = "/local/usr32idc/conda/data-quality/"
INSTRUMENT = "/home/beams/USR32IDC/.dquality/32id_micro"

global variableDict

variableDict = {
    'PreDarkImages': 5,
    'PreWhiteImages': 10,
    'Projections': 1201,
    'PostDarkImages': 5,
    'PostWhiteImages': 10,
    'SampleXOut': 0.2,
    'SampleYOut': 0.0,
    'SampleZOut': 0.0,
    'SampleXIn': 0.0,
    'SampleYIn': 0.0,
    'SampleZIn': 0.0,
    'SampleStartPos': 0.0,
    'SampleEndPos': 180.0,
    'StartSleep_min': 0,
    'StabilizeSleep_ms': 0,
    'ExposureTime': 1,
    'ExposureTime_Flat': 1,
    'ShutterOpenDelay': 0.00,
    'IOC_Prefix': '32idcPG3:',
    #'ExternalShutter': 0,
    'FileWriteMode': 'Stream',
    'UseInterferometer': 0,
    # Logging: 0=UNSET, 10=DEBUG, 20=INFO, 30=WARNING, 40=ERROR, 50=CRITICAL
    'Log_Level': logging.DEBUG,
}


def getVariableDict():
    global variableDict
    return variableDict

# global_PVs['Cam1_FrameType'].put(FrameTypeData, wait=True)

def run_tomo_fly_scan(projections=3000, rotation_start=0,
                      rotation_end=180, exposure=0.2,
                      num_white=(5, 5), num_dark=(5, 0),
                      sample_pos=(None,), out_pos=(None,),
                      log_level=logging.INFO,
                      txm=None):
    """Collect a 180° tomogram in fly-scan mode.
    
    The defining feature here is that the rotation axis does not stop,
    giving more projections in less time. It is common to set the
    number of projections to be significantly higher than when
    executing a step scan.
    
    Parameters
    ----------
    projections : int, optional
      How many total projections to collect over the full rotation
      range.
    rotation_start : float, optional
      Initial angle for the tomogram, in degrees.
    rotation_end : float, optional
      Final angle for the tomogram, in degrees.
    exposure : float, optional
      How long to collect each frame for, in seconds.
    num_white : 2-tuple(int), optional
      (pre, post) tuple for number of white field images to collect.
    num_dark : 2-tuple(int), optional
      (pre, post) tuple for number of dark field images to collect.
    sample_pos : 4-tuple(float), optional
      4 (or less) tuple of (x, y, z, θ°) for the sample position.
    out_pos : 4-tuple(float), optional
      4 (or less) tuple of (x, y, z, θ°) for white field position.
    log_level : int, optional
      Temporary log level to use. ``None`` does not change the logging.
    txm : optional
      An instance of the NanoTXM class. If not given, a new one will
      be created. Mostly used for testing.
    """
    logging.debug("Starting run_tomo_fly_scan()")
    start_time = time.time()
    # Unpack options
    num_pre_white_images, num_post_white_images = num_white
    num_pre_dark_images, num_post_dark_images = num_dark
    sample_pos = expand_position(sample_pos)
    out_pos = expand_position(out_pos)
    num_pre_images = num_pre_dark_images + num_pre_white_images
    num_post_images = num_pre_dark_images + num_pre_white_images
    total_projections = (projections + num_pre_images + num_post_images)
    # Create the TXM object for this scan
    if txm is None:
        txm = new_txm()
    # Execute the actual scan script
    with txm.run_scan():
        # Prepare camera, etc.
        txm.setup_detector(exposure=exposure,
                           num_projections=total_projections)
        txm.setup_hdf_writer(num_projections=total_projections)
        txm.start_logging(level=log_level)
        # Capture pre dark field images
        if num_pre_dark_images > 0:
            txm.close_shutters()
            log.info("Capturing %d pre-dark-fields",
                     num_pre_dark_images)
            txm.start_detector(num_projections=num_pre_dark_images)
            txm.capture_dark_field(num_projections=num_pre_dark_images)
        # Collect pre-scan white-field images
        if num_pre_white_images > 0:
            log.info("Capturing %d pre-flat-fields at %s",
                     num_pre_white_images, str(out_pos))
            # Move the sample out and collect whitefields
            txm.move_sample(theta=out_pos[3]) # So we don't have crashes
            with txm.wait_pvs():
                txm.move_sample(*out_pos)
                txm.open_shutters()
            txm.start_detector(num_projections=num_pre_white_images)
            txm.capture_white_field(num_projections=num_pre_white_images)
        # Collect the actual tomogram flyscan
        txm.move_sample(theta=sample_pos[3])
        with txm.wait_pvs():
            txm.move_sample(*sample_pos)
            txm.open_shutters()
        txm.move_sample(theta=rotation_start)
        txm.start_detector(num_projections=projections)
        angles = txm.capture_tomogram_flyscan(start_angle=rotation_start,
                                              end_angle=rotation_end,
                                              num_projections=projections)
        # Capture post-scan white-field images
        if num_post_white_images > 0:
            log.info("Capturing %d post-flat-fields at %s",
                     num_post_white_images, str(out_pos))
            with txm.wait_pvs():
                txm.move_sample(*out_pos)
            txm.start_detector(num_projections=num_post_white_images)
            txm.capture_white_field(num_projections=num_post_white_images)
        # Capture post-scan dark-field images
        txm.close_shutters()
        if num_post_dark_images > 0:
            log.info("Capturing %d post-dark-fields",
                     num_post_dark_images)
            txm.start_detector(num_projections=num_post_dark_images)
            txm.capture_dark_field(num_projections=num_post_dark_images)
        # wait_pv(global_PVs["HDF1_Capture_RBV"], 0, 600)
        hdf_filename = txm.hdf_filename
    # Save metadata
    with txm.hdf_file(hdf_filename=hdf_filename) as f:
        f.create_dataset('/exchange/theta', data=angles)
    logging.info("Finished fly scan tomogram in {:.2f} sec"
                 "".format(time.time() - start_time))


def main():
    # The script was launched (not imported) so use the variable dictionary
    update_variable_dict(variableDict)
    # Basic global logging config, per file logging is setup later
    log_level = variableDict['Log_Level']
    loggingConfig(level=log_level)
    # Extract variables from the global dictionary
    sleep_time = float(variableDict['StartSleep_min']) * 60.0
    # Prepare variables
    angles = []
    # Pre-scan sleep
    log.debug("Sleeping for %d seconds", int(sleep_time))
    time.sleep(sleep_time)
    # Start the experiment
    num_white = (int(variableDict['PreWhiteImages']),
                 int(variableDict['PostWhiteImages']))
    num_dark = (int(variableDict['PreDarkImages']),
                int(variableDict['PostDarkImages']))
    sample_pos = (variableDict.get('SampleXIn', None),
                  variableDict.get('SampleYIn', None),
                  variableDict.get('SampleZIn', None),
                  float(variableDict['SampleStartPos']))
    out_pos = (variableDict.get('SampleXOut', None),
               variableDict.get('SampleYOut', None),
               variableDict.get('SampleZOut', None),
               variableDict.get('SampleRotOut', None), )
    # Execute the scan!!
    run_tomo_fly_scan(projections=variableDict['Projections'],
                      rotation_start=variableDict['SampleStartPos'],
                      rotation_end=variableDict['SampleEndPos'],
                      exposure=variableDict['ExposureTime'],
                      num_white=num_white, num_dark=num_dark,
                      sample_pos=sample_pos, out_pos=out_pos,
                      log_level=int(variableDict['Log_Level']),)


if __name__ == '__main__':
    main()
