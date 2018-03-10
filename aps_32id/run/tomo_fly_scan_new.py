'''
	FlyScan for Sector 32 ID C

'''

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

__author__ = 'Mark Wolf'
__copyright__ = 'Copyright (c) 2017, UChicago Argonne, LLC.'
__docformat__ = 'restructuredtext en'
__platform__ = 'Unix'
__version__ = '1.6'
__all__ = ['fly_scan',
           'start_scan']

log = logging.getLogger(__name__)

# hardcoded values for verifier
VER_HOST = "txmtwo"
VER_PORT = "5011"
VER_DIR = "/local/usr32idc/conda/data-quality/"
INSTRUMENT = "/home/beams/USR32IDC/.dquality/32id_micro"

global variableDict

variableDict = {'PreDarkImages': 5,
                'PreWhiteImages': 10,
                'Projections': 3000,
                'PostDarkImages': 5,
                'PostWhiteImages': 10,
                'SampleXOut': 8,
                'SampleYOut': 0.0,
                'SampleZOut': 0.0,
                'SampleXIn': 0.0,
                'SampleYIn': 0.0,
                'SampleZIn': 0.0,
                'SampleStartPos': 0.0,
                'SampleEndPos': 180.0,
                'StartSleep_min': 0,
                'StabilizeSleep_ms': 0,
                'ExposureTime': 0.2,
                'ExposureTime_Flat': 0.2,
                'ShutterOpenDelay': 0.00,
                'IOC_Prefix': '32idcPG3:',
                #'ExternalShutter': 0,
                'FileWriteMode': 'Stream',
                'UseInterferometer': 0,
                'CCD_Readout': 0.270
                }


def getVariableDict():
    global variableDict
    return variableDict

def get_calculated_num_projections(variableDict):
    delta = ((float(variableDict['SampleEndPos']) - float(variableDict['SampleStartPos'])) / (float(variableDict['Projections'])))
    slew_speed = (float(variableDict['SampleEndPos']) - float(variableDict['SampleStartPos'])) / (float(variableDict['Projections']) * (float(variableDict['ExposureTime']) + float(variableDict['CCD_Readout'])))
    global_PVs['Fly_ScanDelta'].put(delta)
    log.debug('start pos: %f, end pos: %f',
              float(variableDict['SampleStartPos']),
              float(variableDict['SampleEndPos']))
    global_PVs['Fly_StartPos'].put(float(variableDict['SampleStartPos']))
    global_PVs['Fly_EndPos'].put(float(variableDict['SampleEndPos']))
    global_PVs['Fly_SlewSpeed'].put(slew_speed)
    time.sleep(0.25)
    calc_num_proj = global_PVs['Fly_Calc_Projections'].get()
    if calc_num_proj == None:
        # Error getting fly calculated number of projections!
        calc_num_proj = global_PVs['Fly_Calc_Projections'].get()
    if calc_num_proj < int(variableDict['Projections']):
        variableDict['Projections'] = int(calc_num_proj)


def fly_scan(variableDict):
    theta = []
    global_PVs['Reset_Theta'].put(1)
    global_PVs['Cam1_AcquireTime'].put(float(variableDict['ExposureTime']) )
    
    num_images = int(variableDict['Projections'])
    global_PVs['Cam1_FrameType'].put(FrameTypeData, wait=True)
    global_PVs['Cam1_NumImages'].put(num_images, wait=True)
    global_PVs['Cam1_TriggerMode'].put('Overlapped', wait=True)
    # start acquiring
    global_PVs['Cam1_Acquire'].put(DetectorAcquire)
    wait_pv(global_PVs['Cam1_Acquire'], 1)
    global_PVs['Fly_Taxi'].put(1, wait=True)
    wait_pv(global_PVs['Fly_Taxi'], 0)
    global_PVs['Fly_Run'].put(1, wait=True)
    wait_pv(global_PVs['Fly_Run'], 0)
    # wait for acquire to finish
    wait_pv(global_PVs['Cam1_Acquire'], DetectorIdle)
    # set trigger move to internal for post dark and white
    #global_PVs['Cam1_TriggerMode'].put('Internal')
    global_PVs['Proc_Theta'].put(1)
    #theta_cnt = global_PVs['Theta_Cnt'].get()
    theta = global_PVs['Theta_Array'].get(count=int(variableDict['Projections']))
    return theta


def tomo_fly_scan(projections=3000, rotation_start=0, rotation_end=180):
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
    
    """
    get_calculated_num_projections(variableDict)
    global_PVs['Fly_ScanControl'].put('Custom')
    # Start scan sleep in min so min * 60 = sec
    time.sleep(float(variableDict['StartSleep_min']) * 60.0)
    setup_detector(global_PVs, variableDict)
    setup_writer(global_PVs, variableDict, detector_filename)
    if int(variableDict['PreDarkImages']) > 0:
        close_shutters(global_PVs, variableDict)
        capture_multiple_projections(global_PVs, variableDict, int(variableDict['PreDarkImages']), FrameTypeDark)
    if int(variableDict['PreWhiteImages']) > 0:
        open_shutters(global_PVs, variableDict)
        move_sample_out(global_PVs, variableDict)
        capture_multiple_projections(global_PVs, variableDict, int(variableDict['PreWhiteImages']), FrameTypeWhite)
    move_sample_in(global_PVs, variableDict)
    #time.sleep(float(variableDict['StabilizeSleep_ms']) / 1000.0)
    open_shutters(global_PVs, variableDict)
    # run fly scan
    theta = fly_scan(variableDict)
    ###wait_pv(global_PVs['HDF1_NumCaptured'], expected_num_cap, 60)
    if int(variableDict['PostWhiteImages']) > 0:
        # Capturing Post White Field
        move_sample_out(global_PVs, variableDict)
        capture_multiple_projections(global_PVs, variableDict, int(variableDict['PostWhiteImages']), FrameTypeWhite)
    if int(variableDict['PostDarkImages']) > 0:
        # Capturing Post Dark Field
        close_shutters(global_PVs, variableDict)
        capture_multiple_projections(global_PVs, variableDict, int(variableDict['PostDarkImages']), FrameTypeDark)
    close_shutters(global_PVs, variableDict)
    time.sleep(0.25)
    wait_pv(global_PVs["HDF1_Capture_RBV"], 0, 600)
    add_theta(global_PVs, variableDict, theta)
    global_PVs['Fly_ScanControl'].put('Standard')
    global_PVs['Cam1_TriggerMode'].put('Internal', wait=True)
    global_PVs['Cam1_TriggerMode'].put('Overlapped', wait=True)
    global_PVs['Cam1_TriggerMode'].put('Internal', wait=True)
    # move_dataset_to_run_dir(global_PVs, variableDict)


def main():
    # The script was launched (not imported) so use the variable dictionary
    update_variable_dict(variableDict)
    # Prepare variables
    angles = []
    # Start the experiment
    tomo_fly_scan(projections=variableDict['Projections'])


if __name__ == '__main__':
    main()

