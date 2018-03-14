"""This file runs integration tests on the actual execution scripts
themselves.

"""

# Logging
import logging
logging.basicConfig(level=logging.ERROR)

import warnings
import unittest
import six
if six.PY2:
    import mock
else:
    from unittest import mock
import sys
import os

import numpy as np

from aps_32id.run import (energy_scan, move_energy, tomo_step_scan, tomo_fly_scan)
from aps_32id.txm import NanoTXM
from tools import TXMStub

log = logging.getLogger(__name__)
log.debug('Beginning tests in {}'.format(__name__))

# Set some faster options for testing
energy_scan.variableDict['ExposureTime'] = 0.001
energy_scan.variableDict['StabilizeSleep_ms'] = 0.001


class ScriptTestCase(unittest.TestCase):
    hdf_filename = "/tmp/sector32_test.h5"
    def setUp(self):
        if os.path.exists(self.hdf_filename):
            os.remove(self.hdf_filename)
    def tearDown(self):
        if os.path.exists(self.hdf_filename):
            os.remove(self.hdf_filename)


class MoveEnergyTests(ScriptTestCase):
    @unittest.skip('Need to re-work the integrations tests')
    def test_move_energy(self):
        txm = TXM()
        txm.HDF1_FullFileName_RBV = self.hdf_filename
        move_energy.move_energy(energy=6.7, has_permit=False)


@unittest.skip('Need to re-work the integrations tests')
@mock.patch('txm.TXM._trigger_projections')
@mock.patch('txm.EpicsPV')
class TomoStepScanTests(ScriptTestCase):
    
    @mock.patch('txm.TXM.setup_detector')
    @mock.patch('txm.TXM.setup_hdf_writer')
    @mock.patch('txm.TXM.move_sample')
    def test_full_tomo_scan(self, *args):
        angles = np.linspace(0, 180, 361)
        txm = tomo_step_scan.tomo_step_scan(angles=angles,
                                            num_recursive_images=3,
                                            num_white=(2, 7),
                                            num_dark=(13, 21))
        # Check that the right txm functions were called
        txm.setup_detector.assert_called_once_with(exposure=3)
        expected_projections = 361 + 2 + 7 + 13 + 21
        txm.setup_hdf_writer.assert_called_once_with(num_projections=expected_projections,
                                                     num_recursive_images=3)


class TomoFlyScanTests(unittest.TestCase):
    def setUp(self):
        self.txm = TXMStub(has_permit=True)
        self.txm.exposure_time = 1
    
    def tearDown(self):
        if os.path.exists(self.txm.hdf_filename):
            os.remove(self.txm.hdf_filename)
    
    def test_start_fly_scan(self):
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', message='Could not cast None')
            warnings.filterwarnings('ignore', message='Could not retrieve actual angles')
            warnings.filterwarnings('ignore', message='Collecting white field')
            txm = tomo_fly_scan.run_tomo_fly_scan(txm=self.txm)


class EnergyScanTests(unittest.TestCase):
    def setUp(self):
        self.txm = TXMStub(has_permit=True)
    
    def tearDown(self):
        # Get rid of the temporary HDF5 file
        if os.path.exists('/tmp/test_file.h5'):
            os.remove('/tmp/test_file.h5')
    
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
        self.txm.Cam1_Acquire = self.txm.DETECTOR_IDLE
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', message='Could not cast None')
            warnings.filterwarnings('ignore', message='Could not save energies')
            warnings.filterwarnings('ignore', message='Collecting white field with')
            txm = energy_scan.run_energy_scan(energies=energies,
                                              n_pre_dark=n_pre_dark,
                                              exposure=0.77, repetitions=2,
                                              txm=self.txm)
        # Check that what happened was done correctly
        self.assertEqual(txm.capture_projections.call_count, 2*len(energies))
        txm.capture_projections.assert_called_with(num_projections=1)
        txm.capture_dark_field.assert_called_with(num_projections=4)
        # Verify the detector and hdf writer were colled properly
        txm.setup_hdf_writer.assert_called_with(num_projections=expected_projections,
                                                     num_recursive_images=1)
        txm.setup_detector.assert_called_with(exposure=0.77)
