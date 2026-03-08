class RailroadDomainError(Exception):
    """Base exception for all railroad domain rule violations"""

    pass


class CouplerConnectionError(Exception):
    """Raised when a coupler connection cannot be completed"""

    pass


class CouplerStateError(Exception):
    """Raised when a coupler is in an invalid state for the requested operation"""

    pass


class ConsistTopologyError(Exception):
    """Raised when consist topology is invalid, such as a loop (i.e., end of train connected to front of train)"""

    pass


class ConsistOperationError(Exception):
    """Raised when a consist operation cannot be implemented"""

    pass
