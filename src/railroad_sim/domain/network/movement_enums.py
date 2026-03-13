from __future__ import annotations

from enum import Enum


class MovementOptionKind(str, Enum):
    TRACK = "track"
    BOUNDARY = "boundary"


class MovementBlockReason(str, Enum):
    NONE = "none"
    NO_PATH = "no_path"
    TRACK_CONDITION = "track_condition"
    ROUTE_MISALIGNED = "route_misaligned"
    INVALID_SOURCE = "invalid_source"
    INVALID_DESTINATION = "invalid_destination"
