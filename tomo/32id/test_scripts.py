# Logging
import logging
logging.basicConfig(level=logging.DEBUG)

import unittest
import mock
import sys

import energy_scan
from txm import TXM

log = logging.getLogger(__name__)
log.debug('Beginning tests in {}'.format(__name__))

class EnergyScanTests(unittest.TestCase):
    def setUp(self):
        self.txm = TXM()
        self.txm.is_attached = False
    
    @mock.patch('energy_scan.wait_pv')
    def test_init(self, *args):
        energy_scan.start_scan(self.txm)
        assert False, "Write some tests!"
    
    def test_stop_scan(self, *args):
        energy_scan.start_scan(self.txm)
        assert False, "How do we call this test?"
