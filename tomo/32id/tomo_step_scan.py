'''
TomoScan for Sector 32 ID C

'''
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

from tomo_scan_lib import *


# hardcoded values for verifier
VER_HOST = "txmtwo"
VER_PORT = "5011"
VER_DIR = "/local/usr32idc/conda/data-quality/"
INSTRUMENT = "/home/beams/USR32IDC/.dquality/32id_micro"
IOC_PREFIX = '32idcPG3'
SHUTTER_PERMIT = False

global variableDict

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
    'ExposureTime': 3,
    # 'ShutterOpenDelay': 0.05,
    # 'IOC_Prefix': '32idcPG3:',
    # 'ExternalShutter': 0,
    'FileWriteMode': 'Stream',
    'rot_speed_deg_per_s': 0.5,
    'Recursive_Filter_Enabled': 0,
    'Recursive_Filter_N_Images': 2,
    'Recursive_Filter_Type': 'RecursiveAve'
    # 'UseInterferometer': 0
}


def set_exit_handler(func):
    signal.signal(signal.SIGTERM, func)


def getVariableDict():
    global variableDict
    return variableDict


def tomo_scan(txm):
    log.debug('called tomo_scan()')
    theta = []
    interf_arr = []
    if int(variableDict.get('UseInterferometer', 0)) > 0:
        txm.Interferometer_Mode = "ONE-SHOT"
    # Get variables from variable dictionary
    sample_rot_end = float(variableDict['SampleEnd_Rot'])
    sample_rot_start = float(variableDict['SampleStart_Rot'])
    num_projections = float(variableDict['Projections'])
    step_size = ((sample_rot_end - sample_rot_start) / (num_projections - 1.0))
    txm.Cam1_FrameType = txm.FRAME_DATA
    txm.Cam1_NumImages = 1
    #if int(variableDict['ExternalShutter']) == 1:
    #	global_PVs['Cam1_TriggerMode'].put('Ext. Standard', wait=True)
    if variableDict['Recursive_Filter_Enabled'] == 1:
        txm.Proc1_Filter_Enable = 'Enable'
    sample_rot = sample_rot_start
    for i in range(int(variableDict['Projections'])):
        # while sample_rot <= end_pos:
        log.debug('Sample Rot: %f°', sample_rot)
        txm.Motor_SampleRot = sample_rot
        if int(variableDict.get('UseInterferometer', 0)) > 0:
            txm.Interferometer_Acquire = 1
            interf_arr += [global_PVs['Interferometer_Val'].get()]
        log.debug('Stabilize Sleep: %d ms', variableDict['StabilizeSleep_ms'])
        time.sleep(float(variableDict['StabilizeSleep_ms']) / 1000.0)
        # save theta to array
        theta += [sample_rot]
        # start detector acquire
        if variableDict['Recursive_Filter_Enabled'] == 1:
            global_PVs['Proc1_Callbacks'].put('Enable', wait=True)
            for i in range(int(variableDict['Recursive_Filter_N_Images'])):
                global_PVs['Cam1_Acquire'].put(DetectorAcquire)
                wait_pv(global_PVs['Cam1_Acquire'], DetectorAcquire, 2)
                global_PVs['Cam1_SoftwareTrigger'].put(1)
                wait_pv(global_PVs['Cam1_Acquire'], DetectorIdle, 60)
        else:
            txm.Cam1_Acquire = DetectorAcquire
            txm.wait_pv('Cam1_Acquire', DetectorAcquire, timeout=2)
            txm.Cam1_SoftwareTrigger = 1
        # if external shutter
        #if int(variableDict['ExternalShutter']) == 1:
        #	print 'External trigger'
        #	#time.sleep(float(variableDict['rest_time']))
        #	global_PVs['ExternalShutter_Trigger'].put(1, wait=True)
        # wait for acquire to finish
        txm.wait_pv('Cam1_Acquire', DetectorIdle, 60)
        # update sample rotation
        sample_rot += step_size
    # set trigger move to internal for post dark and white
    #global_PVs['Cam1_TriggerMode'].put('Internal', wait=True)
    #if int(variableDict['ExternalShutter']) == 1:
    #	global_PVs['SetSoftGlueForStep'].put('0')
    if variableDict['Recursive_Filter_Enabled'] == 1:
        txm.Proc1_Filter_Enable = 'Disable'
    return theta, interf_arr


def mirror_fly_scan(rev=False):
    log.debug('called mirror_fly_scan(rev=%r)', rev)
    interf_arr = []
    global_PVs['Interferometer_Reset'].put(1, wait=True)
    time.sleep(2.0)
    # setup fly scan macro
    delta = ((float(variableDict['SampleEnd_Rot']) - float(variableDict['SampleStart_Rot'])) / (	float(variableDict['Projections'])))
    slew_speed = 60
    global_PVs['Fly_ScanDelta'].put(delta)
    if rev:
        global_PVs['Fly_StartPos'].put(float(variableDict['SampleEnd_Rot']))
        global_PVs['Fly_EndPos'].put(float(variableDict['SampleStart_Rot']))
    else:
        global_PVs['Fly_StartPos'].put(float(variableDict['SampleStart_Rot']))
        global_PVs['Fly_EndPos'].put(float(variableDict['SampleEnd_Rot']))
    global_PVs['Fly_SlewSpeed'].put(slew_speed)
    # num_images = ((float(variableDict['SampleEnd_Rot']) - float(variableDict['SampleStart_Rot'])) / (delta + 1.0))
    #num_images = int(variableDict['Projections'])
    log.debug('Taxi')
    global_PVs['Fly_Taxi'].put(1, wait=True)
    wait_pv(global_PVs['Fly_Taxi'], 0)
    log.debug('Fly')
    global_PVs['Fly_Run'].put(1, wait=True)
    wait_pv(global_PVs['Fly_Run'], 0)
    global_PVs['Interferometer_Proc_Arr'].put(1)
    time.sleep(2.0)
    interf_cnt = global_PVs['Interferometer_Cnt'].get()
    interf_arr = global_PVs['Interferometer_Arr'].get(count=interf_cnt)
    # wait for acquire to finish
    return interf_arr


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
    # Collect interferometer
    interf_arrs = []
    use_interferometer = int(variableDict.get('UserInterferometer', 0)) > 0
    print(use_interferometer)
    if use_interferometer:
        for i in range(2):
            interf_arrs += [mirror_fly_scan()]
            interf_arrs += [mirror_fly_scan(rev=True)]
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
    exposure = float(variableDict['ExposureTime'])
    # Start scan sleep in min so min * 60 = sec
    time.sleep(sleep_time)
    # Prepare the microscope for collecting data
    log.error("Reimplement setup_detector() function")
    # setup_detector(global_PVs, variableDict)
    # setup_writer(global_PVs, variableDict)
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
    theta, interf_step = tomo_scan(txm)
    # Capture post-scan white-field images
    if num_post_white_images > 0:
        with txm.wait_pvs():
            txm.move_sample(*out_pos)
        txm.capture_white_field(num_projections=num_post_white_images,
                                exposure=exposure)
    # Capture post-scan dark-field images
    if num_post_dark_images > 0:
        txm.close_shutters()
        txm.capture_dark_field(num_projections=num_post_dark_images,
                               exposure=exposure)
    # Clean up and exit
    txm.close_shutters()
    add_extra_hdf5('global_PVs', variableDict, theta, interf_arrs)
    txm.reset_ccd()
    # move_dataset_to_run_dir()


def main():
    # Prepare the exit handler
    key = ''.join(random.choice(string.letters[26:]+string.digits) for _ in range(10))
    def on_exit(sig, func=None):
        cleanup(global_PVs, variableDict, VER_HOST, VER_PORT, key)
        sys.exit(0)
    set_exit_handler(on_exit)
    # Create the microscope object
    has_permit = False
    txm = TXM(has_permit=has_permit, is_attached=True,
              use_shutter_A=False, use_shutter_B=True,
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
