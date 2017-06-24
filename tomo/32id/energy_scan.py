#######################
##### To be tested!

'''For each energy step, a projection and then a flat field is being
acquired. The script calls the move move_energy function from
tomo_scan_lib.

'''

import sys
import json
import time
import shutil
import os
import imp
import traceback
import math
import logging

import h5py
from epics import PV
from tomo_scan_lib import *
from txm import TXM

global variableDict
variableDict = {
    'PreDarkImages': 0,
    'SampleXOut': 0.0,
    'SampleYOut': 0.0,
    'SampleXIn': 0.0,
    'SampleYIn': 0.0,
    'StartSleep_min': 0,
    'StabilizeSleep_ms': 1000,
    'ExposureTime': 0.5,
    'IOC_Prefix': '32idcPG3:',
    'FileWriteMode': 'Stream',
    'Energy_Start': 6.7,
    'Energy_End': 6.8,
    'Energy_Step': 0.001,
    'ZP_diameter': 180,
    'drn': 60,
    'constant_mag': 1, # 1 means CCD will move to maintain constant magnification
    'Offset': 0.15,
    # 'BSC_diameter': 1320,
    # 'BSC_drn': 60
}

log = logging.getLogger(__name__)

global_PVs = {}


def getVariableDict():
    global variableDict
    return variableDict


def energy_scan(txm):
    """Conduct a scan across a range of X-ray energies.
    
    At each energy collect micrographs.
    
    Parameters
    ----------
    txm : TXM
      An instance of the TXM() class.
    """
    log.debug("energy_scan() called.")
    # Extract variables from variableDict:
    Energy_Start = float(variableDict['Energy_Start'])
    Energy_End = float(variableDict['Energy_End'])
    Energy_Step = float(variableDict['Energy_Step'])
    ZP_diameter = float(variableDict['ZP_diameter'])
    Offset = float(variableDict['Offset'])
    drn = float(variableDict['drn'])
    
    StabilizeSleep_ms = float(variableDict['StabilizeSleep_ms'])
    
    global_PVs['Cam1_NumImages'].put(1, wait=True)
    global_PVs['DCMmvt'].put(1, wait=True)
    log.debug("Setting initial energy to %f", Energy_Start)
    global_PVs['GAPputEnergy'].put(Energy_Start, wait=True)
    wait_pv(global_PVs['EnergyWait'], 0.05)
    energy = Energy_Start
    num_iters = int( (Energy_End - Energy_Start) / Energy_Step ) +1
    log.info('Capturing %d energies', num_iters)
    for i in range(num_iters):
        log.debug('Capturing energy: %f kEV', energy)
        log.debug('Stabilize Sleep %f ms', StabilizeSleep_ms)
        time.sleep(StabilizeSleep_ms / 1000.0)
        
        variableDict.update({'new_Energy': energy})
        # Call move energy function: adjust ZP (& CCD position if constant mag is checked)
        move_energy(global_PVs, variableDict)
        
        log.debug('Stabilize Sleep %f ms', StabilizeSleep_ms)
        time.sleep(StabilizeSleep_ms / 1000.0)
        
        # save theta to array
        energy_arr += [energy]
        
        # Sample projection acquisition:
        #-------------------------------
        # Prepare datatype for the hdf5 file: next proj will be a sample proj
        global_PVs['Cam1_FrameType'].put(FrameTypeData, wait=True)
        # start detector acquire
        global_PVs['Cam1_Acquire'].put(DetectorAcquire, wait=True)
        # wait for acquire to finish
        wait_pv(global_PVs['Cam1_Acquire'], DetectorIdle)
        
        # Flat-field projection acquisition:
        #-------------------------------
        move_sample_out()
        # Prepare datatype for the hdf5 file: next proj will be a flat-field
        global_PVs['Cam1_FrameType'].put(FrameTypeWhite, wait=True)
        # start detector acquire
        global_PVs['Cam1_Acquire'].put(DetectorAcquire, wait=True)
        # wait for acquire to finish
        wait_pv(global_PVs['Cam1_Acquire'], DetectorIdle)
        move_sample_in()
        
        # update Energy to the next one
        energy += Energy_Step
        
    global_PVs['DCMmvt'].put(0)
    return energy_arr


def add_energy_arr(energy_arr):
    log.debug('add_energy_arr() called')
    fullname = global_PVs['HDF1_FullFileName_RBV'].get(as_string=True)
    try:
        hdf_f = h5py.File(fullname)
        energy_ds = hdf_f.create_dataset('/exchange/energy', (len(energy_arr),))
        energy_ds[:] = energy_arr[:]
        hdf_f.close()
    except:
        traceback.print_exc(file=sys.stdout)


def start_scan(txm):
    log.debug('start_scan() called')
    if 'StopTheScan' in variableDict.keys(): # stopping the scan in a clean way
        stop_scan(global_PVs, variableDict)
        return
    # Start scan sleep in min so min * 60 = sec
    log.debug("Sleeping for %f min", float(variableDict['StartSleep_min']))
    time.sleep(float(variableDict['StartSleep_min']) * 60.0)
    # setup_writer(global_PVs, variableDict)
    txm.setup_writer(variableDict)
    if int(variableDict['PreDarkImages']) > 0:
        close_shutters(global_PVs, variableDict)
        log.info('Capturing Pre Dark Field')
        capture_multiple_projections(int(variableDict['PreDarkImages']), FrameTypeDark)
    sample_pos = (variableDict.get('SampleXIn', None),
                  variableDict.get('SampleYIn', None),
                  variableDict.get('SampleZIn', None))
    txm.move_sample(*sample_pos)
    # move_sample_in(global_PVs, variableDict)
    txm.open_shutters()
    # open_shutters(global_PVs, variableDict)
    energy_arr = []
    # global_PVs['Cam1_FrameType'].put(FrameTypeWhite, wait=True)
    energy_arr += energy_scan(txm)
    # move_sample_out()
    # global_PVs['Cam1_FrameType'].put(FrameTypeData, wait=True)
    # energy_scan()
    close_shutters()
    add_energy_arr(energy_arr)
    # move_dataset_to_run_dir()


def main():
    update_variable_dict()
    # Create the microscope object
    txm = TXM()
    start_scan(txm=txm)


if __name__ == '__main__':
    # Set up default stream logging
    # Choices are DEBUG, INFO, WARNING, ERROR, CRITICAL
    logging.basicConfig(level=logging.DEBUG)
    # Enter the main script function
    main()
