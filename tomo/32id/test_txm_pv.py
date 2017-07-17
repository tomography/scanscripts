"""Unit test for the process variable descriptor."""

import logging
logging.basicConfig(level=logging.WARNING)
import warnings
import six
import unittest
if six.PY2:
    import mock
else:
    from unittest import mock

from epics import PV as EpicsPV, get_pv

from txm_pv import TxmPV


log = logging.getLogger(__name__)


class PVDescriptorTestCase(unittest.TestCase):
    class FakeTXM(object):
        pv_queue = []
        _pv_dict = {'ioc_sample_X': 7}
        _put_kwargs = {}
        _get_kwargs = {}
        ioc_prefix = ''
        
        def pv_put(self, pv_name, value, *args, **kwargs):
            self._pv_dict[pv_name] = value
            self._put_kwargs[pv_name] = kwargs
            return True
        
        def pv_get(self, pv_name, *args, **kwargs):
            self._get_kwargs[pv_name] = kwargs
            return self._pv_dict.get(pv_name, None)
    
    def test_setting_values(self):
        txm = self.FakeTXM()
        x_pv = TxmPV('sample_X')
        x_pv.__set__(txm, 7)
        self.assertEqual(x_pv.__get__(txm), 7)
   
    def test_permit_required(self):
        txm = self.FakeTXM()
        shutter_pv = TxmPV('shutter_state', permit_required=True)
        # Set an "old" value
        txm.has_permit = True
        shutter_pv.__set__(txm, 'closed')
        # Check that the permit_required PV is not changed w/o permit
        txm.has_permit = False
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            shutter_pv.__set__(txm, 'open')
            self.assertEqual(len(w), 1, 'Warning was not issued')
        # Check that the value is still the same
        self.assertEqual(txm._pv_dict['shutter_state'], 'closed')
        # Now give it a permit and check that it works
        txm.has_permit = True
        shutter_pv.__set__(txm, 'open')
        self.assertEqual(txm._pv_dict['shutter_state'], 'open')
   
    def test_pv_name(self):
        txm = self.FakeTXM()
        txm.ioc_prefix = 'myIOC'
        test_pv = TxmPV('{ioc_prefix}_my_pv')
        name = test_pv.pv_name(txm)
        self.assertEqual(name, 'myIOC_my_pv')
    
    def test_dtype(self):
        txm = self.FakeTXM()
        # Make sure the returned value is type-cast if dtype is given
        dtype_pv = TxmPV('my_dtype', dtype=float)
        dtype_pv.__set__(txm, 0)
        self.assertIsInstance(dtype_pv.__get__(txm), float)
    
    def test_extra_args(self):
        # Make sure the extra arguments given to the constructor get
        # pass through to the actual PV.
        txm = self.FakeTXM()
        txm.has_permit = True
        # Check the `wait` argument
        str_pv = TxmPV('string_pv', wait=False)
        str_pv.__set__(txm, 'hello')
        str_pv.__get__(txm)
        self.assertFalse(txm._put_kwargs['string_pv']['wait'],
                         '`wait` parameter not passed to pv_put')
        self.assertNotIn('wait', txm._get_kwargs['string_pv'].keys(),
                         '`wait` parameter passed to _pv_get')
        # Check the `as_string` argument
        str_pv = TxmPV('string_pv', as_string=True)
        str_pv.__set__(txm, 'hello')
        str_pv.__get__(txm)
        self.assertIn('as_string', txm._get_kwargs['string_pv'].keys(),
                      '`as_string` parameter not passed to pv_get')
        self.assertNotIn('as_string', txm._put_kwargs['string_pv'].keys(),
                         '`as_string` parameter passed to _pv_put')
