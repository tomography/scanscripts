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
        move_energy.move_energy(txm=txm)


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
        tomo_step_scan.full_tomo_scan(txm=self.txm)


class EnergyScanTests(unittest.TestCase):
    def setUp(self):
        self.txm = TXM(is_attached=False,
                       has_permit=True)
    
    def tearDown(self):
        # Get rid of the temporary HDF5 file
        if os.path.exists('/tmp/test_file.h5'):
            os.remove('/tmp/test_file.h5')
    
    def test_start_scan(self, *args):
        # Get rid of any old files hanging around
        if os.path.exists('/tmp/test_file.h5'):
            os.remove('/tmp/test_file.h5')
        self.txm.HDF1_FullFileName_RBV = '/tmp/test_file.h5'
        # Set some mocked functions for testing
        txm = self.txm
        txm.capture_projections = mock.MagicMock()
        txm.capture_dark_field = mock.MagicMock()
        txm.capture_white_field = mock.MagicMock()
        txm.setup_hdf_writer = mock.MagicMock()
        txm.setup_detector = mock.MagicMock()
        # Launch the script
        energy_scan.variableDict['PreDarkImages'] = 4
        energy_scan.energy_scan(txm)
        # Check that what happened was done correctly
        self.assertEqual(txm.capture_projections.call_count, 101)
        txm.capture_projections.assert_called_with(exposure=0.001)
        txm.capture_dark_field.assert_called_once_with(
            exposure=0.001, num_projections=4)
        txm.setup_hdf_writer.assert_called_once_with()
        # Verify 
        txm.setup_detector.assert_called_once_with()
