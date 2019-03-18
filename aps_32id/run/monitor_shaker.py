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
__all__ = ['monitor_shaker', 'getVariableDict']


variableDict = {
}

RUNNING = 1
STOPPED = 0

log = logging.getLogger(__name__)


def getVariableDict():
    return variableDict


def monitor_shaker():
    """Ensure the shaker does not randomly stop running.

    """
    def check_shaker(pvname, value, **kwargs):
        pv_status = value
    txm = new_txm()
    pv = txm.epics_PV('Shaker')
    pv_status = pv.get()
    index = pv.add_callback(check_shaker)
    try:
        print("Monitoring...")
        while True:
            if pv_status == STOPPED:
                log.info("Restarting shaker")
                pv.put(RUNNING, wait=True)
    except:
        pv.remove_callback(index)
        print("stopped.")


def main():
    logging.basicConfig(level=logging.INFO)
    # Run in an infinte loop and ensure the shaker does not randomly stop
    monitor_shaker()

if __name__ == '__main__':
    main()
