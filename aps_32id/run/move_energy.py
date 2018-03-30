"""Scan script for Sector 32 ID-C. Changes the energy of the beamline.

"""

import os
import logging
import time
from epics import PV
import math

log = logging.getLogger(__name__)

from scanlib import update_variable_dict
from aps_32id.txm import NanoTXM

__all__ = ['move_energy', 'getVariableDict']

variableDict = {
    'new_energy': 9.01, # keV
    'constant_mag': True, # 1 means magnification will be maintained adjusting CCD location
}

SHUTTER_PERMIT = True

def getVariableDict():
    return variableDict


def move_energy(energy, constant_mag=True, has_permit=False):
    """Change the X-ray microscope to a new energy.
    
    Parameters
    ----------
    energy : float
      New energy (in keV) for the microscope/source.
    constant_mag : bool, optional
      If truthy, the camera will move to maintain a constant
      magnification.
    is_attached, has_permit : bool, optional
      Determine if the TXM is attached and is allowed to open
      shutters.
    
    """
    # Prepare TXM object
    txm = NanoTXM(has_permit=has_permit)
    # Attach to the TXM and change energy
    with txm.wait_pvs():
        txm.move_energy(energy, constant_mag=constant_mag)
    log.info("Changed energy to %.5f keV", energy)


def main():
    # Prepare logging
    logfile = '/home/beams/USR32IDC/wolfman/wolfman-devel.log'
    if os.path.exists(logfile):
        logging.basicConfig(level=logging.DEBUG, filename=logfile)
    # Get variables from user dictionary
    update_variable_dict(variableDict)
    energy = float(variableDict['new_energy'])
    constant_mag = bool(variableDict['constant_mag'])
    # Create a TXM object and move its energy
    move_energy(energy, constant_mag=constant_mag)


if __name__ == '__main__':
    main()
