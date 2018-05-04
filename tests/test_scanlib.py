"""Unit test for the extra tooling in scanlib."""

import logging
logging.basicConfig(level=logging.WARNING)
import warnings
import unittest

import numpy as np

from scanlib.tools import energy_range, energy_range_from_points
from scanlib.scan_variables import parse_list_variable

log = logging.getLogger(__name__)


class ToolsTestCase(unittest.TestCase):
    
    def test_energy_range_from_points(self):
        points = (8300, 8500, 8700)
        steps = (100, 50, )
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


class ScanVariableTestCase(unittest.TestCase):

    def test_parse_list_variable(self):
        # Test with a single value
        output = parse_list_variable('0.03')
        self.assertEqual(output, (0.03, ))
        # Test with multiple values
        output = parse_list_variable('0.03, 0.05')
        self.assertEqual(output, (0.03, 0.05))
        # Test with a non-string value
        output = parse_list_variable(0.03)
        self.assertEqual(output, (0.03, ))
        # Test with a non-string 
        output = parse_list_variable([0.03, 0.05])
        self.assertEqual(output, (0.03, 0.05))
