from dataclasses import dataclass

from railroad_sim.domain.network.turnout_types import (
    TurnoutHand,
    TurnoutRouteKind,
)


@dataclass(frozen=True)
class TurnoutZone:
    """
    Represents the physical clearance zone of a turnout.

    This is NOT just geometry — it also defines how the turnout behaves
    depending on routing (normal vs diverging).

    name:
        Unique identifier for the turnout

    clearance_length_ft:
        Distance required to fully clear the fouling point

    hand:
        LEFT or RIGHT turnout (geometry)

    route_kind:
        NORMAL or DIVERGING path currently in use
    """

    name: str
    clearance_length_ft: float
    hand: TurnoutHand
    route_kind: TurnoutRouteKind


@dataclass(frozen=True)
class TurnoutFoulingState:
    """
    Represents whether a turnout is currently fouled.

    turnout_name:
        Must match TurnoutZone.name

    is_fouled:
        True if any part of equipment is within the turnout clearance zone
    """

    turnout_name: str
    is_fouled: bool
    fouling_consist_id: str | None = None
    fouling_equipment_id: str | None = None
    fouling_label: str | None = None
