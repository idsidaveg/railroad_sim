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
