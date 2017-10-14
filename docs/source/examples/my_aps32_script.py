#!/bin/env python
"""An example script for controlling the sector 32 ID-C microscope."""

import logging

from aps_32id import NanoTXM

# Prepare for logging data to a file, or whatever
log = logging.getLogger(__name__)

# A dictionary with the options that can be used when invoking this script
variableDict = {
    'Parameter A': 840,
    'Parameter B': 12.34,
}

def getVariableDict():
    return variableDict

def my_experiment(param_a, param_b=9.8, has_permit=False):
    """My amazing experiment that will change the world.
    
    Parameters
    ----------
    param_a : int
      The first experimental parameter.
    param_b : float, optional
      The second experimental parameter.
    has_permit : bool, optional
      Pass ``True`` to access shutters and X-ray source.
    
    """
    log.debug("Starting my experiment")
    # Create a TXM object to control the instrument
    txm = NanoTXM(has_permit=has_permit,
                  use_shutter_A=False,
                  use_shutter_B=True)
    # Setup the microscope as desired
    txm.setup_detector()
    txm.setup_hdf_writer()
    txm.open_shutters()
    # Run the experiment in this context manager so it stops properly
    with txm.run_scan():
        # Now do some tomography or XANES or whatever
        pass
    # Close the shutters and shutdown
    txm.close_shutters()

def main():
    # The script was launched (not imported) so use the variable dictionary
    update_variable_dict(variableDict)
    # Abort the scan if requested
    if variableDict.get('StopTheScan', False):
        log.info("Aborting scan at user request.")
        txm = TXM(has_permit=SHUTTER_PERMIT)
        txm.stop_scan()
        return
    # Start the experiment
    my_experiment(param_a=variableDict['Parameter A'],
                  param_b=variableDict['Parameter B'])


if __name__ == '__main__':
    main()
