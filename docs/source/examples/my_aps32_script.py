#!/bin/env python
"""An example script for controlling the sector 32 ID-C microscope."""

import logging

from scanlib import update_variable_dict
from aps_32id import NanoTXM

# Prepare for logging data to a file, or whatever
log = logging.getLogger(__name__)


# A dictionary with the options that can be used when invoking this script
variableDict = {
    'Parameter A': 0.1,
    'Parameter B': 505,
    # Logging: -1=no change, 0=UNSET, 10=DEBUG, 20=INFO, 30=WARNING, 40=ERROR, 50=CRITICAL
    'Log_Level': logging.INFO,
}


def getVariableDict():
    return variableDict


def run_my_experiment(param_a, param_b, log_level=20, txm=None):
    """Separate out the work-horse code so that it can be executed
    programatically. The ``txm`` parameter is intended for testing,
    where an instance of :py:class:`tests.tools.TXMStub` is used.
    
    Parameters
    ==========
    param_a :
      An experimental parameter.
    param_b :
      Another experimental parameter.
    log_level : logging.INFO
      How much detail to save to the logs.
    txm : NanoTXM, optional
      A NanoTXM object that represents the X-ray microscope. Useful
      for testing.
    
    """
    log.debug("Starting my experiment")
    # Create a TXM object to control the instrument
    if txm is None:
        txm = new_txm()
    # Run the experiment in this context manager so it stops properly
    with txm.run_scan():
        # Setup the microscope as desired
        txm.setup_hdf_writer()
        txm.start_logging(log_level)
        txm.setup_detector()
        txm.enable_fast_shutter() # Optional: reduces beam damage
        txm.open_shutters()
        # Now do some tomography or XANES or whatever
        pass
        # Close the shutters and shutdown
        txm.close_shutters()


def main():
    # The script was launched (not imported) so load the variable
    # dictionary from CLI parameters
    update_variable_dict(variableDict)
    # Start the experiment
    run_my_experiment(param_a=variableDict['Parameter A'],
                      param_b=variableDict['Parameter B'],
                      log_level=variableDict['Log_Level'])


if __name__ == '__main__':
    main()
