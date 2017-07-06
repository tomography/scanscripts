'''
	TomoScan for Sector 32 ID C

'''
#import sys
#import json
import time
from epics import PV
#import h5py
#import shutil
#import os
#import imp
#import traceback
import math

from tomo_scan_lib import *
global variableDict

variableDict = {'new_Energy': 7.8, # keV
                'constant_mag': 0, # 1 means magnification will be maintained adjusting CCD location
                'ZP_diameter': 180.0, # um
                'drn': 60.0, # nm
                'Offset': 0.15, # keV
                'IOC_Prefix': '32idcPG3:'
				}

global_PVs = {}

def getVariableDict():
	global variableDict
	return variableDict

#def move_energy():
#    
#	global_PVs['DCMmvt'].put(1)
#
#    # Extract variables from variableDict:
#	constant_mag = int(variableDict['constant_mag'])
#	new_Energy = float(variableDict['new_Energy'])
#	ZP_diameter = float(variableDict['ZP_diameter'])
#	Offset = float(variableDict['Offset'])
#	drn = float(variableDict['drn'])
#    
#	print 'move to a new energy:%3.3f' % new_Energy
#	energy_init = global_PVs['DCMputEnergy'].get() # energy before changing
#	landa_init = 1240.0 / (energy_init * 1000.0)
#	ZP_focal = ZP_diameter * drn / (1000.0 * landa_init)
#	curr_CCD_location = float(global_PVs['CCD_Motor'].get())
#	D_init = (curr_CCD_location + math.sqrt(curr_CCD_location * curr_CCD_location - 4.0 * curr_CCD_location * ZP_focal) ) / 2.0
#	new_landa = 1240.0 / (new_Energy * 1000.0)
#	ZP_focal = ZP_diameter * drn / (1000.0 * new_landa)
#	
#	if constant_mag: # CCD will move to maintain magnification during energy change
#        
#        	Mag = (D_init - ZP_focal) / ZP_focal
#        	print 'mag', Mag
#        
#        	dist_ZP_ccd = Mag * ZP_focal + ZP_focal
#        	ZP_WD = dist_ZP_ccd * ZP_focal / (dist_ZP_ccd - ZP_focal)
#        	CCD_location = ZP_WD + dist_ZP_ccd
#        	print 'move ccd ', CCD_location
#        	global_PVs['CCD_Motor'].put(CCD_location, wait=True)
#        	print 'move zp ', ZP_WD
#        	global_PVs['ZpLocation'].put(ZP_WD, wait=True)
#
#	else: # no constant magnification, i.e. CCD will not move
#        	
#        	D_new = (curr_CCD_location + math.sqrt(curr_CCD_location * curr_CCD_location - 4.0 * curr_CCD_location * ZP_focal) ) / 2.0
#        	ZP_WD = D_new * ZP_focal / (D_new - ZP_focal)
#        	print 'move zp ', ZP_WD
#        	global_PVs['ZpLocation'].put(ZP_WD, wait=True)
#
#	global_PVs['DCMputEnergy'].put(energy, wait=True)
#
#	global_PVs['GAPputEnergy'].put(energy)
#	wait_pv(global_PVs['EnergyWait'], 0)
#	global_PVs['GAPputEnergy'].put(energy + Offset)
#	wait_pv(global_PVs['EnergyWait'], 0)
#	global_PVs['DCMmvt'].put(0)


def start_scan():
	print 'start_scan()'
    	init_general_PVs(global_PVs, variableDict)
	move_energy(global_PVs, variableDict)

def main():
	update_variable_dict(variableDict)
	start_scan()

if __name__ == '__main__':
	main()
