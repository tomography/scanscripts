'''
	FlyScan for Sector 32 ID C

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

from tomo_scan_lib import *

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


global_PVs = {}

#def getVariableDict():
#	return variableDict
def getVariableDict():
	global variableDict
	return variableDict

def get_calculated_num_projections(variableDict):
	print 'get_calculated_num_projections'
	delta = ((float(variableDict['SampleEndPos']) - float(variableDict['SampleStartPos'])) / (float(variableDict['Projections'])))
	slew_speed = (float(variableDict['SampleEndPos']) - float(variableDict['SampleStartPos'])) / (float(variableDict['Projections']) * (float(variableDict['ExposureTime']) + float(variableDict['CCD_Readout'])))
	global_PVs['Fly_ScanDelta'].put(delta)
	print 'start pos ',float(variableDict['SampleStartPos']),'end pos', float(variableDict['SampleEndPos'])
	global_PVs['Fly_StartPos'].put(float(variableDict['SampleStartPos']))
	global_PVs['Fly_EndPos'].put(float(variableDict['SampleEndPos']))
	global_PVs['Fly_SlewSpeed'].put(slew_speed)
	time.sleep(0.25)
	calc_num_proj = global_PVs['Fly_Calc_Projections'].get()
	if calc_num_proj == None:
		print 'Error getting fly calculated number of projections!'
		calc_num_proj = global_PVs['Fly_Calc_Projections'].get()
	if calc_num_proj < int(variableDict['Projections']):
		print 'Updating number of projections from:', variableDict['Projections'], ' to: ', calc_num_proj
		variableDict['Projections'] = int(calc_num_proj)
	print 'Num projections = ',int(variableDict['Projections']), ' fly calc triggers = ', calc_num_proj

def fly_scan(variableDict):
	print 'fly_scan()'
	theta = []
	global_PVs['Reset_Theta'].put(1)
	global_PVs['Cam1_AcquireTime'].put(float(variableDict['ExposureTime']) )
	# setup fly scan macro
	#delta = ((float(variableDict['SampleEndPos']) - float(variableDict['SampleStartPos'])) / (float(variableDict['Projections']) ))
	# slew_speed = (end - start) / (proj * (exposure + ccd_readout))
	#slew_speed = (float(variableDict['SampleEndPos']) - float(variableDict['SampleStartPos'])) / ( float(variableDict['Projections']) * (float(variableDict['ExposureTime']) + float(variableDict['CCD_Readout'])))
	#global_PVs['Fly_ScanDelta'].put(delta)
	#global_PVs['Fly_StartPos'].put(float(variableDict['SampleStartPos']))
	#global_PVs['Fly_EndPos'].put(float(variableDict['SampleEndPos']))
	#global_PVs['Fly_SlewSpeed'].put(slew_speed)

	#num_images1 = ((float(variableDict['SampleEndPos']) - float(variableDict['SampleStartPos'])) / (delta + 1.0))
	num_images = int(variableDict['Projections'])
	global_PVs['Cam1_FrameType'].put(FrameTypeData, wait=True)
	global_PVs['Cam1_NumImages'].put(num_images, wait=True)
	global_PVs['Cam1_TriggerMode'].put('Overlapped', wait=True)
	# start acquiring
	global_PVs['Cam1_Acquire'].put(DetectorAcquire)
	wait_pv(global_PVs['Cam1_Acquire'], 1)
	print 'Taxi'
	global_PVs['Fly_Taxi'].put(1, wait=True)
	wait_pv(global_PVs['Fly_Taxi'], 0)
	print 'Fly'
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


def start_scan(variableDict, detector_filename):
	print 'start_scan()'
	init_general_PVs(global_PVs, variableDict)
	if variableDict.has_key('StopTheScan'):
		stop_scan(global_PVs, variableDict)
		return
	get_calculated_num_projections(variableDict)
	global_PVs['Fly_ScanControl'].put('Custom')
	# Start scan sleep in min so min * 60 = sec
	time.sleep(float(variableDict['StartSleep_min']) * 60.0)
	setup_detector(global_PVs, variableDict)
	setup_writer(global_PVs, variableDict, detector_filename)
	if int(variableDict['PreDarkImages']) > 0:
		close_shutters(global_PVs, variableDict)
		print 'Capturing Pre Dark Field'
		capture_multiple_projections(global_PVs, variableDict, int(variableDict['PreDarkImages']), FrameTypeDark)
	if int(variableDict['PreWhiteImages']) > 0:
		print 'Capturing Pre White Field'
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
		print 'Capturing Post White Field'
		move_sample_out(global_PVs, variableDict)
		capture_multiple_projections(global_PVs, variableDict, int(variableDict['PostWhiteImages']), FrameTypeWhite)
	if int(variableDict['PostDarkImages']) > 0:
		print 'Capturing Post Dark Field'
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
	#move_dataset_to_run_dir(global_PVs, variableDict)


def main():
	update_variable_dict(variableDict)
	init_general_PVs(global_PVs, variableDict)
	FileName = global_PVs['HDF1_FileName'].get(as_string=True)
	start_scan(variableDict, FileName)


if __name__ == '__main__':
	main()

