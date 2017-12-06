"""Unit tests for the transmission x-ray microscope `TXM()` class."""

import logging
logging.basicConfig(level=logging.WARNING)
logging.captureWarnings(True)

import six
import time
import unittest
if six.PY2:
    import mock
else:
    from unittest import mock
import warnings

from aps_32id.txm import NanoTXM, permit_required
from scanlib import TxmPV, exceptions_
from tools import UnpluggedTXM


log = logging.getLogger(__name__)
log.debug('Beginning tests in {}'.format(__name__))


class PermitDecoratorsTestCase(unittest.TestCase):
    class FakeTXM():
        has_permit = False
        ioc_prefix = ''
        test_value = False
        @permit_required
        def permit_func(self):
            self.test_value = True
    
    def test_no_permit(self):
        """Make sure that the function is not executed if no permit"""
        txm = self.FakeTXM()
        txm.has_permit = False
        txm.test_value = False
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            txm.permit_func()
            self.assertTrue(len(w) >= 1, 'Permit warning not raised: {}'.format(w))
        self.assertFalse(txm.test_value, 'Function still called without permit')


class TXMTestCase(unittest.TestCase):
    
    def test_pv_put(self):
        # Have a dummy PV method to check if it actually calls
        class StubTXM2(UnpluggedTXM):
            _test_value = 0
            def _pv_put(self, pv_name, value, *args, **kwargs):
                self._test_value = value
                return True
        txm = StubTXM2()
        # Check if the method set the test value
        txm.pv_put('my_pv', 3, wait=True)
        self.assertEqual(txm._test_value, 3)
        # Check that the method adds a promise if a PV queue is present
        txm.pv_queue = []
        txm.pv_put('my_pv', 3, wait=True)
        self.assertEqual(len(txm.pv_queue), 1, "%d PV promises added to queue" % len(txm.pv_queue))

    def test_pv_put_twice(self):
        """Check what happens if two non-blocking calls to pv_put are made."""
        # Have a dummy PV method to check if it actually calls
        class StubTXM2(UnpluggedTXM):
            _test_value = 0
            def _pv_put(self, pv_name, value, *args, **kwargs):
                self._test_value = value
                return True
        txm = StubTXM2()
        # Check that the method adds a promise if a PV queue is present
        txm.pv_queue = []
        txm.pv_put('my_pv', 3, wait=True)
        txm.pv_put('my_pv', 3, wait=True)
        self.assertEqual(len(txm.pv_queue), 1, "%d PV promises added to queue" % len(txm.pv_queue))
    
    def test_move_sample(self):
        txm = UnpluggedTXM()
        txm.Motor_SampleX = 0.
        txm.Motor_SampleY = 0.
        txm.Motor_SampleZ = 0.
        txm.Motor_SampleRot = 0.
        self.assertEqual(txm.Motor_SampleX, 0.)
        txm.move_sample(1, 2, 3, 45)
        self.assertEqual(txm.Motor_Sample_Top_X, 1)
        self.assertEqual(txm.Motor_SampleY, 2)
        self.assertEqual(txm.Motor_Sample_Top_Z, 3)
        self.assertEqual(txm.Motor_SampleRot, 45)
    
    def test_move_energy(self):
        txm = UnpluggedTXM(has_permit=True)
        # Check what happens if we accidentally give the energy in eV
        with self.assertRaises(exceptions_.EnergyError):
            txm.move_energy(8500)
        # Check that the PVs are set properly
        txm.EnergyWait = 0
        txm.DCMmvt = 14
        txm.DCMputEnergy = 8.5
        txm.CCD_Motor = 3400
        txm.move_energy(8.6)
        self.assertEqual(txm.DCMmvt, 14)
    
    def test_setup_tiff_writer(self):
        txm = UnpluggedTXM(has_permit=True)
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
        txm = UnpluggedTXM(has_permit=True)
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
        log.error("test_setup_detector() needs to be checked")
        txm = UnpluggedTXM(has_permit=False)
        txm.pg_external_trigger = False
        txm.setup_detector(live_display=False)
        # Check that PV values were set
        self.assertEqual(txm.Cam1_Display, False)
        self.assertEqual(txm.Cam1_ImageMode, 'Single')
        self.assertEqual(txm.Cam1_ArrayCallbacks, 'Enable')
        self.assertEqual(txm.SetSoftGlueForStep, '0')
        self.assertEqual(txm.Cam1_FrameRateOnOff, 0)
        self.assertEqual(txm.Cam1_TriggerMode, "Overlapped")
    
    def test_setup_hdf_writer(self):
        txm = UnpluggedTXM(has_permit=True)
        txm.Proc1_ArrayPort = "test_value"
        txm.setup_hdf_writer(num_projections=3, write_mode="stream")
        # Test without recursive filter
        self.assertEqual(txm.Proc1_Filter_Enable, "Disable")
        self.assertEqual(txm.HDF1_ArrayPort, 'test_value')
        self.assertEqual(txm.HDF1_NumCapture, 3)
        self.assertEqual(txm.HDF1_FileWriteMode, 'stream')
        self.assertEqual(txm.HDF1_Capture, 1)
        self.assertTrue(txm.hdf_writer_ready)
    
    def test_setup_hdf_writer_recursive(self):
        txm = UnpluggedTXM(has_permit=True)
        txm.Proc1_ArrayPort = "test_value"
        txm.setup_hdf_writer(num_recursive_images=3,
                             num_projections=3, write_mode="stream")
        # Test with recursive filter
        self.assertEqual(txm.Proc1_Callbacks, "Enable")
        self.assertEqual(txm.Proc1_Filter_Enable, "Enable")
        self.assertEqual(txm.Proc1_Filter_Type, txm.RECURSIVE_FILTER_TYPE)
        self.assertEqual(txm.HDF1_ArrayPort, 'PROC1')
        self.assertEqual(txm.Proc1_Num_Filter, 3)
        self.assertEqual(txm.Proc1_Reset_Filter, 1)
        self.assertEqual(txm.Proc1_AutoReset_Filter, 'Yes')
        self.assertEqual(txm.Proc1_Filter_Callbacks, 'Array N only')
        # These should be the same regardless of recursion filter
        self.assertEqual(txm.HDF1_FileWriteMode, 'stream')
        self.assertEqual(txm.HDF1_Capture, 1)
        self.assertTrue(txm.hdf_writer_ready)
    
    @mock.patch('aps_32id.txm.EpicsPV')
    def test_open_shutters(self, EpicsPV):
        txm = UnpluggedTXM(has_permit=True)
        with warnings.catch_warnings(record=True) as w:
            txm.is_attached = True
            txm.use_shutter_A = False
            txm.use_shutter_B = False
            txm.shutters_are_open = True
            txm.open_shutters()
            self.assertEqual(len(w), 1)
            self.assertFalse(txm.shutters_are_open)
        # Now check with only shutter A
        txm = UnpluggedTXM(has_permit=True, use_shutter_A=True,
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
    
    def test_close_shutters(self):
        txm = UnpluggedTXM(has_permit=True)
        with warnings.catch_warnings(record=True) as w:
            txm.ShutterA_Move_Status = 1
            txm.ShutterA_Close = None
            txm.ShutterB_Move_Status = 1
            txm.ShutterB_Close = None
            txm.shutters_are_open = True
            txm.use_shutter_A = False
            txm.use_shutter_B = False
            txm.close_shutters()
            self.assertEqual(len(w), 1)
            self.assertEqual(txm.ShutterA_Close, None)
            self.assertEqual(txm.ShutterB_Close, None)
        # Now check with only shutter A
        txm = UnpluggedTXM(has_permit=True, use_shutter_A=True,
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
    
    @unittest.skip('while loop runs forever')
    def test_trigger_projections(self):
        # Currently this test only checks that the method can run without error
        txm = UnpluggedTXM()
        txm._trigger_projections(num_projections=3)
    
    def test_capture_projections(self):
        txm = UnpluggedTXM()
        txm._trigger_projections = mock.MagicMock()
        # Check for warning if collecting with shutters closed
        txm.shutters_are_open = False
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            txm.capture_projections()
            self.assertEqual(len(w), 1, "Did not raise shutter warning")
            self.assertIn('Collecting projections with shutters closed.',
                          str(w[0].message))
        # Test when num_projections is > 1
        txm.shutters_are_open = True
        txm.capture_projections(num_projections=3)
        self.assertEqual(txm.Cam1_FrameType, txm.FRAME_DATA)
        txm._trigger_projections.assert_called_with(num_projections=3)
        # Test when num_projections == 1
        txm.capture_projections(num_projections=1)
        txm._trigger_projections.assert_called_with(num_projections=1)
    
    def test_capture_dark_field(self):
        txm = UnpluggedTXM()
        txm._trigger_projections = mock.MagicMock()
        # Check for warning if collecting with shutters open
        txm.shutters_are_open = True
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            txm.capture_dark_field()
            self.assertEqual(len(w), 1, "Did not raise shutter warning")
            self.assertIn('Collecting dark field with shutters open.',
                          str(w[0].message))
        # Test when calling with multiple projections
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', module='scanlib.txm_pv',
                                    category=RuntimeWarning)
            txm.close_shutters()
        txm._trigger_projections.reset_mock()
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', module='aps_32id', category=RuntimeWarning)
            txm.capture_dark_field(num_projections=3)
        self.assertEqual(txm.Cam1_FrameType, txm.FRAME_DARK)
        txm._trigger_projections.assert_called_once_with(num_projections=3)
        # Test when calling only one projection
        txm._trigger_projections.reset_mock()
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', module='aps_32id', category=RuntimeWarning)
            txm.capture_dark_field(num_projections=1)
        txm._trigger_projections.assert_called_once_with(num_projections=1)
    
    def test_capture_flat_field(self):
        txm = UnpluggedTXM()
        txm._trigger_projections = mock.MagicMock()
        # Check for warning if collecting with shutters closed
        txm.shutters_are_open = False
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            txm.capture_white_field()
            self.assertEqual(len(w), 1, "Did not raise shutter warning")
            self.assertIn('Collecting white field with shutters closed.', str(w[0].message))
        # Test for collecting multiple projections
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', module='aps_32id', category=RuntimeWarning)
            txm.open_shutters()
        txm._trigger_projections.reset_mock()
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', module='aps_32id', category=RuntimeWarning)
            txm.capture_white_field(num_projections=3)
        self.assertEqual(txm.Cam1_FrameType, txm.FRAME_WHITE)
        txm._trigger_projections.assert_called_with(num_projections=3)
        # Test when calling only one projection
        txm._trigger_projections.reset_mock()
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', module='aps_32id', category=RuntimeWarning)
            txm.capture_white_field(num_projections=1)
        txm._trigger_projections.assert_called_once_with(num_projections=1)
    
    def test_reset_ccd(self):
        txm = UnpluggedTXM()
        txm.Cam1_ImageMode = mock.MagicMock()
        # Set some fake intial values to check if they change
        txm.Cam1_TriggerMode = "Nonsense"
        txm.wait_pv = mock.MagicMock()
        # txm.Proc1_Filter_Callbacks = "more nonsense"
        txm.reset_ccd()
        # Check that new values were set
        self.assertEqual(txm.Cam1_TriggerMode, "Internal")
        self.assertEqual(txm.Proc1_Filter_Callbacks, "Every array")
        self.assertEqual(txm.Cam1_ImageMode, "Continuous")
        self.assertEqual(txm.Cam1_Display, 1)
        self.assertEqual(txm.Cam1_Acquire, txm.DETECTOR_ACQUIRE)
        # Check that the method waits for cam1_acquire
        txm.wait_pv.assert_called_once_with('Cam1_Acquire', txm.DETECTOR_ACQUIRE, timeout=2)

    def test_sample_position(self):
        txm = UnpluggedTXM()
        txm.Motor_Sample_Top_X = 3
        txm.Motor_SampleY = 5
        txm.Motor_Sample_Top_Z = 7
        txm.Motor_SampleRot = 9
        self.assertEqual(txm.sample_position(), (3, 5, 7, 9))
    
    def test_run_scan(self):
        txm = UnpluggedTXM(has_permit=True)
        # Set the initial values
        init_position = (3., 4, 5, 90)
        txm.move_sample(*init_position)
        E_init = 8.7
        txm.move_energy(8.7)
        with txm.run_scan():
            # Change the values inside the manager
            txm.move_sample(1, 2, 3, 45)
            txm.move_energy(9)
        # Check that the value was restored when the context completed
        self.assertEqual(txm.sample_position(), init_position)
        self.assertEqual(txm.energy(), 8.7)
