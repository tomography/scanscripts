# Logging
import logging
logging.basicConfig(level=logging.WARNING)

import unittest
import mock
import sys
import os

import energy_scan
from txm import TXM

log = logging.getLogger(__name__)
log.debug('Beginning tests in {}'.format(__name__))

# Set some faster options for testing
energy_scan.variableDict['ExposureTime'] = 0.001
energy_scan.variableDict['StabilizeSleep_ms'] = 0.001

class EnergyScanTests(unittest.TestCase):
    def setUp(self):
        self.txm = TXM(is_attached=False,
                       has_permit=True)
    
    def test_start_scan(self, *args):
        if os.path.exists('/tmp/test_file.h5'):
            os.remove('/tmp/test_file.h5')
        self.txm.HDF1_FullFileName_RBV = '/tmp/test_file.h5'
        energy_scan.start_scan(self.txm)
