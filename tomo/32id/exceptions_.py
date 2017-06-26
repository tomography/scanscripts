class EnergyError(ValueError):
    """The energy requested is outside the acceptable range for the given
    task.
    
    """
    pass

class PermitError(RuntimeError):
    """The TXM tried to do something the required a shutter permit but
    didn't have one.
    
    """
    pass

class TimeoutError(RuntimeError):
    """Took too long connecting to a PV."""
    pass
