# -*- coding: utf-8 -*-
#######################

'''For each energy step, a projection and then a flat field are
acquired. The script calls the move_energy method from the TXM class.

'''

import time
import os
import logging
import warnings

import numpy as np
import h5py
import tqdm
from scanlib.scan_variables import update_variable_dict, parse_list_variable
from scanlib.tools import energy_range_from_points, loggingConfig
from aps_32id.txm import new_txm

__author__ = 'Mark Wolfman'
__copyright__ = 'Copyright (c) 2017, UChicago Argonne, LLC.'
__docformat__ = 'restructuredtext en'
__platform__ = 'Unix'
__all__ = ['run_energy_scan', 'getVariableDict']


variableDict = {
    'PreDarkImages': 0,
    'SampleXOut': 0.0,
    'SampleYOut': 0.0,
    'SampleZOut': 0.0,
    'SampleRotOut': 0.0, # In degrees
    'SampleXIn': 0.0,
    'SampleYIn': 0.0,
    'SampleZIn': 0.0,
    'SampleRotIn': 0.0, # In degrees
    'StartSleep_min': 0.0,
    'StabilizeSleep_ms': 3000,
    'ExposureTime': 1,
#    'Energy_limits': '7.100, 7.110, 7.117, 7.130, 7.150, 7.200',
#    'Energy_Step': '0.003, 0.001, 0.0005, 0.001, 0.003',
#    'Energy_limits': '11.05, 11.075, 11.15, 11.2',
#    'Energy_limits': '8.3, 8.34, 8.37, 8.4',
    'Energy_limits': '8.3, 8.305, 8.31', # for quick test
    'Energy_Step': '0.002, 0.002',
    'ZP_X_drift': 0.,
    'constant_mag': False, # will CCD move to maintain constant magnification?
    # 'BSC_diameter': 1320,
    # 'BSC_drn': 60
    'Repetitions': 1,
    'Pause': 0.01, # in minutes
    'Use_Fast_Shutter': 1,
    # Logging: 0=UNSET, 10=DEBUG, 20=INFO, 30=WARNING, 40=ERROR, 50=CRITICAL
    'Log_Level': logging.INFO,
}

SHUTTER_PERMIT = False

log = logging.getLogger(__name__)


def getVariableDict():
    return variableDict


def _capture_energy_frames(txm, energies, constant_mag,
                           stabilize_sleep_ms, sample_pos, out_pos, ZP_X_drift_array):
    """A helper method for collected a set of energy frames.
    
    The TXM should already be set up before calling this function.

    Parameters
    ----------
    txm :
      A NanoTXM or MicroCT object that this script will control.
    energies : np.ndarray
      An array with the energies (in keV) for capturing frames.
    constant_mag : bool
      Whether to move the detector at each energy to keep the
      magnification constant.
    stabilize_sleep_ms : int
      How long to wait after moving energy to allow the beamline
      (monochromator, etc.) to stabilize.
    sample_pos : 4-tuple
      (x, y, z, θ°) with the position for the sample.
    out_pos : 4-tuple
      (x, y, z, θ°) with the position for the flat field.
    ZP_X_drift_array : np.ndarray
      Each entry is the change in x position of the zoneplate needed
      to keep the sample centered at that energy.

    """
    correct_backlash = True # First energy only
    for idx, energy in enumerate(tqdm.tqdm(energies, "Energy scan")):
        log.debug('Preparing to capture energy: %f keV', energy)
        # Check whether we should collect the sample or white field first 
        sample_first = not bool(idx % 2)
        log.info("Collecting %s first.", "sample" if sample_first else "white-field")
        # Move sample, zone plate and energy
        txm.zone_plate_x = ZP_X_drift_array[idx]
        if sample_first:
            txm.move_sample(*sample_pos)
        else:
            txm.move_sample(*out_pos)
        txm.move_energy(energy, constant_mag=constant_mag,
                        correct_backlash=correct_backlash)
        correct_backlash = False # Needed on first energy only
        # Pause for a moment to allow the beam to stabilize
        log.debug('Stabilize Sleep %f ms', stabilize_sleep_ms)
        time.sleep(stabilize_sleep_ms / 1000.0)
        # Sample projection acquisition (or white-field on odd passes)
        if sample_first:
            log.info("Acquiring sample position %s at %.4f eV", sample_pos, energy)
            txm.capture_projections()
        else:
            log.info("Acquiring white-field position %s at %.4f eV", out_pos, energy)
            txm.capture_white_field()
        # Flat-field projection acquisition (or sample on odd passes)
        if sample_first:
            txm.move_sample(*out_pos)
            log.info("Acquiring white-field position %s at %.4f eV", out_pos, energy)
            # time.sleep(3)
            txm.capture_white_field()
        else:
            txm.move_sample(*sample_pos)
            log.info("Acquiring sample position %s at %.4f eV", sample_pos, energy)
            txm.capture_projections()


def run_energy_scan(energies, exposure=0.5, n_pre_dark=5,
                    has_permit=True, sample_pos=(0.,), out_pos=(0.2,),
                    ZP_X_drift_array=None,
                    constant_mag=True, stabilize_sleep_ms=1000,
                    repetitions=1,
                    pause=0,
                    use_fast_shutter=True,
                    log_level=logging.INFO,
                    txm=None):
    """Collect a series of 2-dimensional projections across a range of energies.
    
    At each position, a sample projection and white-field projection
    will be collected by moving the sample along the X direction.
    
    Parameters
    ----------
    energies : np.ndarray
      An array with the list of energies to scan, in keV.
    exposure : float, optional
      How long to collect each frame for, in seconds.
    n_pre_dark : int, optional
      How many dark-field projections to collect before starting the
      energy scan.
    is_attached : bool, optional
      Determines whether the instrument is available.
    has_permit : bool, optional
      Does the user have permission to open the shutters and change
      source energy.
    sample_pos : 4-tuple, optional
      (x, y, z, θ) tuple for positioning the sample in the beam.
    out_pos : 4-tuple, optional
      (x, y, z, θ) tuple for removing the sample from the beam.
    ZP_X_drift_array : np.ndarray, optional
      Each entry is the change in x position of the zoneplate needed
      to keep the sample centered at that energy.
    constant_mag : bool, optional
      Whether to adjust the camera position to maintain a constant
      focus.
    stabilize_sleep_ms : int, optional
      How long, in milliseconds, to wait for the beam to stabilize
      before collecting projections.
    repetitions : int, optional
      How many times to run this energy scan, including the first one.
    pause : int, optional
      How long, in minute, the scan pause in between each energy scan repetition
    use_fast_shutter : bool, optional
      Whether to open and shut the fast shutter before triggering
      projections.
    log_level : int, optional
      Temporary log level to use. ``None`` does not change the logging.
    txm : optional
      An instance of the NanoTXM class. If not given, a new one will
      be created. Mostly used for testing.
    
    """
    log.debug("Starting run_energy_scan()")
    start_time = time.time()
    total_projections = n_pre_dark + 2 * len(energies)
    # Fix up default parameters
    if ZP_X_drift_array is None:
        ZP_X_drift_array = np.zeros_like(energies)
    elif ZP_X_drift_array.shape != energies.shape:
        raise ValueError("ZP_X_drift_array shape does not match energies: "
                         "{} vs {}".format(ZP_X_drift_array.shape, energies.shape))
    log.debug('ZP x-drift corrections: {}'.format(ZP_X_drift_array))
    # Create the TXM object for this scan
    if txm is None:
        txm = new_txm()
    # Execute the actual scan script
    with txm.run_scan():
        if use_fast_shutter:
            txm.enable_fast_shutter()
        # Prepare TXM for capturing data
        txm.setup_detector(exposure=exposure,
                           num_projections=total_projections)
        # Collect repetitions of the energy scan
        for rep in range(repetitions):
            time.sleep(pause * 60.0) # convert min to sec
            txm.setup_hdf_writer(num_projections=total_projections)
            time.sleep(5)
            txm.start_logging(log_level)
            # Capture pre dark field images
            if n_pre_dark > 0:
                txm.close_shutters()
                log.info('Capturing %d Pre Dark Field images', n_pre_dark)
                txm.capture_dark_field(num_projections=n_pre_dark)
            # Calculate the array of energies that will be scanned
            log.info('Capturing %d energies', len(energies))
            # Collect frames at each energy
            txm.open_shutters()
            _capture_energy_frames(txm=txm, energies=energies,
                                   constant_mag=constant_mag,
                                   stabilize_sleep_ms=stabilize_sleep_ms,
                                   sample_pos=sample_pos, out_pos=out_pos,
                                   ZP_X_drift_array=ZP_X_drift_array)
            txm.close_shutters()
            # Add the energy array to the active HDF file
            hdf_filename = txm.hdf_filename
            print ('1', hdf_filename)
    try:
        print ('2', hdf_filename)
        with txm.hdf_file(hdf_filename, mode="r+") as hdf_f:
            log.debug('Saving energies to file: %s', hdf_filename)
            hdf_f.create_dataset('/exchange/energy',
                                 data=energies)
    except (OSError, IOError):
        # Could not load HDF file, so raise a warning
        msg = "Could not save energies to file %s" % hdf_filename
        warnings.warn(msg, RuntimeWarning)
        log.warning(msg)
    # Log the duration and output file
    duration = time.time() - start_time
    log.info('Energy scan took %d sec and saved in file %s',
             duration, hdf_filename)
    return txm


def main():
    # Enter the main script function
    update_variable_dict(variableDict)
    # Set up default logging
    # Choices are DEBUG, INFO, WARNING, ERROR, CRITICAL
    # logging.basicConfig(level=logging.WARNING)
    log_level = variableDict['Log_Level']
    loggingConfig(level=log_level)
    # Get the requested sample positions
    sample_pos = (variableDict.get('SampleXIn', None),
                  variableDict.get('SampleYIn', None),
                  variableDict.get('SampleZIn', None),
                  variableDict.get('SampleRotIn', None))
    out_pos = (variableDict.get('SampleXOut', None),
               variableDict.get('SampleYOut', None),
               variableDict.get('SampleZOut', None),
               variableDict.get('SampleRotOut', None))    
    # Prepare the list of energies requested
    energy_limits = parse_list_variable(variableDict['Energy_limits'], dtype=float)
    energy_steps = parse_list_variable(variableDict['Energy_Step'], dtype=float)
    energies = energy_range_from_points(energy_points=energy_limits,
                                        energy_steps=energy_steps)
    ZP_X_drift = float(variableDict['ZP_X_drift'])
    ZP_X_drift_array = (energies-energies[0]) * ZP_X_drift / (energies[-1]-energies[0])
    # Start scan sleep in min so min * 60 = sec
    sleep_min = float(variableDict.get('StartSleep_min', 0))
    stabilize_sleep_ms = float(variableDict.get("StabilizeSleep_ms"))
    repetitions = int(variableDict['Repetitions'])
    pause = float(variableDict['Pause'])
    constant_mag = bool(variableDict['constant_mag'])
    use_fast_shutter = bool(int(variableDict['Use_Fast_Shutter']))
    if sleep_min > 0:
        log.debug("Sleeping for %f min", sleep_min)
        time.sleep(sleep_min * 60.0)
    # Start the energy scan
    run_energy_scan(
        energies=energies, has_permit=SHUTTER_PERMIT,
        exposure=float(variableDict['ExposureTime']),
        n_pre_dark=int(variableDict['PreDarkImages']),
        sample_pos=sample_pos,
        out_pos=out_pos,
        stabilize_sleep_ms=stabilize_sleep_ms,
        ZP_X_drift_array=ZP_X_drift_array,
        constant_mag=constant_mag,
        repetitions=repetitions,
        pause=pause,
        log_level=log_level,
        use_fast_shutter=use_fast_shutter,
    )

if __name__ == '__main__':
    main()
