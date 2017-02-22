'''
	Tomo Scan Lib for Sector 32 ID C

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

ShutterA_Open_Value = 0
ShutterA_Close_Value = 1
ShutterB_Open_Value = 0
ShutterB_Close_Value = 1
FrameTypeData = 0
FrameTypeDark = 1
FrameTypeWhite = 2
DetectorIdle = 0
DetectorAcquire = 1
UseShutterA = 0
UseShutterB = 1
PG_Trigger_External_Trigger = 1
Recursive_Filter_Type = 'RecursiveAve'


def update_variable_dict(variableDict):
	argDic = {}
	if len(sys.argv) > 1:
		strArgv = sys.argv[1]
		argDic = json.loads(strArgv)
	print 'orig variable dict', variableDict
	for k,v in argDic.iteritems():
		variableDict[k] = v
	print 'new variable dict', variableDict


#wait on a pv to be a value until max_timeout (default forever)
def wait_pv(pv, wait_val, max_timeout_sec=-1):
	print 'wait_pv(', pv.pvname, wait_val, max_timeout_sec, ')'
	#delay for pv to change
	time.sleep(.01)
	startTime = time.time()
	while(True):
		pv_val = pv.get()
		if (pv_val != wait_val):
			if max_timeout_sec > -1:
				curTime = time.time()
				diffTime = curTime - startTime
				if diffTime >= max_timeout_sec:
					return False
			time.sleep(.01)
		else:
			return True


def init_general_PVs(global_PVs, variableDict):
	print 'init_PVs()'
	#init detector pv's
	global_PVs['Cam1_ImageMode'] = PV(variableDict['IOC_Prefix'] + 'cam1:ImageMode')
	global_PVs['Cam1_ArrayCallbacks'] = PV(variableDict['IOC_Prefix'] + 'cam1:ArrayCallbacks')
	global_PVs['Cam1_AcquirePeriod'] = PV(variableDict['IOC_Prefix'] + 'cam1:AcquirePeriod')
	global_PVs['Cam1_TriggerMode'] = PV(variableDict['IOC_Prefix'] + 'cam1:TriggerMode')
	global_PVs['Cam1_SoftwareTrigger'] = PV(variableDict['IOC_Prefix'] + 'cam1:SoftwareTrigger')
	global_PVs['Cam1_AcquireTime'] = PV(variableDict['IOC_Prefix'] + 'cam1:AcquireTime')
	global_PVs['Cam1_FrameRateOnOff'] = PV(variableDict['IOC_Prefix'] + 'cam1:FrameRateOnOff')
	global_PVs['Cam1_FrameType'] = PV(variableDict['IOC_Prefix'] + 'cam1:FrameType')
	global_PVs['Cam1_NumImages'] = PV(variableDict['IOC_Prefix'] + 'cam1:NumImages')
	global_PVs['Cam1_Acquire'] = PV(variableDict['IOC_Prefix'] + 'cam1:Acquire')

	#hdf5 writer pv's
	global_PVs['HDF1_AutoSave'] = PV(variableDict['IOC_Prefix'] + 'HDF1:AutoSave')
	global_PVs['HDF1_DeleteDriverFile'] = PV(variableDict['IOC_Prefix'] + 'HDF1:DeleteDriverFile')
	global_PVs['HDF1_EnableCallbacks'] = PV(variableDict['IOC_Prefix'] + 'HDF1:EnableCallbacks')
	global_PVs['HDF1_BlockingCallbacks'] = PV(variableDict['IOC_Prefix'] + 'HDF1:BlockingCallbacks')
	global_PVs['HDF1_FileWriteMode'] = PV(variableDict['IOC_Prefix'] + 'HDF1:FileWriteMode')
	global_PVs['HDF1_NumCapture'] = PV(variableDict['IOC_Prefix'] + 'HDF1:NumCapture')
	global_PVs['HDF1_Capture'] = PV(variableDict['IOC_Prefix'] + 'HDF1:Capture')
	global_PVs['HDF1_Capture_RBV'] = PV(variableDict['IOC_Prefix'] + 'HDF1:Capture_RBV')
	global_PVs['HDF1_FileName'] = PV(variableDict['IOC_Prefix'] + 'HDF1:FileName')
	global_PVs['HDF1_FullFileName_RBV'] = PV(variableDict['IOC_Prefix'] + 'HDF1:FullFileName_RBV')
	global_PVs['HDF1_FileTemplate'] = PV(variableDict['IOC_Prefix'] + 'HDF1:FileTemplate')
	global_PVs['HDF1_ArrayPort'] = PV(variableDict['IOC_Prefix'] + 'HDF1:NDArrayPort')

	#motor pv's
	global_PVs['Motor_SampleX'] = PV('32idcTXM:mcs:c1:m2.VAL')
	global_PVs['Motor_SampleY'] = PV('32idcTXM:xps:c1:m7.VAL')
#	global_PVs['Motor_SampleRot'] = PV('32idcTXM:hydra:c0:m1.VAL')
	global_PVs['Motor_SampleRot'] = PV('32idcTXM:ens:c1:m1.VAL')
	global_PVs['Motor_SampleZ'] = PV('32idcTXM:mcs:c1:m1.VAL')
	global_PVs['Motor_X_Tile'] = PV('32idc01:m33.VAL')
	global_PVs['Motor_Y_Tile'] = PV('32idc02:m15.VAL')

	#shutter pv's
	global_PVs['ShutterA_Open'] = PV('32idb:rshtrA:Open')
	global_PVs['ShutterA_Close'] = PV('32idb:rshtrA:Close')
	global_PVs['ShutterA_Move_Status'] = PV('PB:32ID:STA_A_FES_CLSD_PL')
	global_PVs['ShutterB_Open'] = PV('32idb:fbShutter:Open.PROC')
	global_PVs['ShutterB_Close'] = PV('32idb:fbShutter:Close.PROC')
	global_PVs['ShutterB_Move_Status'] = PV('PB:32ID:STA_B_SBS_CLSD_PL')
	global_PVs['ExternalShutter_Trigger'] = PV('32idcTXM:shutCam:go')

	#fly macro
	global_PVs['Fly_ScanDelta'] = PV('32idcTXM:eFly:scanDelta')
	global_PVs['Fly_StartPos'] = PV('32idcTXM:eFly:startPos')
	global_PVs['Fly_EndPos'] = PV('32idcTXM:eFly:endPos')
	global_PVs['Fly_SlewSpeed'] = PV('32idcTXM:eFly:slewSpeed')
	global_PVs['Fly_Taxi'] = PV('32idcTXM:eFly:taxi')
	global_PVs['Fly_Run'] = PV('32idcTXM:eFly:fly')
	global_PVs['Fly_ScanControl'] = PV('32idcTXM:eFly:scanControl')
	global_PVs['Fly_Calc_Projections'] = PV('32idcTXM:eFly:calcNumTriggers')

	# theta controls
	global_PVs['Reset_Theta'] = PV('32idcTXM:SG_RdCntr:reset.PROC')
	global_PVs['Proc_Theta'] = PV('32idcTXM:SG_RdCntr:cVals.PROC')
	global_PVs['Theta_Array'] = PV('32idcTXM:eFly:motorPos.AVAL')
	global_PVs['Theta_Cnt'] = PV('32idcTXM:SG_RdCntr:aSub.VALB')

	#init misc pv's
	global_PVs['Image1_Callbacks'] = PV(variableDict['IOC_Prefix'] + 'image1:EnableCallbacks')
	global_PVs['ExternShutterExposure'] = PV('32idcTXM:shutCam:tExpose')
	global_PVs['SetSoftGlueForStep'] = PV('32idcTXM:SG3:MUX2-1_SEL_Signal')
	#global_PVs['ClearTheta'] = PV('32idcTXM:recPV:PV1_clear')
	global_PVs['ExternShutterDelay'] = PV('32idcTXM:shutCam:tDly')
	global_PVs['Interferometer'] = PV('32idcTXM:SG2:UpDnCntr-1_COUNTS_s')
	global_PVs['Interferometer_Update'] = PV('32idcTXM:SG2:UpDnCntr-1_COUNTS_SCAN.PROC')
	global_PVs['Interferometer_Reset'] = PV('32idcTXM:SG_RdCntr:reset.PROC')
	global_PVs['Interferometer_Cnt'] = PV('32idcTXM:SG_RdCntr:aSub.VALB')
	global_PVs['Interferometer_Arr'] = PV('32idcTXM:SG_RdCntr:cVals.AA')
	global_PVs['Interferometer_Proc_Arr'] = PV('32idcTXM:SG_RdCntr:cVals.PROC')
	global_PVs['Interferometer_Val'] = PV('32idcTXM:userAve4.VAL')
	global_PVs['Interferometer_Mode'] = PV('32idcTXM:userAve4_mode.VAL')
	global_PVs['Interferometer_Acquire'] = PV('32idcTXM:userAve4_acquire.PROC')

	#init proc1 pv's
	global_PVs['Proc1_Callbacks'] = PV(variableDict['IOC_Prefix'] + 'Proc1:EnableCallbacks')
	global_PVs['Proc1_ArrayPort'] = PV(variableDict['IOC_Prefix'] + 'Proc1:NDArrayPort')
	global_PVs['Proc1_Filter_Enable'] = PV(variableDict['IOC_Prefix'] + 'Proc1:EnableFilter')
	global_PVs['Proc1_Filter_Type'] = PV(variableDict['IOC_Prefix'] + 'Proc1:FilterType')
	global_PVs['Proc1_Num_Filter'] = PV(variableDict['IOC_Prefix'] + 'Proc1:NumFilter')
	global_PVs['Proc1_Reset_Filter'] = PV(variableDict['IOC_Prefix'] + 'Proc1:ResetFilter')
	global_PVs['Proc1_AutoReset_Filter'] = PV(variableDict['IOC_Prefix'] + 'Proc1:AutoResetFilter')
	global_PVs['Proc1_Filter_Callbacks'] = PV(variableDict['IOC_Prefix'] + 'Proc1:FilterCallbacks')

	#tiff writer pv's
	global_PVs['TIFF1_AutoSave'] = PV(variableDict['IOC_Prefix'] + 'TIFF1:AutoSave')
	global_PVs['TIFF1_DeleteDriverFile'] = PV(variableDict['IOC_Prefix'] + 'TIFF1:DeleteDriverFile')
	global_PVs['TIFF1_EnableCallbacks'] = PV(variableDict['IOC_Prefix'] + 'TIFF1:EnableCallbacks')
	global_PVs['TIFF1_BlockingCallbacks'] = PV(variableDict['IOC_Prefix'] + 'TIFF1:BlockingCallbacks')
	global_PVs['TIFF1_FileWriteMode'] = PV(variableDict['IOC_Prefix'] + 'TIFF1:FileWriteMode')
	global_PVs['TIFF1_NumCapture'] = PV(variableDict['IOC_Prefix'] + 'TIFF1:NumCapture')
	global_PVs['TIFF1_Capture'] = PV(variableDict['IOC_Prefix'] + 'TIFF1:Capture')
	global_PVs['TIFF1_FullFileName_RBV'] = PV(variableDict['IOC_Prefix'] + 'TIFF1:FullFileName_RBV')
	global_PVs['TIFF1_FileNumber'] = PV(variableDict['IOC_Prefix'] + 'TIFF1:FileNumber')
	global_PVs['TIFF1_FileName'] = PV(variableDict['IOC_Prefix'] + 'TIFF1:FileName')
	global_PVs['TIFF1_ArrayPort'] = PV(variableDict['IOC_Prefix'] + 'TIFF1:NDArrayPort')
	
	#energy
	global_PVs['DCMmvt'] = PV('32ida:KohzuModeBO.VAL')
	global_PVs['GAPputEnergy'] = PV('32id:ID32us_energy')
	global_PVs['EnergyWait'] = PV('ID32us:Busy')
	global_PVs['DCMputEnergy'] = PV('32ida:BraggEAO.VAL')

def stop_scan(global_PVs, variableDict):
	global_PVs['TIFF1_AutoSave'].put('No')
	global_PVs['TIFF1_Capture'].put(0)
	global_PVs['HDF1_Capture'].put(0)
	wait_pv(global_PVs['HDF1_Capture'], 0)
	reset_CCD(global_PVs, variableDict)

def reset_CCD(global_PVs, variableDict):
	global_PVs['Cam1_TriggerMode'].put('Internal', wait=True)
	global_PVs['Cam1_TriggerMode'].put('Overlapped', wait=True)
	global_PVs['Cam1_TriggerMode'].put('Internal', wait=True)
	global_PVs['Proc1_Filter_Callbacks'].put( 'Every array' )
	global_PVs['HDF1_ArrayPort'].put(global_PVs['Proc1_ArrayPort'].get())
	global_PVs['Cam1_ImageMode'].put('Continuous', wait=True)
	global_PVs['Cam1_Acquire'].put(DetectorAcquire); wait_pv(global_PVs['Cam1_Acquire'], DetectorAcquire, 2)

def setup_detector(global_PVs, variableDict):
	print 'setup_detector()'
	global_PVs['Cam1_ImageMode'].put('Multiple')
	global_PVs['Cam1_ArrayCallbacks'].put('Enable')
	#global_PVs['Image1_Callbacks'].put('Enable')
	global_PVs['Cam1_AcquirePeriod'].put(float(variableDict['ExposureTime']))
	global_PVs['Cam1_AcquireTime'].put(float(variableDict['ExposureTime']))
	# if we are using external shutter then set the exposure time
	global_PVs['SetSoftGlueForStep'].put('0')
	global_PVs['Cam1_FrameRateOnOff'].put(0)
	#if int(variableDict['ExternalShutter']) == 1:
	#	global_PVs['ExternShutterExposure'].put(float(variableDict['ExposureTime']))
	#	global_PVs['ExternShutterDelay'].put(float(variableDict['ShutterOpenDelay']))
	#	global_PVs['SetSoftGlueForStep'].put('1')
	# if software trigger capture two frames (issue with Point grey grasshopper)
	if PG_Trigger_External_Trigger == 1:
		wait_time_sec = int(variableDict['ExposureTime']) + 5
		global_PVs['Cam1_TriggerMode'].put('Overlapped', wait=True) #Ext. Standard
		global_PVs['Cam1_NumImages'].put(1, wait=True)
		global_PVs['Cam1_Acquire'].put(DetectorAcquire)
		wait_pv(global_PVs['Cam1_Acquire'], DetectorAcquire, 2)
		global_PVs['Cam1_SoftwareTrigger'].put(1)
		wait_pv(global_PVs['Cam1_Acquire'], DetectorIdle, wait_time_sec)
		global_PVs['Cam1_Acquire'].put(DetectorAcquire)
		wait_pv(global_PVs['Cam1_Acquire'], DetectorAcquire, 2)
		global_PVs['Cam1_SoftwareTrigger'].put(1)
		wait_pv(global_PVs['Cam1_Acquire'], DetectorIdle, wait_time_sec)
	else:
		global_PVs['Cam1_TriggerMode'].put('Internal')
	#global_PVs['ClearTheta'].put(1)


def setup_writer(global_PVs, variableDict, filename=None):
	print 'setup_writer()'
	if variableDict.has_key('Recursive_Filter_Enabled'):
		if variableDict['Recursive_Filter_Enabled'] == 1:
#			global_PVs['Proc1_Callbacks'].put('Disable')
			global_PVs['Proc1_Callbacks'].put('Enable')
			global_PVs['Proc1_Filter_Enable'].put('Disable')
			global_PVs['HDF1_ArrayPort'].put('PROC1')
			global_PVs['Proc1_Filter_Type'].put( Recursive_Filter_Type )
			global_PVs['Proc1_Num_Filter'].put( int( variableDict['Recursive_Filter_N_Images'] ) )
			global_PVs['Proc1_Reset_Filter'].put( 1 )
			global_PVs['Proc1_AutoReset_Filter'].put( 'Yes' )
			global_PVs['Proc1_Filter_Callbacks'].put( 'Array N only' )
		else:
#			global_PVs['Proc1_Callbacks'].put('Disable')
			global_PVs['Proc1_Filter_Enable'].put('Disable')
			global_PVs['HDF1_ArrayPort'].put(global_PVs['Proc1_ArrayPort'].get())
	else:
#		global_PVs['Proc1_Callbacks'].put('Disable')
		global_PVs['Proc1_Filter_Enable'].put('Disable')
		global_PVs['HDF1_ArrayPort'].put(global_PVs['Proc1_ArrayPort'].get())
	global_PVs['HDF1_AutoSave'].put('Yes')
	global_PVs['HDF1_DeleteDriverFile'].put('No')
	global_PVs['HDF1_EnableCallbacks'].put('Enable')
	global_PVs['HDF1_BlockingCallbacks'].put('No')
	totalProj = int(variableDict['PreDarkImages']) + int(variableDict['PreWhiteImages']) + int(variableDict['Projections']) + int(variableDict['PostDarkImages']) + int(variableDict['PostWhiteImages'])
	global_PVs['HDF1_NumCapture'].put(totalProj)
	global_PVs['HDF1_FileWriteMode'].put(str(variableDict['FileWriteMode']), wait=True)
	if not filename == None:
		global_PVs['HDF1_FileName'].put(filename)
	global_PVs['HDF1_Capture'].put(1)
	wait_pv(global_PVs['HDF1_Capture'], 1)

def capture_multiple_projections(global_PVs, variableDict, num_proj, frame_type):
	print 'capture_multiple_projections(', num_proj, ')'
	wait_time_sec = int(variableDict['ExposureTime']) + 5
	global_PVs['Cam1_ImageMode'].put('Multiple')
	global_PVs['Cam1_FrameType'].put(frame_type)
	if PG_Trigger_External_Trigger == 1:
		#set external trigger mode
		global_PVs['Cam1_TriggerMode'].put('Overlapped', wait=True)
		global_PVs['Cam1_NumImages'].put(1)
		for i in range(int(num_proj)):
			global_PVs['Cam1_Acquire'].put(DetectorAcquire)
			wait_pv(global_PVs['Cam1_Acquire'], DetectorAcquire, 2)
			global_PVs['Cam1_SoftwareTrigger'].put(1)
			wait_pv(global_PVs['Cam1_Acquire'], DetectorIdle, wait_time_sec)

	else:
		global_PVs['Cam1_TriggerMode'].put('Internal')
		global_PVs['Cam1_NumImages'].put(int(num_proj))
		global_PVs['Cam1_Acquire'].put(DetectorAcquire, wait=True)
		wait_pv(global_PVs['Cam1_Acquire'], DetectorIdle, wait_time_sec)


def move_sample_in(global_PVs, variableDict):
	print 'move_sample_in()'
#	global_PVs['Motor_X_Tile'].put(float(variableDict['SampleXIn']), wait=True)
	global_PVs['Motor_SampleX'].put(float(variableDict['SampleXIn']), wait=True)
#	global_PVs['Motor_SampleY'].put(float(variableDict['SampleYIn']), wait=True)
#	global_PVs['Motor_SampleZ'].put(float(variableDict['SampleZIn']), wait=True)
	global_PVs['Motor_SampleRot'].put(0, wait=True)


def move_sample_out(global_PVs, variableDict):
	print 'move_sample_out()'
#	global_PVs['Motor_SampleRot'].put(float(variableDict['SampleRotOut']), wait=True)
#	global_PVs['Motor_X_Tile'].put(float(variableDict['SampleXOut']), wait=True)
	global_PVs['Motor_SampleX'].put(float(variableDict['SampleXOut']), wait=True)
#	global_PVs['Motor_SampleY'].put(float(variableDict['SampleYOut']), wait=True)
#	global_PVs['Motor_SampleZ'].put(float(variableDict['SampleZOut']), wait=True)
	global_PVs['Motor_SampleRot'].put(0, wait=True)

def open_shutters(global_PVs, variableDict):
	print 'open_shutters()'
	if UseShutterA > 0:
		global_PVs['ShutterA_Open'].put(1, wait=True)
		wait_pv(global_PVs['ShutterA_Move_Status'], ShutterA_Open_Value)
	if UseShutterB > 0:
		global_PVs['ShutterB_Open'].put(1, wait=True)
		wait_pv(global_PVs['ShutterB_Move_Status'], ShutterB_Open_Value)


def close_shutters(global_PVs, variableDict):
	print 'close_shutters()'
	if UseShutterA > 0:
		global_PVs['ShutterA_Close'].put(1, wait=True)
		wait_pv(global_PVs['ShutterA_Move_Status'], ShutterA_Close_Value)
	if UseShutterB > 0:
		global_PVs['ShutterB_Close'].put(1, wait=True)
		wait_pv(global_PVs['ShutterB_Move_Status'], ShutterB_Close_Value)


def add_theta(global_PVs, variableDict, theta_arr):
	print 'add_theta()'
	fullname = global_PVs['HDF1_FullFileName_RBV'].get(as_string=True)
	try:
		hdf_f = h5py.File(fullname, mode='a')
		if theta_arr != None:
			theta_ds = hdf_f.create_dataset('/exchange/theta', (len(theta_arr),))
			theta_ds[:] = theta_arr[:]
		hdf_f.close()
	except:
		traceback.print_exc(file=sys.stdout)


def add_extra_hdf5(global_PVs, variableDict, theta_arr, interf_arrs):
	print 'add_extra_hdf5()'
	wait_pv(global_PVs['HDF1_Capture_RBV'], 0, 10.0)
	fullname = global_PVs['HDF1_FullFileName_RBV'].get(as_string=True)
	try:
		print 'Opening hdf5 file ',fullname
		hdf_f = h5py.File(fullname, mode='a')
		theta_ds = hdf_f.create_dataset('/exchange/theta', (len(theta_arr),))
		theta_ds[:] = theta_arr[:]
		if variableDict.has_key('UseInterferometer') and int(variableDict['UseInterferometer']) > 0:
			interf_ds = hdf_f.create_dataset('/exchange/interferometer', (len(interf_arrs), len(interf_arrs[0])), dtype='f' )
			for i in range(len(interf_arrs)):
				if len(interf_arrs[i]) == len(interf_arrs[0]):
					interf_ds[i,:] = interf_arrs[i][:]
		hdf_f.close()
	except:
		traceback.print_exc(file=sys.stdout)


def move_dataset_to_run_dir(global_PVs, variableDict):
	print 'move_dataset_to_run_dir()'
	try:
		txm_ui = imp.load_source('txm_ui', '/local/usr32idc/DMagic/doc/demo/txm_ui.py')
		run_dir = txm_ui.directory()
		full_path = global_PVs['HDF1_FullFileName_RBV'].get(as_string=True)
		base_name = os.path.basename(full_path)
		run_full_path = run_dir + '/' + base_name
		shutil.move(full_path, run_full_path)
	except:
		print 'error moving dataset to run directory'

def move_energy(energy, global_PVs, variableDict):
	print 'move_energy()', energy
	prev_energy = float(global_PVs['DCMputEnergy'].get())
	curr_CCD_location = float(global_PVs['CCD_Motor'].get())

	landa = 1240.0 / (prev_energy * 1000.0)
	ZP_focal = ZP_diameter * drn / (1000.0 * landa)
	D = (curr_CCD_location + math.sqrt(curr_CCD_location * curr_CCD_location - 4.0 * curr_CCD_location * ZP_focal) ) / 2.0
	Mag = (D - ZP_focal) / ZP_focal
	print 'mag', Mag
	global_PVs['DCMmvt'].put(1)

	landa = 1240.0 / (energy * 1000.0)
	ZP_focal = ZP_diameter * drn / (1000.0 * landa)
	dist_ZP_ccd = Mag * ZP_focal + ZP_focal
	ZP_WD = dist_ZP_ccd * ZP_focal / (dist_ZP_ccd - ZP_focal)
	CCD_location = ZP_WD + dist_ZP_ccd
	print 'move ccd ', CCD_location
	global_PVs['CCD_Motor'].put(CCD_location, wait=True)
	print 'move zp ', ZP_WD
	global_PVs['ZpLocation'].put(ZP_WD, wait=True)

	global_PVs['DCMputEnergy'].put(energy, wait=True)

	global_PVs['GAPputEnergy'].put(energy)
	wait_pv(global_PVs['EnergyWait'], 0)
	global_PVs['GAPputEnergy'].put(energy + float(variableDict['Offset']))
	wait_pv(global_PVs['EnergyWait'], 0)
	global_PVs['DCMmvt'].put(0)



########################## Interlaced #########################
def bitreversed_decimal(dec_input, maxbits):
# Description: Compute bit-reversed value of a decimal number 
# Inputs:
# in - Decimal input whose bit-reversed value must be computed
# maxbits - Total number of bits in binary used to represent 'in' and 'out'.
# Ouputs:
# out - Bit-reversed value of 'in'.

    if maxbits == 0:
        bit_rev = 0
        return

#    dec_input = bin(dec_input, maxbits)
    dec_input = int(dec_input)
    maxbits = int(maxbits)
    
    dec_input = bin(dec_input)
    dec_input = dec_input[2:]
    if len(dec_input)<maxbits:
        dec_input = '0'*(maxbits-len(dec_input))+dec_input
#    bit_rev = '0'*maxbits
    bit_rev = str('')
    for i in range(0,maxbits):
#        print('  ** Loop #',i)
#        print('       maxbits: ', maxbits)
#        print('       dec_input', dec_input)
        bit_rev = bit_rev + dec_input[maxbits-1-i]
#        print('       bit_rev: ', bit_rev)
    
    bit_rev = int(bit_rev,2)

    return bit_rev
    

def gen_interlaced_views(N, K, N_p):
# Description: Generate interlaced view angles
# Formula: the_views[n] = [(n mod(N/K))K + Br(floor(nK/N) mod(K))]*pi/N;
#          mod denotes modulo, floor gives the lowest integer value, Br denotes bit-reversal 
# Input: 
# N - Total number of distinct view angles in a frame
# K - Number of interlaced sub-frames in each frame
# N_p - Total number of view angles (Note that angles repeat from frame to frame)
# Output:
# the_views - Interlaced view angles

    k = int(np.log2(K))
    L = N/K # Number of equi-spaced view angles in a sub-frame
    delta_theta = 180/N # Determines scaling of output
    
#    print(k, L, K)
    
    the_views = np.zeros((N_p))
    buf1 = np.zeros((N_p))
    buf2 = np.zeros((N_p))
    
    for i in range(0,N_p):
#        print('**** Main loop #', i)
        buf1[i] = np.mod(i,L)*K
        buf2[i] = bitreversed_decimal(np.mod(np.floor(i/L), K), k)
        the_views[i] = buf1[i] + buf2[i]
        the_views[i] = the_views[i]*delta_theta
    
    return the_views


## Example:
#N_theta = 16 # Total number of distinct view angles in a frame
#K = 4 # Number of interlaced sub-frames in each frame
#N_p = 32 # Total number of view angles (Note that angles repeat from frame to frame)

#the_views = gen_interlaced_views(N_theta, K, N_p)
#
#X = np.linspace(0,N_p-1)
##plt.plot(X, the_views, 'o'), plt.plot(the_views, 'ro'), plt.plot(the_views, 'b-'), plt.grid(), plt.xlabel('View index'), plt.ylabel('View angle (degrees)'), plt.title('Interlaced views'), plt.show()
########################## Interlaced #########################