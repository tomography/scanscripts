# -*- coding: utf-8 -*-

"""Classes for interactions between the TXM class and the real TXM.

TxmPV
  A descriptor for the process variables used by the microscopes.

"""

import logging
import warnings

from epics import PV as EpicsPV

import exceptions_

log = logging.getLogger(__name__)


class TxmPV(object):
    """A descriptor representing a process variable in the EPICS system.
    
    This allows accessing process variables as if they were object
    attributes. If the descriptor owner (ie. TXM) is not attached,
    this descriptor performs like a regular attribute. Optionally,
    this can also be done for objects that have no shutter permit.
    
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
    
    class PVPromise():
        is_complete = False
        result = None
    
    def __init__(self, pv_name, dtype=None, permit_required=False,
                 wait=True, as_string=False):
        # Set default values
        self._namestring = pv_name
        self.dtype = dtype
        self.permit_required = permit_required
        self.wait = wait
        self.as_string = as_string
    
    def epics_PV(self, txm):
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
        # Ask the PV for an updated value if possible
        pv_name = self.pv_name(txm)
        result = txm.pv_get(pv_name, as_string=self.as_string)
        # Convert to correct datatype if given
        if self.dtype is not None:
            try:
                result = self.dtype(result)
            except TypeError:
                msg = "Could not cast {} to type {}".format(result, self.dtype)
                warnings.warn(msg, RuntimeWarning)
                log.warn(msg)
        return result
    
    def __set__(self, txm, val):
        pv_name = self.pv_name(txm)
        log.debug("Setting PV value %s: %s", pv_name, val)
        self.txm = txm
        # Check that the TXM has shutter permit if required for this PV
        if (not self.permit_required) or txm.has_permit:
            # Set the PV, but only if the TXM has the required permits)
            was_successful = txm.pv_put(pv_name=pv_name, value=val,
                                        wait=self.wait)
            # Check that setting the new value was successful
            if not was_successful:
                msg = "Error waiting on response from PV {}".format(str(self))
                log.error(msg)
                raise exceptions_.PVError(msg)
        else:
            # There's a valid TXM but we can't operate this PV
            msg = "PV {pv} was not set because TXM doesn't have beamline permit."
            msg = msg.format(pv=pv_name)
            warnings.warn(msg, RuntimeWarning)
            log.warning(msg)
    
    def complete_put(self, data, pvname):
        log.debug("Completed put for %s", self)
        promise = data
        promise.is_complete = True
    
    def __set_name__(self, txm, name):
        self.name = name
    
    def __str__(self):
        return getattr(self, 'name', self._namestring)
    
    def __repr__(self):
        return "<TxmPV: {}>".format(self._namestring)
