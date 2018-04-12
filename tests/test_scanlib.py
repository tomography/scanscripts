"""Unit test for the extra tooling in scanlib."""

import logging
logging.basicConfig(level=logging.WARNING)
import warnings
import unittest

import numpy as np

from scanlib.tools import energy_range, energy_range_from_points

log = logging.getLogger(__name__)


class ToolsTestCase(unittest.TestCase):
    
    def test_energy_range_from_points(self):
        points = (8300, 8500, 8700)
        steps = (100, 50, 100)
        expected = np.array((8300, 8400, 8500, 8550, 8600, 8650, 8700))
        output = energy_range_from_points(energy_points=points,
                                          energy_steps=steps)
        np.testing.assert_array_equal(output, expected)
        # Check with mismatched arrays
        points = (8.3, 8.5, 8.7)
        steps = (0.1, 0.3, 0.1)
        with self.assertRaises(ValueError):
            energy_range_from_points(energy_points=points,
                                     energy_steps=steps)