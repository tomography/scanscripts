"""This file tests the actual execution scripts themselves."""

# Logging
import logging
logging.basicConfig(level=logging.INFO)

import unittest
import six
if six.PY2:
    import mock
else:
    from unittest import mock
import sys
import os

import numpy as np

import energy_scan
import move_energy
import tomo_step_scan
from txm import TXM

log = logging.getLogger(__name__)
log.debug('Beginning tests in {}'.format(__name__))

# Set some faster options for testing
energy_scan.variableDict['ExposureTime'] = 0.001
energy_scan.variableDict['StabilizeSleep_ms'] = 0.001


class MoveEnergyTests(unittest.TestCase):
    def test_move_energy(self):
        txm = TXM(is_attached=False)
        move_energy.move_energy(energy=6.7)


class TomoStepScanTests(unittest.TestCase):
    hdf_filename = "/tmp/sector32_test.h5"
    
    def setUp(self):
        self.txm = TXM(is_attached=False,
                       has_permit=True)
    
    def tearDown(self):
        if os.path.exists(self.hdf_filename):
            os.remove(self.hdf_filename)
    
    def test_full_tomo_scan(self):
        self.txm.HDF1_FullFileName_RBV = self.hdf_filename
        self.txm.setup_detector = mock.MagicMock()
        tomo_step_scan.full_tomo_scan(txm=self.txm)
        # Check that the right txm functions were called
        detector_kwargs = {
            'exposure': 98,
            'num_projections': 361
        }
        self.txm.setup_detector.assert_called_once_with(**detector_kwargs)


class EnergyScanTests(unittest.TestCase):
    def setUp(self):
        self.txm = TXM(is_attached=False,
                       has_permit=True)
    
    def tearDown(self):
        # Get rid of the temporary HDF5 file
        if os.path.exists('/tmp/test_file.h5'):
            os.remove('/tmp/test_file.h5')
    
    @mock.patch('txm.TXM.capture_projections')
    @mock.patch('txm.TXM.capture_dark_field')
    @mock.patch('txm.TXM.capture_white_field')
    @mock.patch('txm.TXM.setup_hdf_writer')
    @mock.patch('txm.TXM.setup_detector')
    def test_start_scan(self, *args):
        # Get rid of any old files hanging around
        if os.path.exists('/tmp/test_file.h5'):
            os.remove('/tmp/test_file.h5')
        # Set some sensible TXM values for testing
        self.txm.HDF1_FullFileName_RBV = '/tmp/test_file.h5'
        # Launch the script
        energies = np.linspace(8.6, 8.8, num=4)
        n_pre_dark = 4
        expected_projections = n_pre_dark + 2 * len(energies)
        txm = energy_scan.energy_scan(energies=energies,
                                      n_pre_dark=n_pre_dark,
                                      exposure=0.77,
                                      is_attached=False,
                                      has_permit=True)
        # Check that what happened was done correctly
        self.assertEqual(txm.capture_projections.call_count, len(energies))
        txm.capture_projections.assert_called_with()
        txm.capture_dark_field.assert_called_once_with(num_projections=4)
        # Verify the detector and hdf writer were colled properly
        txm.setup_hdf_writer.assert_called_once_with(num_projections=expected_projections)
        txm.setup_detector.assert_called_once_with(exposure=0.77)
