# -*- coding: utf-8 -*-

"""Classes for interactions between the TXM class and the real TXM.

TxmPV
  A descriptor for the process variables used by the microscopes.

"""

import logging
import datetime as dt
import os

import epics
import numpy as np

__author__ = 'Mark Wolfman'
__copyright__ = 'Copyright (c) 2017, UChicago Argonne, LLC.'
__docformat__ = 'restructuredtext en'
__platform__ = 'Unix'
__version__ = '1.6'


def loggingConfig(level=logging.INFO):
    """Prepare a basic logging file setup with the date of the experiment."""
    path = epics.caget('32idcPG3:HDF1:FilePath', as_string=True)
    filename = "{}.log".format(dt.date.today().isoformat())
    logging.basicConfig(level=int(level), filename=os.path.join(path, filename))


def expand_position(position, length=4):
    """Take a tuple with length <= 4 and pad it with ``None``'s up to
    length.
    
    Example, if ``length=4`` and ``position=(1, 0)``, then the output
    is ``(1, 0, None, None)``.
    
    """
    new_position = tuple(position) + (None,) * (length-len(position))
    return new_position


def energy_range_from_points(energy_points, energy_steps):
    """Convert energy ranges to a flat energy list.
    
    This function is called with a list of energy limits and spacings between
    those energy points:
        
        .. code:: python
        
            energy_range(
                energy_points=(8.3, 8.5, 8.7),
                energy_steps=(0.02, 0.01)
            )
    
    """
    # Validate the length of the lists
    if len(energy_points) != (len(energy_steps) + 1):
        raise ValueError("Number of energy points must be one more than "
                         "number of energy steps: %d, %d"
                         "" % (len(energy_points), len(energy_steps)))
    # First prepare a list of ranges
    ranges = []
    for idx in range(len(energy_steps)):
        start = energy_points[idx]
        stop = energy_points[idx+1]
        step = energy_steps[idx]
        ranges.append((start, stop, step))
    # Convert the list of ranges to a list of energies
    energies = energy_range(*ranges)
    return energies

    
def energy_range(*ranges):
    """Convert energy ranges to a flat energy list.
    
    This function is called with multiple energy ranges:
        
        .. code:: python
        
            energy_range(
                (8.3, 8.5, 0.02),
                (8.5, 8.7, 0.01),
            )
    
    Each entry in ``ranges`` should be a tuple of (start, stop,
    step). Unlike the standard ``range`` function, stop is
    inclusive."""

    Es = [np.arange(r[0], r[1]+r[2], r[2]) for r in ranges]
    Es = np.concatenate(Es)
    Es = np.unique(Es)
    return Es
