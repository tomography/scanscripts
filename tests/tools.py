import six
if six.PY2:
    import mock
else:
    from unittest import mock
from aps_32id.txm import NanoTXM

class UnpluggedTXM(NanoTXM):
    _pv_dict = {
        'ioc_sample_X': 7,
        '32ida:BraggEAO.VAL': 8.7, # DMCputEnergy
        '32idcTXM:mxv:c1:m6.VAL': 3400, # CCD_Motor
    }
    ioc_prefix = ''

    def __init__(self, *args, **kwargs):
        self.pv_queue = []
        self._put_calls = []
        self._get_kwargs = {}
        super(UnpluggedTXM, self).__init__(*args, **kwargs)
    
    def pv_get(self, pv_name, *args, **kwargs):
        if pv_name == 'cam1:Acquire':
            # This prevents stalling when triggering projections
            out = NanoTXM.DETECTOR_IDLE
        else:
            self._get_kwargs[pv_name] = kwargs
            out = self._pv_dict.get(pv_name, None)
        return out
    
    def wait_pv(self, *args, **kwargs):
            return True
    
    def _pv_put(self, pv_name, value, *args, **kwargs):
        self._put_calls.append((pv_name, value))
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
    open_shutters = mock.MagicMock()
