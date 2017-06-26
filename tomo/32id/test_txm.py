"""Tests for the transmission x-ray microscope `TXM()` class."""

import logging
logging.basicConfig(level=logging.WARNING)

import six
import time
import unittest
if six.PY2:
    import mock
else:
    from unittest import mock
import warnings

from txm import TXM, permit_required, txm_required, TxmPV
import exceptions_

log = logging.getLogger(__name__)
log.debug('Beginning tests in {}'.format(__name__))

class PermitDecoratorsTestCase(unittest.TestCase):
    class FakeTXM():
        has_permit = False
        is_attached = True
        ioc_prefix = ''
        test_value = False
        @permit_required
        def permit_func(self):
            self.test_value = True
        
        @txm_required(None)
        def txm_func(self):
            self.test_value = True
    
    def test_return_value(self):
        # First check that it's not set when mocked
        txm = self.FakeTXM()
        txm.has_permit = False
        txm.test_value = False
        with self.assertRaises(exceptions_.PermitError):
            txm.permit_func()
        # Now check that it *is* set when permit is available
        txm.has_permit = True
        txm.permit_func()
        self.assertTrue(txm.test_value)
    
    def test_txm_return_value(self):
        # First check that it's not set when mocked
        txm = self.FakeTXM()
        txm.is_attached = False
        txm.test_value = False
        txm.txm_func()
        self.assertFalse(txm.test_value)
        # Now check that it *is* set when permit is available
        txm.is_attached = True
        txm.txm_func()
        self.assertTrue(txm.test_value)
   
    def test_no_permit(self):
        """Make sure that not having a permit doesn't cause the check to
        fail.
        """
        txm = self.FakeTXM()
        txm.has_permit = False
        txm.is_attached = True
        txm.test_value = False
        txm.txm_func()
        self.assertTrue(txm.test_value)


class PVDescriptorTestCase(unittest.TestCase):
    class FakeTXM(object):
        pv_queue = []
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
        epics_pv.put.assert_called_with(27,
                                        callback=test_pv.complete_put,
                                        callback_data=(txm,))
        # Check that the PV was added to the queue
        self.assertEqual(len(txm.pv_queue), 1)
        self.assertIs(txm.pv_queue[0], test_pv)
    
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
        epics_pv.put.assert_called()
    
    @mock.patch('txm.EpicsPV')
    def test_complete_put(self, EpicsPV):
        txm = self.FakeTXM()
        txm.is_attached = True
        txm.has_permit = False
        test_pv = txm.__class__.__dict__['ioc_state']
        # Give it a wrong value and see if it stays not complete
        test_pv.put_complete = False
        epics_pv = test_pv.get_epics_PV(txm)
        epics_pv.get = mock.MagicMock(return_value=4)
        test_pv.curr_value = 4
        test_pv.complete_put(txm)
        self.assertTrue(test_pv.put_complete)
        assert False, "Write a test for when multiple puts are called in succession."
    
    def test_pv_name(self):
        txm = self.FakeTXM()
        txm.ioc_prefix = 'myIOC'
        test_pv = txm.__class__.__dict__['ioc_state']
        name = test_pv.pv_name(txm)
        self.assertEqual(name, 'myIOC_state')
    
    def test_dtype(self):
        # Make sure the dtype is compatible with the default value
        with self.assertRaises(TypeError):
            TxmPV('', default=None, dtype=float)
            


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
        txm.Motor_SampleX = None
        txm.Motor_SampleY = None
        txm.Motor_SampleZ = None
        self.assertEqual(txm.Motor_SampleX, None)
        txm.move_sample(1, 2, 3)
        self.assertEqual(txm.Motor_SampleX, 1)
        self.assertEqual(txm.Motor_SampleY, 2)
        self.assertEqual(txm.Motor_SampleZ, 3)
    
    def test_move_energy(self):
        txm = TXM(is_attached=False, has_permit=True)
        # Check what happens if we accidentally give the energy in eV
        with self.assertRaises(exceptions_.EnergyError):
            txm.move_energy(8500)
        # Check that the PVs are set properly
        txm.EnergyWait = 0
        txm.move_energy(8.6)
        assert False, "Add corrections for backlash"

    def test_open_shutters(self):
        txm = TXM(is_attached=False, has_permit=True)
        with warnings.catch_warnings(record=True) as w:
            txm.is_attached = True
            txm.open_shutters()
            txm.is_attached = False
            self.assertEqual(len(w), 1)
        # Now check with only shutter A
        txm = TXM(is_attached=False,
                  has_permit=True,
                  use_shutter_A=True,
                  use_shutter_B=False)
        txm.ShutterA_Move_Status = 0
        txm.ShutterB_Move_Status = 0
        txm.open_shutters()
        self.assertEqual(txm.ShutterA_Open, 1)
        self.assertEqual(txm.ShutterB_Open, None)
        # Now check with only shutter B
        txm.ShutterA_Open = None
        txm.use_shutter_A = False
        txm.use_shutter_B = True
        txm.open_shutters()
        self.assertEqual(txm.ShutterA_Open, None)
        self.assertEqual(txm.ShutterB_Open, 1)
    
    def test_close_shutters(self):
        txm = TXM(is_attached=False, has_permit=True)
        with warnings.catch_warnings(record=True) as w:
            txm.ShutterA_Move_Status = 1
            txm.ShutterB_Move_Status = 1
            txm.is_attached = True
            txm.close_shutters()
            txm.is_attached = False
            self.assertEqual(len(w), 1)
        # Now check with only shutter A
        txm = TXM(is_attached=False,
                  has_permit=True,
                  use_shutter_A=True,
                  use_shutter_B=False)
        txm.close_shutters()
        self.assertEqual(txm.ShutterA_Close, 1)
        self.assertEqual(txm.ShutterB_Close, None)
        # Now check with only shutter B
        txm.ShutterA_Close = None
        txm.use_shutter_A = False
        txm.use_shutter_B = True
        txm.close_shutters()
        self.assertEqual(txm.ShutterA_Close, None)
        self.assertEqual(txm.ShutterB_Close, 1)
    
    def test_wait_pvs(self):
        """Check that the ``wait_pvs`` context manager waits."""
        txm = TXM(is_attached=False)
        test_pv = txm.__class__.__dict__['DCMmvt']
        txm.pv_queue = [test_pv]
        with txm.wait_pvs() as w:
            # Check that it resets the pv_queue
            self.assertEqual(txm.pv_queue, [])
        # TODO: There should probably be more/better tests here...
