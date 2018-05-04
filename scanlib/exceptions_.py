class EnergyError(ValueError):
    """The energy requested is outside the acceptable range for the given
    task.
    
    """
    pass

class PermitError(RuntimeError):
    """The TXM tried to do something requiring a shutter permit, but it
    didn't have one.
    
    """
    pass

class PVError(RuntimeError):
    """A problem occurred trying to interact with process variables."""
    pass

class TimeoutError(RuntimeError):
    """Took too long connecting to a PV."""
    pass

class ConfigurationError(RuntimeError):
    pass
