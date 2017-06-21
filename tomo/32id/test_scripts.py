# Logging
import logging
logging.basicConfig(level=logging.DEBUG)

import unittest
import mock
import sys

import energy_scan

log = logging.getLogger(__name__)
log.debug('Beginning tests')

# @mock.patch('energy_scan.PV')
class EnergyScanTests(unittest.TestCase):
    def test_init(self, *args):
        energy_scan.start_scan()
        assert False, "Write some tests!"
