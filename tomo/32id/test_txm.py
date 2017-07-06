"""Tests for the transmission x-ray microscope `TXM()` class."""

import logging
logging.basicConfig(level=logging.DEBUG)

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
        ring_current = TxmPV('ring_curr', wait=True)
        default_current = TxmPV('current', default=7)
        shutter_state = TxmPV('shutter', permit_required=True)
        ioc_state = TxmPV('{ioc_prefix}_state')
        args_pv = TxmPV('withargs', get_kwargs={'as_string': True})
    
    def test_unattached_values(self):
        txm = self.FakeTXM()
        txm.is_attached = False
        self.assertEqual(txm.default_current, 7)
        # Does the new value get saved
        txm.default_current = 3
        self.assertEqual(txm.default_current, 3)
    
    @mock.patch('txm.EpicsPV')
    def test_pv_promise(self, EpicsPV):
        txm = self.FakeTXM()
        txm.is_attached = True
        # Mock the Epics PV object so we can test it for real
        test_pv = txm.__class__.__dict__['ring_current']
        epics_pv = test_pv.get_epics_PV(txm)
        # If the TXM has no queue, then the PV should be
        # called with ``put(wait=True)``
        txm.pv_queue = None
        test_pv.__set__(txm, 5)
        epics_pv.put.assert_called_with(5, wait=True)
        # If the TXM has a queue, then the PV should add a promise
        txm.pv_queue = []
        test_pv.__set__(txm, 6)
        self.assertEqual(len(txm.pv_queue), 1)
        promise = txm.pv_queue[0]
        self.assertIsInstance(promise, test_pv.PVPromise)
        epics_pv.put.assert_called_with(6, callback=test_pv.complete_put,
                                        callback_data=promise, wait=False)
        # Now check that completing the put changes the promises state
        test_pv.complete_put(promise, pvname='ring_current')
        self.assertTrue(promise.is_complete)
        
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
        epics_pv.put.assert_called()
    
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

    @mock.patch('txm.EpicsPV')
    def test_extra_args(self, EpicsPV):
        # Make sure the extra arguments given to the constructor get
        # pass through to the actual PV.
        txm = self.FakeTXM()
        txm.is_attached = True
        test_pv = txm.__class__.__dict__['args_pv']
        self.assertEqual(test_pv.get_kwargs['as_string'], True)
        # Check that the arguments get passed to the real PV
        txm.args_pv
        test_pv.get_epics_PV(txm).get.assert_called_once_with(as_string=True)


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
        txm.Motor_SampleX = 0.
        txm.Motor_SampleY = 0.
        txm.Motor_SampleZ = 0.
        self.assertEqual(txm.Motor_SampleX, 0.)
        txm.move_sample(1, 2, 3)
        self.assertEqual(txm.Motor_Sample_Top_X, 1)
        self.assertEqual(txm.Motor_SampleY, 2)
        self.assertEqual(txm.Motor_Sample_Top_Z, 3)
    
    def test_move_energy(self):
        txm = TXM(is_attached=False, has_permit=True)
        # Check what happens if we accidentally give the energy in eV
        with self.assertRaises(exceptions_.EnergyError):
            txm.move_energy(8500)
        # Check that the PVs are set properly
        txm.EnergyWait = 0
        txm.DCMmvt = 14
        txm.move_energy(8.6)
        self.assertEqual(txm.DCMmvt, 14)
    
    def test_setup_tiff_writer(self):
        txm = TXM(is_attached=False, has_permit=True)
        txm.setup_tiff_writer(filename="hello.h5",
                              num_recursive_images=1, num_projections=5)
        # Test without recursive filter
        self.assertEqual(txm.TIFF1_AutoSave, 'Yes')
        self.assertEqual(txm.TIFF1_DeleteDriverFile, 'No')
        self.assertEqual(txm.TIFF1_EnableCallbacks, 'Enable')
        self.assertEqual(txm.TIFF1_BlockingCallbacks, 'No')
        self.assertEqual(txm.TIFF1_NumCapture, 5)
        self.assertEqual(txm.TIFF1_FileWriteMode, 'Stream')
        self.assertEqual(txm.TIFF1_FileName, 'hello.h5')
        self.assertEqual(txm.TIFF1_Capture, txm.CAPTURE_ENABLED)
    
    def test_setup_tiff_writer_recursive(self):
        txm = TXM(is_attached=False, has_permit=True)
        txm.setup_tiff_writer(filename="hello.h5", num_recursive_images=3, num_projections=5)
        # Test *with* recursive filter
        self.assertEqual(txm.Proc1_Callbacks, 'Enable')
        self.assertEqual(txm.Proc1_Filter_Enable, 'Disable')
        self.assertEqual(txm.TIFF1_ArrayPort, 'PROC1')
        self.assertEqual(txm.Proc1_Filter_Type, txm.RECURSIVE_FILTER_TYPE)
        self.assertEqual(txm.Proc1_Num_Filter, 3)
        self.assertEqual(txm.Proc1_Reset_Filter, 1)
        self.assertEqual(txm.Proc1_AutoReset_Filter, 'Yes')
        self.assertEqual(txm.Proc1_Filter_Callbacks, 'Array N only')
        # These are the same regardless of recursive filtering
        self.assertEqual(txm.TIFF1_AutoSave, 'Yes')
        self.assertEqual(txm.TIFF1_DeleteDriverFile, 'No')
        self.assertEqual(txm.TIFF1_EnableCallbacks, 'Enable')
        self.assertEqual(txm.TIFF1_BlockingCallbacks, 'No')
        self.assertEqual(txm.TIFF1_NumCapture, 5)
        self.assertEqual(txm.TIFF1_FileWriteMode, 'Stream')
        self.assertEqual(txm.TIFF1_FileName, 'hello.h5')
        self.assertEqual(txm.TIFF1_Capture, txm.CAPTURE_ENABLED)
    
    def test_setup_detector(self):
        txm = TXM(is_attached=False, has_permit=False)
        txm.pg_external_trigger = False
        txm.setup_detector(live_display=False)
        # Check that PV values were set
        self.assertEqual(txm.Cam1_Display, False)
        self.assertEqual(txm.Cam1_ImageMode, 'Multiple')
        self.assertEqual(txm.Cam1_ArrayCallbacks, 'Enable')
        self.assertEqual(txm.SetSoftGlueForStep, 0)
        self.assertEqual(txm.Cam1_FrameRateOnOff, 0)
        self.assertEqual(txm.Cam1_TriggerMode, "Internal")
    
    def test_setup_hdf_writer(self):
        txm = TXM(is_attached=False, has_permit=True)
        txm.Proc1_ArrayPort = "test_value"
        txm.setup_hdf_writer(filename="testfile.h5",
                             num_projections=3, write_mode="stream")
        # Test without recursive filter
        self.assertEqual(txm.Proc1_Filter_Enable, "Disable")
        self.assertEqual(txm.HDF1_ArrayPort, 'test_value')
        self.assertEqual(txm.HDF1_NumCapture, 3)
        self.assertEqual(txm.HDF1_FileWriteMode, 'stream')
        self.assertEqual(txm.HDF1_FileName, 'testfile.h5')
        self.assertEqual(txm.HDF1_Capture, 1)
        self.assertTrue(txm.hdf_writer_ready)
    
    def test_setup_hdf_writer_recursive(self):
        txm = TXM(is_attached=False, has_permit=True)
        txm.Proc1_ArrayPort = "test_value"
        txm.setup_hdf_writer(filename="testfile.h5", num_recursive_images=3,
                             num_projections=3, write_mode="stream")
        # Test with recursive filter
        self.assertEqual(txm.Proc1_Callbacks, "Enable")
        self.assertEqual(txm.Proc1_Filter_Enable, "Disable")
        self.assertEqual(txm.Proc1_Filter_Type, txm.RECURSIVE_FILTER_TYPE)
        self.assertEqual(txm.HDF1_ArrayPort, 'PROC1')
        self.assertEqual(txm.Proc1_Num_Filter, 3)
        self.assertEqual(txm.Proc1_Reset_Filter, 1)
        self.assertEqual(txm.Proc1_AutoReset_Filter, 'Yes')
        self.assertEqual(txm.Proc1_Filter_Callbacks, 'Array N only')
        # These should be the same regardless of recursion filter
        self.assertEqual(txm.HDF1_FileWriteMode, 'stream')
        self.assertEqual(txm.HDF1_FileName, 'testfile.h5')
        self.assertEqual(txm.HDF1_Capture, 1)
        self.assertTrue(txm.hdf_writer_ready)
    
    @mock.patch('txm.EpicsPV')
    def test_open_shutters(self, EpicsPV):
        txm = TXM(is_attached=False, has_permit=True)
        with warnings.catch_warnings(record=True) as w:
            txm.is_attached = True
            txm.use_shutter_A = False
            txm.use_shutter_B = False
            txm.shutters_are_open = True
            txm.open_shutters()
            txm.is_attached = False
            self.assertEqual(len(w), 1)
            self.assertFalse(txm.shutters_are_open)
        # Now check with only shutter A
        txm = TXM(is_attached=False,
                  has_permit=True,
                  use_shutter_A=True,
                  use_shutter_B=False)
        txm.ShutterA_Move_Status = 0
        txm.ShutterA_Open = None
        txm.ShutterB_Move_Status = 0
        txm.ShutterB_Open = None
        txm.shutters_are_open = False
        txm.open_shutters()
        self.assertEqual(txm.ShutterA_Open, 1)
        self.assertEqual(txm.ShutterB_Open, None)
        self.assertTrue(txm.shutters_are_open)
        # Now check with only shutter B
        txm.ShutterA_Open = None
        txm.use_shutter_A = False
        txm.use_shutter_B = True
        txm.open_shutters()
        self.assertEqual(txm.ShutterA_Open, None)
        self.assertEqual(txm.ShutterB_Open, 1)
    
    @mock.patch('txm.EpicsPV')
    def test_close_shutters(self, EpicsPV):
        txm = TXM(is_attached=False, has_permit=True)
        with warnings.catch_warnings(record=True) as w:
            txm.ShutterA_Move_Status = 1
            txm.ShutterB_Move_Status = 1
            txm.shutters_are_open = True
            txm.is_attached = True
            txm.use_shutter_A = False
            txm.use_shutter_B = False
            txm.close_shutters()
            txm.is_attached = False
            self.assertEqual(len(w), 1)
            self.assertFalse(txm.shutters_are_open)
        # Now check with only shutter A
        txm = TXM(is_attached=False,
                  has_permit=True,
                  use_shutter_A=True,
                  use_shutter_B=False)
        txm.ShutterA_Close = None
        txm.ShutterB_Close = None
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
        txm.pv_queue = 'outer_value'
        with txm.wait_pvs() as q:
            self.assertEqual(q, [])
            # Check that it resets the pv_queue
            self.assertEqual(txm.pv_queue, q)
            # Add a pv promise
            promise = TxmPV.PVPromise()
            promise.is_complete = True
            txm.pv_queue.append(promise)
        # Was the previous queue restored?
        self.assertEqual(txm.pv_queue, 'outer_value')
        # Now does it work in non-blocking mode?
        with txm.wait_pvs(block=False) as q:
            promise = TxmPV.PVPromise()
            promise.is_complete = False
            txm.pv_queue.append(promise)
    
    def test_trigger_multiple_projections(self):
        txm = TXM(is_attached=False)
        txm.pg_external_trigger = True
        txm._trigger_multiple_projections(exposure=0.5, num_projections=3)
        self.assertEqual(txm.Cam1_ImageMode, 'Multiple')
        self.assertEqual(txm.Cam1_TriggerMode, 'Overlapped')
        self.assertEqual(txm.Cam1_NumImages, 1)
        # Now with internal trigger
        txm.pg_external_trigger = False
        txm._trigger_multiple_projections(exposure=0.5, num_projections=3)
        self.assertEqual(txm.Cam1_TriggerMode, "Internal")
        self.assertEqual(txm.Cam1_NumImages, 3)
    
    def test_trigger_single_projection(self):
        # Currently this test only checks that the method can run without error
        txm = TXM(is_attached=False)
        txm._trigger_single_projection(exposure=0.5)
    
    def test_capture_projections(self):
        txm = TXM(is_attached=False)
        txm._trigger_multiple_projections = mock.MagicMock()
        txm._trigger_single_projection = mock.MagicMock()
        # Check for warning if collecting with shutters closed
        txm.shutters_are_open = False
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            txm.capture_projections()
            self.assertEqual(len(w), 1, "Did not raise shutter warning")
            self.assertIn('Collecting projections with shutters closed.', w[0].message)
        # Test when num_projections is > 1
        txm.shutters_are_open = True
        txm.capture_projections(num_projections=3)
        self.assertEqual(txm.Cam1_FrameType, txm.FRAME_DATA)
        txm._trigger_multiple_projections.assert_called_with(exposure=0.5,
                                                             num_projections=3)
        # Test when num_projections == 1
        txm.capture_projections(num_projections=1)
        txm._trigger_single_projection.assert_called_with(exposure=0.5,)
    
    def test_capture_dark_field(self):
        txm = TXM(is_attached=False)
        txm._trigger_multiple_projections = mock.MagicMock()
        txm._trigger_single_projection = mock.MagicMock()
        # Check for warning if collecting with shutters open
        txm.shutters_are_open = True
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            txm.capture_dark_field()
            self.assertEqual(len(w), 1, "Did not raise shutter warning")
            self.assertIn('Collecting dark field with shutters open.', w[0].message)
        # Test when calling with multiple projections
        txm.close_shutters()
        txm.capture_dark_field(num_projections=3)
        self.assertEqual(txm.Cam1_FrameType, txm.FRAME_DARK)
        txm._trigger_multiple_projections.assert_called_with(num_projections=3,
                                                             exposure=0.5)
        # Test when calling only one projection
        txm.capture_dark_field(num_projections=1)
        txm._trigger_single_projection.assert_called_with(exposure=0.5)
    
    def test_capture_flat_field(self):
        txm = TXM(is_attached=False)
        txm._trigger_multiple_projections = mock.MagicMock()
        txm._trigger_single_projection = mock.MagicMock()
        # Check for warning if collecting with shutters closed
        txm.shutters_are_open = False
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            txm.capture_white_field()
            self.assertEqual(len(w), 1, "Did not raise shutter warning")
            self.assertIn('Collecting white field with shutters closed.', w[0].message)
        # Test for collecting multiple projections
        txm.open_shutters()
        txm._trigger_multiple_projections.reset_mock()
        txm._trigger_single_projection.reset_mock()
        txm.capture_white_field(num_projections=3)
        self.assertEqual(txm.Cam1_FrameType, txm.FRAME_WHITE)
        txm._trigger_multiple_projections.assert_called_with(num_projections=3,
                                                             exposure=0.5)
        # Test when calling only one projection
        txm._trigger_multiple_projections.reset_mock()
        txm._trigger_single_projection.reset_mock()
        txm.capture_white_field(num_projections=1)
        txm._trigger_single_projection.assert_called_with(exposure=0.5)
