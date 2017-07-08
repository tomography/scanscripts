"""Scan script for Sector 32 ID-C. Changes the energy of the beamline.

"""

import logging
import time
from epics import PV
import math

log = logging.getLogger(__name__)

from txm import TXM

global variableDict
variableDict = {
    'new_energy': 7.8, # keV
    'constant_mag': 1, # 1 means magnification will be maintained adjusting CCD location
}

global_PVs = {}

def getVariableDict():
    global variableDict
    return variableDict


def move_energy(energy, constant_mag=True, is_attached=True,
                has_permit=False):
    """Change the X-ray microscope to a new energy.
    
    Parameters
    ==========
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
    txm = TXM(is_attached=is_attached, has_permit=has_permit)
    # Get variables from user dictionary.
    # Attach to the TXM and change energy
    with txm.wait_pvs():
        txm.move_energy(energy, constant_mag=constant_mag)
    log.info("Changed energy to %.5f keV", energy)


if __name__ == '__main__':
    # Prepare logging
    logging.basicConfig(level.DEBUG)
    # Get variables from user dictionary
    update_variable_dict(variableDict)
    zp_diameter = float(variableDict['ZP_diameter'])
    drn = float(variableDict['drn'])
    # Create a TXM object and move its energy
    txm = TXM(is_attached=True, zp_diameter=zp_diameter, drn=drn)
    move_energy(txm=txm)
