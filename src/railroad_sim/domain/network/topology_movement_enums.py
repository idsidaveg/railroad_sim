from __future__ import annotations

from enum import Enum


class MovementOptionKind(str, Enum):
    TRACK = "track"
    BOUNDARY = "boundary"


class MovementBlockReason(str, Enum):
    # Topology / routing
    NONE = "none"
    CONTACT = "contact"
    NO_PATH = "no_path"
    TRACK_CONDITION = "track_condition"
    ROUTE_MISALIGNED = "route_misaligned"
    INVALID_SOURCE = "invalid_source"
    INVALID_DESTINATION = "invalid_destination"

    # Boundary / network transition
    BOUNDARY_EXIT = "boundary_exit"

    # Movement ambiguity / invalid state
    AMBIGUOUS_CONTINUATION = "ambiguous_continuation"
    INVALID_TRACK_OPTION = "invalid_track_option"
    TRACK_OCCUPIED = "track_occupied"

    # Turntable constraints
    TURNTABLE_BRIDGE_LENGTH_EXCEEDED = "turntable_bridge_length_exceeded"
    TURNTABLE_BRIDGE_WEIGHT_EXCEEDED = "turntable_bridge_weight_exceeded"
    TURNTABLE_BRIDGE_AXLE_LOAD_EXCEEDED = "turntable_bridge_axle_load_exceeded"
