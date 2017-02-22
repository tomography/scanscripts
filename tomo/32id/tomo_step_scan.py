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

from tomo_scan_lib import *


global variableDict



variableDict = {'PreDarkImages': 5,
		'PreWhiteImages': 5,
		'Projections': 361,
		'PostDarkImages': 0,
		'PostWhiteImages': 5,
		'SampleXOut': 0.05,
#		'SampleYOut': 0.1,
#		'SampleZOut': 0,
#		'SampleRotOut': 90.0,
		'SampleXIn': 0.0,
#		'SampleYIn': 0.1,
#		'SampleZIn': 0.0,
		'SampleStart_Rot': 0.0,
		'SampleEnd_Rot': 180.0,
		'StartSleep_min': 0,
		'StabilizeSleep_ms': 1,
		'ExposureTime': 3,
#		'ShutterOpenDelay': 0.05,
		'IOC_Prefix': '32idcPG3:',
#		'ExternalShutter': 0,
		'FileWriteMode': 'Stream',
		'rot_speed_deg_per_s': 0.5,
		'Recursive_Filter_Enabled': 0,
		'Recursive_Filter_N_Images': 2,
		'Recursive_Filter_Type': 'RecursiveAve'
#		'UseInterferometer': 0
		}

global_PVs = {}

def getVariableDict():
	global variableDict
	return variableDict

def tomo_scan():
	print 'tomo_scan()'
	theta = []
	interf_arr = []
	if variableDict.has_key('UseInterferometer') and int(variableDict['UseInterferometer']) > 0:
		global_PVs['Interferometer_Mode'].put('ONE-SHOT')
	step_size = ((float(variableDict['SampleEnd_Rot']) - float(variableDict['SampleStart_Rot'])) / (float(variableDict['Projections']) - 1.0))
	#end_pos = float(variableDict['SampleEnd_Rot'])
	global_PVs['Cam1_FrameType'].put(FrameTypeData, wait=True)
	global_PVs['Cam1_NumImages'].put(1, wait=True)
	#if int(variableDict['ExternalShutter']) == 1:
	#	global_PVs['Cam1_TriggerMode'].put('Ext. Standard', wait=True)
	sample_rot = float(variableDict['SampleStart_Rot'])
	if variableDict['Recursive_Filter_Enabled'] == 1:
		global_PVs['Proc1_Filter_Enable'].put('Enable')
  
	for i in range(int(variableDict['Projections'])):
	#while sample_rot <= end_pos:
		print 'Sample Rot:', sample_rot
		global_PVs['Motor_SampleRot'].put(sample_rot, wait=True)
		if variableDict.has_key('UseInterferometer') and int(variableDict['UseInterferometer']) > 0:
			global_PVs['Interferometer_Acquire'].put(1)
			interf_arr += [global_PVs['Interferometer_Val'].get()]
		print 'Stabilize Sleep (ms)', variableDict['StabilizeSleep_ms']
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
			global_PVs['Cam1_Acquire'].put(DetectorAcquire)
			wait_pv(global_PVs['Cam1_Acquire'], DetectorAcquire, 2)
			global_PVs['Cam1_SoftwareTrigger'].put(1)
		# if external shutter
		#if int(variableDict['ExternalShutter']) == 1:
		#	print 'External trigger'
		#	#time.sleep(float(variableDict['rest_time']))
		#	global_PVs['ExternalShutter_Trigger'].put(1, wait=True)
		# wait for acquire to finish
		wait_pv(global_PVs['Cam1_Acquire'], DetectorIdle, 60)
		# update sample rotation
		sample_rot += step_size
	# set trigger move to internal for post dark and white
	#global_PVs['Cam1_TriggerMode'].put('Internal', wait=True)
	#if int(variableDict['ExternalShutter']) == 1:
	#	global_PVs['SetSoftGlueForStep'].put('0')
	if variableDict['Recursive_Filter_Enabled'] == 1:
			global_PVs['Proc1_Filter_Enable'].put('Disable', wait=True)
	return theta, interf_arr

def mirror_fly_scan(rev=False):
	print 'mirror_fly_scan()'
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
	print 'Taxi'
	global_PVs['Fly_Taxi'].put(1, wait=True)
	wait_pv(global_PVs['Fly_Taxi'], 0)
	print 'Fly'
	global_PVs['Fly_Run'].put(1, wait=True)
	wait_pv(global_PVs['Fly_Run'], 0)
	global_PVs['Interferometer_Proc_Arr'].put(1)
	time.sleep(2.0)
	interf_cnt = global_PVs['Interferometer_Cnt'].get()
	interf_arr = global_PVs['Interferometer_Arr'].get(count=interf_cnt)
	# wait for acquire to finish
	return interf_arr


def full_tomo_scan():
	print 'start_scan()'
	init_general_PVs(global_PVs, variableDict)
	if variableDict.has_key('StopTheScan'):
		stop_scan(global_PVs, variableDict)
		return
	#collect interferometer
	interf_arrs = []
	if variableDict.has_key('UseInterferometer') and int(variableDict['UseInterferometer']) > 0:
		for i in range(2):
			interf_arrs += [mirror_fly_scan()]
			interf_arrs += [mirror_fly_scan(rev=True)]
	# Start scan sleep in min so min * 60 = sec
	time.sleep(float(variableDict['StartSleep_min']) * 60.0)
	setup_detector(global_PVs, variableDict)
	setup_writer(global_PVs, variableDict)
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
	theta, interf_step = tomo_scan()
#	interf_arrs += [interf_step]
	if int(variableDict['PostWhiteImages']) > 0:
		print 'Capturing Post White Field'
		move_sample_out(global_PVs, variableDict)
		capture_multiple_projections(global_PVs, variableDict, int(variableDict['PostWhiteImages']), FrameTypeWhite)
	if int(variableDict['PostDarkImages']) > 0:
		print 'Capturing Post Dark Field'
		close_shutters(global_PVs, variableDict)
		capture_multiple_projections(global_PVs, variableDict, int(variableDict['PostDarkImages']), FrameTypeDark)
	close_shutters(global_PVs, variableDict)
	#if int(variableDict['ExternalShutter']) == 1:
	#	global_PVs['SetSoftGlueForStep'].put('0')
	add_extra_hdf5(global_PVs, variableDict, theta, interf_arrs)	
	reset_CCD(global_PVs, variableDict)
	#move_dataset_to_run_dir()


def main():
	update_variable_dict(variableDict)
	full_tomo_scan()

if __name__ == '__main__':
	main()

