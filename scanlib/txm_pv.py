# -*- coding: utf-8 -*-

"""Classes for interactions between the TXM class and the real TXM.

TxmPV
  A descriptor for the process variables used by the microscopes.

"""

__author__ = 'Mark Wolf'
__copyright__ = 'Copyright (c) 2017, UChicago Argonne, LLC.'
__docformat__ = 'restructuredtext en'
__platform__ = 'Unix'
__version__ = '1.6'
__all__ = ['TxmPV', 'permit_required']

import logging
import warnings

from epics import PV as EpicsPV

from . import exceptions_

log = logging.getLogger(__name__)


def permit_required(real_func, return_value=None):
    """Decorates a method so it can only open with a permit.
    
    This method decorator ensures that the decorated method can only
    be called on an object that has a shutter permit. If it doesn't,
    then an exceptions is raised:
    
    .. code:: python
        
        class MyTXM(NanoTXM):
            @permit_required
            def open_shutters(self):
                pass
        
        # This will work as expected
        txm = MyTXM(has_permit=True)
        txm.open_shutters()
        
        # This will raise a warning and do nothing else
        txm = MyTXM(has_permit=False)
        txm.open_shutters()
    
    Parameters
    ----------
    real_func
      The function or method to decorate.
    
    """
    def wrapped_func(obj, *args, **kwargs):
        # Inner function that checks the status of permit
        if obj.has_permit and False:
            ret = real_func(obj, *args, **kwargs)
        else:
            msg = "Shutter permit not granted."
            warnings.warn(msg, RuntimeWarning)
            ret = None
        return ret
    return wrapped_func


class PVMonitor():
    """A context manager that updates with the latest PV value.
    
    This uses epics callbacks behind the scenes, so avoids the extra
    overhead of constantly running epics.caget(). The value of
    ``latest_value`` is updated whenever the value changes.

    A common pattern might be to use this within a while loop
    alongside epics.poll() to test when a value has reached a desired
    target.

    .. code:: python

        with PVMonitor(pv_name='my:awesome:motor') as mon:
            while True:
                if mon.latest_value = target_value:
                    break
                else:
                    epics.poll()

    """
    latest_value = None
    def __init__(self, pv_name):
        self.pv_name = pv_name
        self.pv = EpicsPV(self.pv_name)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, typ, value, traceback):
        self.stop()

    def start(self):
        # self.update_value(pvname=self.pv_name, value=self.pv.get())
        self.callback_idx = self.pv.add_callback(self.update_value)

    def stop(self):
        self.pv.remove_callback(self.callback_idx)

    def update_value(self, pvname, value, **kwargs):
        self.latest_value = value


class TxmPV(object):
    """A descriptor representing a process variable in the EPICS system.
    
    This allows accessing process variables as if they were object
    attributes. If the descriptor owner (ie. TXM) is not attached,
    this descriptor performs like a regular attribute. Optionally,
    this can also be done for objects that have no shutter permit. If
    access from a class, rather than an instance, it just returns the
    descriptor itself.
    
    Attributes
    ----------
    put_complete : bool
      If False, there is a pending put operation.
    
    Parameters
    ----------
    pv_name : str
      The name of the process variable to connect to as defined in the
      EPICS system.
    dtype : optional
      If given, the values returned by `PV.get` will be
      typecast. Example: ``dtype=int`` will return
      ``int(PV[pv].get())``.
    permit_required : bool, optional
      If truthy, data will only be sent if the owner `has_permit`
      attribute is true. Reading of process variable is still enabled
      either way.
    wait : bool, optional
      If truthy, setting this descriptor will block until the
      operation succeeds.
    as_string : bool, optional
      If truthy, the string representation of the process variable
      will be given, otherwise the raw bytes will be returned for
      character array variables.

    """
    _epicsPV = None
    put_complete = True
    
    def __init__(self, pv_name, dtype=None, permit_required=False,
                 wait=True, as_string=False):
        # Set default values
        self._namestring = pv_name
        self.dtype = dtype
        self.permit_required = permit_required
        self.wait = wait
        self.as_string = as_string
    
    def epics_PV(self, txm):
        """Gets the underlying epics process variable object.
        
        Goes down one level of abstraction to allow a finer level of
        control if necessary.
        
        """
        # Only create a PV if one doesn't exist or the IOC prefix has changed
        is_cached = (self._epicsPV is not None)
        if not is_cached:
            pv_name = self.pv_name(txm)
            self._epicsPV = EpicsPV(pv_name)
        return self._epicsPV
    
    def pv_name(self, txm):
        """Do string formatting on the pv_name and return the result."""
        return self._namestring.format(ioc_prefix=txm.ioc_prefix)
    
    def __get__(self, txm, type=None):
        if txm is None:
            # Allows for the retrieval of the descriptor itself if
            # called on a class
            result = self
        else:
            # Ask the PV for an updated value if possible
            pv_name = self.pv_name(txm)
            result = txm.pv_get(pv_name, as_string=self.as_string)
            # Convert to correct datatype if given
            if self.dtype is not None:
                try:
                    result = self.dtype(result)
                except TypeError:
                    msg = "Could not cast {} = {} to type {}"
                    msg = msg.format(pv_name, result, self.dtype)
                    warnings.warn(msg, RuntimeWarning)
                    log.warning(msg)
        return result
    
    def __set__(self, txm, val):
        pv_name = self.pv_name(txm)
        log.debug("Setting PV value %s: %s", pv_name, val)
        self.txm = txm
        # Check that the TXM has shutter permit if required for this PV
        if (not self.permit_required) or txm.has_permit:
            # Set the PV, but only if the TXM has the required permits)
            try:
                was_successful = txm.pv_put(pv_name=pv_name, value=val,
                                            wait=self.wait)
            except TypeError:
                was_successful = False
            # Check that setting the new value was successful
            if not was_successful and self.wait:
                msg = "Error setting value to PV {}".format(str(self))
                log.error(msg)
                warnings.warn(msg, RuntimeWarning)
        else:
            # There's a valid TXM but we can't operate this PV
            msg = "PV {pv} was not set because TXM doesn't have beamline permit."
            msg = msg.format(pv=pv_name)
            warnings.warn(msg, RuntimeWarning)
            log.warning(msg)
    
    def __set_name__(self, txm, name):
        self.name = name
        # Create a new version of the docstring
        doc = "The ``{pv_name}`` process variable."
        doc = doc.format(pv_name=self.pv_name(txm))
        self.__doc__ = doc
    
    def __str__(self):
        return getattr(self, 'name', self._namestring)
    
    def __repr__(self):
        return "<TxmPV: {}>".format(self._namestring)
