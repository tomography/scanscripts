from unittest import mock
from aps_32id.txm import NanoTXM

class UnpluggedTXM(NanoTXM):
    pv_queue = []
    _pv_dict = {
        'ioc_sample_X': 7,
        '32ida:BraggEAO.VAL': 8.7, # DMCputEnergy
        '32idcTXM:mxv:c1:m6.VAL': 3400, # CCD_Motor
    }
    _put_kwargs = {}
    _get_kwargs = {}
    ioc_prefix = ''
    
    def pv_get(self, pv_name, *args, **kwargs):
        self._get_kwargs[pv_name] = kwargs
        return self._pv_dict.get(pv_name, None)
    
    def wait_pv(self, *args, **kwargs):
            return True
    
    def _pv_put(self, pv_name, value, *args, **kwargs):
        self._pv_dict[pv_name] = value
        return True


class TXMStub(UnpluggedTXM):
    # Mocked versions of the methods
    wait_pv = mock.MagicMock()
    _trigger_projections = mock.MagicMock()
    capture_projections = mock.MagicMock()
    capture_dark_field = mock.MagicMock()
    setup_hdf_writer = mock.MagicMock()
    setup_detector = mock.MagicMock()
