from enum import Enum


class CouplerPosition(Enum):
    """
    Physical location of a coupler on a piece of rolling stock.

    FRONT:
        The coupler located at the front end of the car.

    REAR:
        The coupler located at the rear end of the car.

    Each RollingStock instance owns exactly two couplers:
        - front_coupler
        - rear_coupler

    Couplers connect directly to another coupler to form the
    physical links that define a consist.
    """

    FRONT = "front"
    REAR = "rear"


class TraversalDirection(Enum):
    """
    Direction used when walking through a consist.

    IMPORTANT:
    TraversalDirection does NOT refer to the physical direction
    a train is moving. It describes which neighboring car should
    be visited next when traversing the consist topology.

    The consist order is defined from HEAD -> REAR.

    Direction mapping:

        FORWARD
            Move toward the rear end of the consist.
            Follow the *rear coupler* of the current car.

        REVERSE
            Move toward the head end of the consist.
            Follow the *front coupler* of the current car.

    Example consist:

        A --- B --- C

    If the current car is B:

        TraversalDirection.FORWARD
            B.rear_coupler -> C

        TraversalDirection.REVERSE
            B.front_coupler -> A

    This distinction avoids confusion between:
        - train movement
        - physical orientation of a car
        - traversal of the consist graph
    """

    FORWARD = "forward"
    REVERSE = "reverse"


# determine if a particular piece of RollingStock is fit for service
class RollingStockCondition(Enum):
    IN_SERVICE = "in_service"
    DAMAGED = "damaged"
    BAD_ORDER = "bad_order"
    IN_SHOP = "in_shop"
    RETIRED = "retired"


class MaintenanceStatus(Enum):
    NONE = "none"
    SCHEDULED = "scheduled"
    DUE_SOON = "due_soon"
    OVERDUE = "overdue"


class RollingStockEventType(Enum):
    CREATED = "created"
    RENAMED = "renamed"
    INSPECTED = "inspected"
    DAMAGED = "damaged"
    BAD_ORDERED = "bad_ordered"
    MAINTENANCE_SCHEDULED = "maintenance_scheduled"
    MAINTENANCE_COMPLETED = "maintenance_completed"
    RELEASED_TO_SERVICE = "released_to_service"
    ASSIGNED_TO_TRAIN = "assigned_to_train"
    REMOVED_FROM_TRAIN = "removed_from_train"
    DERAILED = "derailed"
    HAZMAT_LEAK = "hazmat_leak"
    MECHANICAL_FAILURE = "mechanical_failure"
    LOAD_SHIFT = "load_shift"


class EventSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    MAJOR = "major"
    CRITICAL = "critical"


class TrainEventType(Enum):
    CREATED = "created"
    CONSIST_ASSIGNED = "consist_assigned"
    CONSIST_CHANGED = "consist_changed"
    CONSIST_RELEASED = "consist_released"
    DEPARTED = "departed"
    ARRIVED = "arrived"
    HELD = "held"
    COMPLETED = "completed"
    CANCELED = "canceled"
    CAR_ADDED = "car_added"
    CAR_REMOVED = "car_removed"
    ROLLING_STOCK_DAMAGED = "rolling_stock_damaged"
    ROLLING_STOCK_DERAILED = "rolling_stock_derailed"
    HAZMAT_LEAK_REPORTED = "hazmat_leak_reported"
    MECHANICAL_FAILURE_REPORTED = "mechanical_failure_reported"
    LOAD_SHIFT_REPORTED = "load_shift_recorded"
    EMERGENCY_STOPPED = "emergency_stopped"
    INCIDENT_REPORTED = "incident_reported"


class TrainStatus(Enum):
    PLANNED = "planned"
    ACTIVE = "active"
    HELD = "held"
    COMPLETED = "completed"
    CANCELED = "canceled"
    EMERGENCY_STOPPED = "emergency_stopped"


# Track level enums
class TrackEnd(str, Enum):
    A = "A"
    B = "B"


class TrackType(str, Enum):
    MAINLINE = "mainline"
    SIDING = "siding"
    YARD = "yard"
    INDUSTRIAL = "industrial"
    STAGING = "staging"


class TrackCondition(str, Enum):
    CLEAR = "clear"
    SNOW_COVERED = "snow_covered"
    DAMAGED = "damaged"
    RESTRICTED = "restricted"
    OUT_OF_SERVICE = "out_of_service"


class TrackTrafficRule(str, Enum):
    BIDIRECTIONAL = "bidirectional"
    A_TO_B_ONLY = "a_to_b_only"
    B_TO_A_ONLY = "b_to_a_only"


class TravelDirection(str, Enum):
    TOWARD_A = "toward_a"
    TOWARD_B = "toward_b"
    STATIONARY = "stationary"


class MovementState(str, Enum):
    STATIONARY = "stationary"
    MOVING = "moving"
