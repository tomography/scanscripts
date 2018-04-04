#!/bin/env python
"""An example script for controlling the sector 32 ID-C microscope."""

import logging

from scanlib import update_variable_dict
from aps_32id import NanoTXM

# Prepare for logging data to a file, or whatever
log = logging.getLogger(__name__)

# A dictionary with the options that can be used when invoking this script
variableDict = {
    'Energy': 8.7,
    'Exposure': 1.,
    # Logging: -1=no change, 0=UNSET, 10=DEBUG, 20=INFO, 30=WARNING, 40=ERROR, 50=CRITICAL
    'Log_Level': logging.INFO,
}

def getVariableDict():
    return variableDict

def run_my_experiment(energy, exposure=0.5, log_level=logging.INFO, has_permit=False, txm=None):
    """Separate out the work-horse code so that it can be executed
    programatically. The ``txm`` parameter is intended for testing,
    where an instance of :py:class:`tests.tools.TXMStub` is used.
    
    Parameters
    ==========
    energy : float
      What energy (in keV) for setting the beamline.
    exposure : float, optional
      How long to collect the frame for.
    log_level : logging.INFO
      How much detail to save to the logs.
    has_permit : bool, optional
      Pass ``True`` to access shutters and X-ray source.
    txm : NanoTXM, optional
      A NanoTXM object that represents the X-ray microscope. Useful
      for testing.
    
    """
    log.debug("Starting my experiment")
    # Create a TXM object to control the instrument
    if txm is None:
        txm = NanoTXM(has_permit=has_permit,
                      use_shutter_A=False,
                      use_shutter_B=True)
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
    my_experiment(param_a=variableDict['Parameter A'],
                  param_b=variableDict['Parameter B'],
                  log_level=variableDict['Log_Level'])


if __name__ == '__main__':
    main()
