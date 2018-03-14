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
import tomo_step_scan

global variableDict

variableDict = {'PreDarkImages': 1,
                'PreWhiteImages': 1,
                'Projections': 1500,
		'ProjectionsPerRot': 1,
                'PostDarkImages': 1,
                'PostWhiteImages': 1,
                'SampleXOut':  -5.0,
#                'SampleYOut': 0.0,
                'SampleXIn': 0.0,
#                'SampleYIn': -10.0,
                'SampleStart_Rot': 0.0,
                'SampleEnd_Rot': 180.0,
                'StartSleep_min': 0,
                'StabilizeSleep_ms': 0,
                'ExposureTime': 0.1,
                'CCD_Readout': 0.27,
                'IOC_Prefix': '2bmbPG1:',
                'FileWriteMode': 'Stream',
                'X_Start': 0.0,
                'X_NumTiles': 1,
                'X_Stop': 0.0,
                'Y_Start': 0.0,
                'Y_NumTiles': 4,
                'Y_Stop': 4.0,
#		'Interlaced': 0,
#		'Interlaced_Sub_Cycles': 4,
#		'rot_speed_deg_per_s': 0.5,
#		'Recursive_Filter_Enabled': 0,
#		'Recursive_Filter_N_Images': 2,
#		'Recursive_Filter_Type': 'RecursiveAve'
#                'SampleMoveSleep': 0.0,
                'MosaicMoveSleep': 0.0,
                'Display_live': 0
                #'UseInterferometer': 0
                }



global_PVs = {}

def getVariableDict():
	return variableDict

def main():
    update_variable_dict(variableDict)
    init_general_PVs(global_PVs, variableDict)
    if variableDict.has_key('StopTheScan'):
        stop_scan(global_PVs, variableDict)
        return
    FileName = global_PVs['HDF1_FileName'].get(as_string=True)
    FileTemplate = global_PVs['HDF1_FileTemplate'].get(as_string=True)
    global_PVs['HDF1_FileTemplate'].put('%s%s.h5')
    if int(variableDict['Y_NumTiles']) <= 1:
        y_itr = 0.0
    else:
        y_itr = ((float(variableDict['Y_Stop']) - float(variableDict['Y_Start'])) / (float(variableDict['Y_NumTiles']) - 1))
    if int(variableDict['X_NumTiles']) <= 1:
        x_itr = 0.0
    else:
        x_itr = ((float(variableDict['X_Stop']) - float(variableDict['X_Start'])) / (float(variableDict['X_NumTiles']) - 1))
    y_val = float(variableDict['Y_Start'])
    for y in range( int(variableDict['Y_NumTiles']) ):
        x_val = float(variableDict['X_Start'])
        global_PVs['Motor_SampleY'].put(y_val, wait=True, timeout=600.0)
        #print 'sleep', float(variableDict['MosaicMoveSleep'])
        #time.sleep(float(variableDict['MosaicMoveSleep']))
        #wait_pv(global_PVs["Motor_Y_Tile"], y_val, 600)
        y_val += y_itr
        for x in range( int(variableDict['X_NumTiles']) ):
            print( y_val, x_val)
            global_PVs["Motor_SampleX"].put(x_val, wait=True, timeout=600.0)
            print('sleep', float(variableDict['MosaicMoveSleep']))
            time.sleep(float(variableDict['MosaicMoveSleep']))
            #wait_pv(global_PVs["Motor_X_Tile"], x_val, 600)
            x_val += x_itr
            tomo_step_scan.full_tomo_scan(variableDict, FileName+'_y' + str(y) + '_x' + str(x) )
    global_PVs['HDF1_FileName'].put(FileName)
    global_PVs['HDF1_FileTemplate'].put('%s%s_%3.3d.h5')


if __name__ == '__main__':
    main()

