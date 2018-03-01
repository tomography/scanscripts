# -*- coding: utf-8 -*-

"""Classes for interactions between the TXM class and the real TXM.

TxmPV
  A descriptor for the process variables used by the microscopes.

"""

import numpy as np

__author__ = 'Mark Wolf'
__copyright__ = 'Copyright (c) 2017, UChicago Argonne, LLC.'
__docformat__ = 'restructuredtext en'
__platform__ = 'Unix'
__version__ = '1.6'


def energy_range(*ranges):
    """Convert energy ranges to a flat energy list.

    Each entry in ``ranges`` should be a tuple of (start, stop,
    step). Unlike the standard ``range`` function, stop is
    inclusive."""

    Es = [np.arange(r[0], r[1]+r[2], r[2]) for r in ranges]
    Es = np.concatenate(Es)
    Es = np.unique(Es)
    return Es
