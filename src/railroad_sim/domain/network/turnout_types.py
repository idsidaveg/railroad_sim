from enum import Enum


class TurnoutHand(str, Enum):
    LEFT = "left"
    RIGHT = "right"


class TurnoutRouteKind(str, Enum):
    NORMAL = "normal"
    DIVERGING = "diverging"
