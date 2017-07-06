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
    'constant_mag': 0, # 1 means magnification will be maintained adjusting CCD location
    'ZP_diameter': 180.0, # um
    'drn': 60.0, # nm
    'offset': 0.15, # keV
}

global_PVs = {}

def getVariableDict():
    global variableDict
    return variableDict

def move_energy(txm):
    # Get variables from user dictionary.
    energy = float(variableDict['new_energy'])
    constant_mag = float(variableDict['constant_mag'])
    offset = float(variableDict['offset'])
    # Attach to the TXM and change energy
    with txm.wait_pvs():
        txm.move_energy(energy, constant_mag=constant_mag, gap_offset=offset)
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
