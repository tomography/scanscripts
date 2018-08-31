"""Unit tests for the transmission x-ray microscope `TXM()` class."""

import logging
logging.basicConfig(level=logging.WARNING)
logging.captureWarnings(True)
import os
from contextlib import contextmanager

import six
import time
import unittest
if six.PY2:
    import mock
else:
    from unittest import mock
import warnings
import epics

from aps_32id.txm import NanoTXM, permit_required, txm_config
import aps_32id.txm as txm_module
from scanlib import TxmPV, exceptions_
from tools import UnpluggedTXM


log = logging.getLogger(__name__)
log.debug('Beginning tests in {}'.format(__name__))

# Flags for determining which tests to run
HAS_PERMIT = txm_config()['32-ID-C'].getboolean('has_permit')
TXM_CONNECTED = epics.get_pv('32idb:AShtr:UserArm', connect=True).connected

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


@unittest.skipUnless(TXM_CONNECTED, 'TXM not connected')
class SystemTests(unittest.TestCase):
    
    @contextmanager
    def filter_permit_warnings(self):
        """Context manager to filter out warnings resulting from no permit."""
        with warnings.catch_warnings():
            
            warnings.filterwarnings(
                'ignore', message='Collecting projections with shutters closed.')
            warnings.filterwarnings(
                'ignore', message='Shutters not closed because TXM does not have permit')
            warnings.filterwarnings(
                'ignore', message='Could not cast 32ida:BraggEAO.VAL = None')
            yield

    """System-level tests that require the TXM to be connected."""
    def test_fast_shutter(self):
        """Make sure the fast shutter responds to triggers."""
        with self.filter_permit_warnings():
            txm = NanoTXM(has_permit=False)
            with txm.run_scan():
                # Prepare the detector for capture
                txm.enable_fast_shutter()
                self.assertEqual(txm.Fast_Shutter_Control, txm.FAST_SHUTTER_CONTROL_AUTO)
                exposure = 0.5 # seconds
                txm.setup_detector(1, exposure=exposure)
                self.assertEqual(txm.Cam1_Acquire, txm.DETECTOR_ACQUIRE)
                # Trigger an exposure
                txm.Cam1_SoftwareTrigger = 1
                # Check that the acquisition finished
                time.sleep(exposure + 0.1)
                self.assertEqual(txm.Cam1_Acquire, txm.DETECTOR_IDLE)
        
    def test_projections_with_fast_shutter(self):
        """Make sure projects can be triggered with the fast shutter."""
        with self.filter_permit_warnings():
            txm = NanoTXM(has_permit=False)
            with txm.run_scan():
                # Collect some projections and wait for them to finish
                n_prj = 5
                txm.setup_detector(num_projections=n_prj, exposure=0.5)
                txm.enable_fast_shutter()
                txm.capture_projections(n_prj)


class TXMUnitTests(unittest.TestCase):
    
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
        txm.zone_plate_drift_x = 0.1
        txm.zone_plate_drift_y=-0.2
        # Check what happens if we accidentally give the energy in eV
        with self.assertRaises(exceptions_.EnergyError):
            txm.move_energy(8500)
        # Check that the PVs are set properly
        txm.EnergyWait = 0
        txm.DCMmvt = 14
        txm.DCMputEnergy = 8.5
        txm.CCD_Motor = 3400
        txm.zone_plate_x = 1
        txm.zone_plate_y = 2
        txm.zone_plate_z = 70
        txm.move_energy(8.6)
        self.assertEqual(txm.DCMmvt, 14)
        # Check that the zoneplate is moved correctly
        dz = txm.zone_plate_z - 70
        self.assertEqual(txm.zone_plate_x, 1 + dz * 0.1)
        self.assertEqual(txm.zone_plate_y, 2 - dz * 0.2)
    
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
        txm = UnpluggedTXM(has_permit=False)
        txm.pg_external_trigger = False
        txm.setup_detector(num_projections=35, exposure=1.3)
        # Check that PV values were set
        self.assertEqual(txm.Cam1_Display, True)
        self.assertEqual(txm.Cam1_ImageMode, 'Multiple')
        self.assertEqual(txm.Cam1_ArrayCallbacks, 'Enable')
        self.assertEqual(txm.Fast_Shutter_Exposure, 1.3)
        self.assertEqual(txm.Cam1_FrameRateOnOff, 0)
        self.assertEqual(txm.Cam1_TriggerMode, "Ext. Standard")
        self.assertEqual(txm.Cam1_NumImages, 35)
        self.assertEqual(txm.Cam1_Acquire, txm.DETECTOR_ACQUIRE)
    
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
    
    def test_enable_fast_shutter(self):
        txm = UnpluggedTXM(has_permit=True)
        # Test with software trigger
        txm.enable_fast_shutter(rotation_trigger=False, delay=1.5)
        # Check the state
        self.assertEqual(txm.Fast_Shutter_Trigger_Mode,
                         txm.FAST_SHUTTER_TRIGGER_MANUAL)
        self.assertEqual(txm.Fast_Shutter_Control,
                         txm.FAST_SHUTTER_CONTROL_AUTO)
        self.assertEqual(txm.Fast_Shutter_Relay,
                         txm.FAST_SHUTTER_RELAY_SYNCED)
        self.assertEqual(txm.Fast_Shutter_Trigger_Source,
                         txm.FAST_SHUTTER_TRIGGER_ENCODER)
        self.assertEqual(txm.Fast_Shutter_Delay,
                         1.5)
        self.assertEqual(txm.Fast_Shutter_Open,
                         txm.FAST_SHUTTER_CLOSED)
        self.assertTrue(txm.fast_shutter_enabled)
        # Test with rotation trigger
        txm.enable_fast_shutter(rotation_trigger=True)
        # Check the state
        self.assertEqual(txm.Fast_Shutter_Trigger_Mode,
                         txm.FAST_SHUTTER_TRIGGER_ROTATION)
    
    def test_disable_fast_shutter(self):
        txm = UnpluggedTXM(has_permit=True)
        # Set the wrong values first
        txm.Fast_Shutter_Trigger_Mode = txm.FAST_SHUTTER_TRIGGER_MANUAL
        txm.Fast_Shutter_Control = txm.FAST_SHUTTER_CONTROL_AUTO
        txm.Fast_Shutter_Relay = txm.FAST_SHUTTER_RELAY_SYNCED
        txm.Fast_Shutter_Trigger_Source = -1
        # Test with software trigger
        txm.disable_fast_shutter()
        # Check the state
        self.assertEqual(txm.Fast_Shutter_Trigger_Mode,
                         txm.FAST_SHUTTER_TRIGGER_ROTATION)
        self.assertEqual(txm.Fast_Shutter_Control,
                         txm.FAST_SHUTTER_CONTROL_MANUAL)
        self.assertEqual(txm.Fast_Shutter_Relay,
                         txm.FAST_SHUTTER_RELAY_DIRECT)
        self.assertEqual(txm.Fast_Shutter_Trigger_Source,
                         txm.FAST_SHUTTER_TRIGGER_ENCODER)
        self.assertEqual(txm.Fast_Shutter_Open,
                         txm.FAST_SHUTTER_OPEN)
        self.assertFalse(txm.fast_shutter_enabled)
    
    def test_open_shutters(self):
        txm = UnpluggedTXM(has_permit=True)
        with warnings.catch_warnings(record=True) as w:
            txm.use_shutter_A = False
            txm.use_shutter_B = False
            txm.shutters_are_open = True
            txm.open_shutters()
            self.assertEqual(len(w), 1)
            self.assertFalse(txm.shutters_are_open)
        # Now check with only shutter A
        txm = UnpluggedTXM(has_permit=True)
        txm.use_shutter_A = True
        txm.use_shutter_B = False
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
        txm = UnpluggedTXM(has_permit=True)
        txm.use_shutter_A = True
        txm.use_shutter_B = False
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
    
    def test_trigger_projection(self):
        # Currently this test only checks that the method can run without error
        txm = UnpluggedTXM()
        txm.Cam1_NumImagesCounter = 0
        txm._trigger_projection()
    
    def test_capture_projections(self):
        txm = UnpluggedTXM()
        txm._trigger_projection = mock.MagicMock()
        # Check for warning if collecting with shutters closed
        txm.shutters_are_open = False
        with warnings.catch_warnings(record=True) as w:
            txm_module.__warningregistry__.clear()            
            warnings.simplefilter('always')
            txm.capture_projections()
            self.assertEqual(len(w), 1, "Did not raise shutter warning")
            self.assertIn('Collecting projections with shutters closed.',
                          str(w[0].message))
        # Test when num_projections is > 1
        txm._trigger_projection.reset_mock()
        txm.shutters_are_open = True
        txm.capture_projections(num_projections=3)
        self.assertEqual(txm.Cam1_FrameType, txm.FRAME_DATA)
        txm._trigger_projection.assert_called_with()
        self.assertEqual(txm._trigger_projection.call_count, 3)
        # Test when num_projections == 1
        txm._trigger_projection.reset_mock()
        txm.capture_projections(num_projections=1)
        txm._trigger_projection.assert_called_with()
        self.assertEqual(txm._trigger_projection.call_count, 1)
    
    def test_capture_dark_field(self):
        txm = UnpluggedTXM()
        txm._trigger_projection = mock.MagicMock()
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
            warnings.filterwarnings('ignore', message='Shutters not closed')
            txm.close_shutters()
        txm._trigger_projection.reset_mock()
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', module='aps_32id', category=RuntimeWarning)
            txm.capture_dark_field(num_projections=3)
        self.assertEqual(txm.Cam1_FrameType, txm.FRAME_DARK)
        self.assertEqual(txm._trigger_projection.call_count, 3)
        # Test when calling only one projection
        txm._trigger_projection.reset_mock()
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', module='aps_32id', category=RuntimeWarning)
            txm.capture_dark_field(num_projections=1)
        self.assertEqual(txm._trigger_projection.call_count, 1)
    
    def test_capture_flat_field(self):
        txm = UnpluggedTXM()
        txm._trigger_projection = mock.MagicMock()
        # Check for warning if collecting with shutters closed
        txm.shutters_are_open = False
        with warnings.catch_warnings(record=True) as w:
            warnings.filterwarnings('always', message='collecting white field')
            txm.capture_white_field()
            if six.PY3:
                # For some reason, these warnings are not caught in python 2.7...
                self.assertEqual(len(w), 1, "Did not raise shutter warning")
                self.assertIn('Collecting white field with shutters closed.', str(w[0].message))
        warnings.resetwarnings()
        # Test for collecting multiple projections
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', module='aps_32id', category=RuntimeWarning)
            warnings.filterwarnings('ignore', message=".*TXM doesn't have beamline permit.")
            txm.open_shutters()
        txm._trigger_projection.reset_mock()
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', module='aps_32id', category=RuntimeWarning)
            txm.capture_white_field(num_projections=3)
        self.assertEqual(txm.Cam1_FrameType, txm.FRAME_WHITE)
        txm._trigger_projection.assert_called_with()
        self.assertEqual(txm._trigger_projection.call_count, 3)
        # Test when calling only one projection
        txm._trigger_projection.reset_mock()
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', module='aps_32id', category=RuntimeWarning)
            txm.capture_white_field(num_projections=1)
        txm._trigger_projection.assert_called_with()
        self.assertEqual(txm._trigger_projection.call_count, 1)
    
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
        self.assertEqual(txm._pv_dict['cam1:Acquire'], txm.DETECTOR_ACQUIRE)
        # Check that the method waits for cam1_acquire
        txm.wait_pv.assert_called_once_with('Cam1_Acquire', txm.DETECTOR_ACQUIRE, timeout=2)
    
    def test_sample_position(self):
        txm = UnpluggedTXM()
        txm.Motor_Sample_Top_X = 3
        txm.Motor_SampleY = 5
        txm.Motor_Sample_Top_Z = 7
        txm.Motor_SampleRot = 9
        self.assertEqual(txm.sample_position(), (3, 5, 7, 9))
    
    def test_capture_tomogram_flyscan(self):
        txm = UnpluggedTXM(has_permit=True)
        txm.exposure_time = 0.3
        txm.Fly_Calc_Projections = 360
        txm.HDF1_NumCapture_RBV = 390
        txm.Cam1_NumImages = 370
        # Execute tomogram scan
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', message="Could not retrieve actual angles")
            theta = txm.capture_tomogram_flyscan(0, 180, 360, ccd_readout=0.2)
        # Check set values
        self.assertEqual(txm.Fly_ScanControl, "Standard")
        self.assertEqual(txm.Fly_ScanDelta, 0.5)
        self.assertEqual(txm.Fly_StartPos, 0)
        self.assertEqual(txm.Fly_EndPos, 180)
        self.assertEqual(txm.Fly_SlewSpeed, 1)
        self.assertEqual(txm.Reset_Theta, 1)
        self.assertEqual(txm.Cam1_TriggerMode, "Overlapped")
    
    def test_start_logging(self):
        # Prepare the test resources
        logfile = 'run_scan_test_file.log'
        if os.path.exists(logfile):
            os.remove(logfile)
        txm = UnpluggedTXM(has_permit=True)
        root_logger = logging.getLogger()
        num_handlers = len(logging.getLogger().handlers)
        # Disable the stderr logger for now
        old_handler_level = root_logger.handlers[0].level
        old_root_level = root_logger.level
        # Make sure nothing happens if level=(-1|None)
        txm.start_logging(level=None)
        self.assertEqual(len(root_logger.handlers), num_handlers)
        txm.start_logging(level=-1)
        self.assertEqual(len(root_logger.handlers), num_handlers)
        # Now do some actual logging
        try:
            root_logger.handlers[0].setLevel(logging.WARNING)
            # Test that a new stream handler is added
            with warnings.catch_warnings(record=True) as w:
                txm.start_logging(level=logging.DEBUG)
                if six.PY3:
                    self.assertEqual(len(w), 1)
            self.assertFalse(os.path.exists(logfile))
            handlers = logging.getLogger().handlers
            self.assertEqual(len(handlers), num_handlers + 1)
            self.assertEqual(root_logger.level, logging.DEBUG)
            # Test that a file handler is added if possible
            root_logger.removeHandler(root_logger.handlers[-1])
            txm.HDF1_Capture_RBV = txm.HDF_WRITING
            txm.HDF1_FullFileName_RBV = 'run_scan_test_file.h5'
            txm.start_logging(level=logging.DEBUG)
            self.assertTrue(os.path.exists('run_scan_test_file.log'))
        except:
            # Restore default logging levels
            root_logger.setLevel(old_root_level)
            root_logger.handlers[0].setLevel(old_handler_level)
            raise
        os.remove(logfile)
    
    def test_run_scan(self):
        txm = UnpluggedTXM(has_permit=True)
        txm.zone_plate_x = 0
        txm.zone_plate_y = 0
        txm.zone_plate_z = 70
        # txm.Cam1_AcquireTime = 1.
        # txm.Cam1_AcquirePeriod = 1.
        # Set the initial values
        init_position = (3., 4, 5, 90)
        txm.move_sample(*init_position)
        E_init = 8.7
        txm.move_energy(8.7)
        root_logger = logging.getLogger()
        num_handlers = len(root_logger.handlers)
        old_level = root_logger.level
        if old_level == logging.CRITICAL:
            warnings.warn("Starting at logging.CRITICAL makes this test trivial")
        # Disable the stderr logger for now
        with txm.run_scan():
            # Change that the log handlers are set
            with warnings.catch_warnings():
                warnings.filterwarnings('ignore', message='HDF writer not yet running')
                txm.start_logging(level=logging.CRITICAL)
            self.assertEqual(len(root_logger.handlers), num_handlers + 1)
            # Do some TXM experiment stuff
            txm.move_sample(1, 2, 3, 45)
            txm.move_energy(9)
        # Check that the value was restored when the context completed
        self.assertEqual(txm.sample_position(), init_position)
        self.assertEqual(txm.energy(), 8.7)
        # Check that the logging was restored
        self.assertEqual(root_logger.level, old_level)
        self.assertEqual(len(root_logger.handlers), num_handlers)
