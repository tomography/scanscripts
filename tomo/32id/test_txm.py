"""Tests for the transmission x-ray microscope `TXM()` class."""

import logging
logging.basicConfig(level=logging.DEBUG)

import unittest
import mock
import warnings

from txm import TXM, permit_required, txm_required, TxmPV

log = logging.getLogger(__name__)
log.debug('Beginning tests in {}'.format(__name__))

class PermitDecoratorsTestCase(unittest.TestCase):
    class FakeTXM():
        has_permit = False
        is_attached = True
        ioc_prefix = ''
        test_value = False
        @permit_required(None)
        def fake_func(self):
            self.test_value = True
        
        @txm_required(None)
        def fake_func2(self):
            self.test_value = True
    
    def test_return_value(self):
        # First check that it's not set when mocked
        txm = self.FakeTXM()
        txm.has_permit = False
        txm.test_value = False
        txm.fake_func()
        self.assertFalse(txm.test_value)
        # Now check that it *is* set when permit is available
        txm.has_permit = True
        txm.fake_func()
        self.assertTrue(txm.test_value)

    def test_attached(self):
        """Make sure that not being attached also causes the check to fail."""
        txm = self.FakeTXM()
        txm.has_permit = True
        txm.is_attached = False
        txm.test_value = False
        txm.fake_func()
        self.assertFalse(txm.test_value)
    
    def test_txm_return_value(self):
        # First check that it's not set when mocked
        txm = self.FakeTXM()
        txm.is_attached = False
        txm.test_value = False
        txm.fake_func2()
        self.assertFalse(txm.test_value)
        # Now check that it *is* set when permit is available
        txm.is_attached = True
        txm.fake_func2()
        self.assertTrue(txm.test_value)
    
    def test_(self):
        """Make sure that not having a permit doesn't cause the check to
        fail.
        """
        txm = self.FakeTXM()
        txm.has_permit = False
        txm.is_attached = True
        txm.test_value = False
        txm.fake_func2()
        self.assertTrue(txm.test_value)


class PVDescriptorTestCase(unittest.TestCase):
    class FakeTXM(object):
        ioc_prefix = ''
        ring_current = TxmPV('ring_curr')
        default_current = TxmPV('current', default=7)
        shutter_state = TxmPV('shutter', permit_required=True)
        ioc_state = TxmPV('{ioc_prefix}_state')
    
    def test_unattached_values(self):
        txm = self.FakeTXM()
        txm.is_attached = False
        self.assertEqual(txm.default_current, 7)
        # Does the new value get saved
        txm.default_current = 3
        self.assertEqual(txm.default_current, 3)
    
    @mock.patch('txm.EpicsPV')
    def test_actual_pv(self, EpicsPV):
        txm = self.FakeTXM()
        txm.is_attached = False
        # Mock the Epics PV object so we can test it for real
        test_pv = txm.__class__.__dict__['ring_current']
        epics_pv = test_pv.get_epics_PV(txm)
        # Make sure that the PV is not used when TXM is unattached
        txm.ring_current
        txm.ring_current = 19
        epics_pv.get.assert_not_called()
        epics_pv.put.assert_not_called()
        # Access the value and see the PV method was called
        txm.is_attached = True
        txm.ring_current
        epics_pv.get.assert_called()
        txm.ring_current = 27
        epics_pv.put.assert_called_with(27)
    
    @mock.patch('txm.EpicsPV')
    def test_permit_required(self, EpicsPV):
        txm = self.FakeTXM()
        txm.is_attached = True
        txm.has_permit = False
        # Mock the Epics PV object so we can test it for real
        test_pv = txm.__class__.__dict__['shutter_state']
        epics_pv = test_pv.get_epics_PV(txm)
        # Check that the permit_required PV is not changed w/o permit
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            txm.shutter_state = True
            self.assertEqual(len(w), 1) # Warning was issued
        epics_pv.put.assert_not_called()
        epics_pv.get = mock.MagicMock(return_value=2)
        self.assertEqual(txm.shutter_state, 2)
        # Now give it a permit and check that it works
        txm.has_permit = True
        txm.shutter_state = True
        epics_pv.put.assert_called_with(True)
    
    def test_pv_name(self):
        txm = self.FakeTXM()
        txm.ioc_prefix = 'myIOC'
        test_pv = txm.__class__.__dict__['ioc_state']
        name = test_pv.pv_name(txm)
        self.assertEqual(name, 'myIOC_state')


class TXMTestCase(unittest.TestCase):

    def test_has_permit(self):
        txm = TXM()
        txm.is_attached = True
        txm.has_permit = False
        self.assertFalse(txm.has_permit)
        # Now if the device has permit
        txm.is_attached = True
        txm.has_permit = True
        self.assertTrue(txm.has_permit)

    def test_move_sample(self):
        txm = TXM(is_attached=False)
        self.assertEqual(txm.Motor_SampleX, None)
        txm.move_sample(1, 2, 3)
        self.assertEqual(txm.Motor_SampleX, 1)
        self.assertEqual(txm.Motor_SampleY, 2)
        self.assertEqual(txm.Motor_SampleZ, 3)

    def test_open_shutters(self):
        txm = TXM(is_attached=False)
        with warnings.catch_warnings(record=True) as w:
            txm.open_shutters()
            self.assertEqual(len(w), 1)
