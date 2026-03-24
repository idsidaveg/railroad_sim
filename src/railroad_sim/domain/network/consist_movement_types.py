"""
Execution-layer movement types for Consist displacement.

This module defines:
- MoveCommand: operator intent (forward / reverse)
- MovementExecutionResult: result of moving a ConsistExtent through the network

These types sit *above* topology movement (movement_service.py)
and *below* application/simulation layers.

They operate directly on:
- ConsistExtent
- ConsistFootprint
- Turnout evaluation results
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict

from railroad_sim.domain.network.position_types import (
    ConsistExtent,
    ConsistFootprint,
)
from railroad_sim.domain.network.topology_movement_enums import (
    MovementBlockReason,
)
from railroad_sim.domain.network.turnout_occupancy import (
    TurnoutFoulingState,
)


class MoveCommand(str, Enum):
    """
    Operator-issued movement command.

    NOTE:
    This is intentionally separate from TravelDirection.

    - MoveCommand: what we are trying to do NOW
    - TravelDirection: orientation of the consist on the network
    """

    FORWARD = "forward"
    REVERSE = "reverse"


@dataclass(frozen=True, slots=True)
class MovementExecutionResult:
    """
    Result of executing a movement command on a ConsistExtent.

    This replaces the current "stage snapshot" concept with a
    deterministic, computed movement outcome.

    Attributes:
        requested_distance_ft:
            Distance requested by caller.

        actual_distance_ft:
            Distance successfully traveled. May be less than requested
            if movement is limited by topology.

        prior_extent:
            Extent before movement.

        new_extent:
            Extent after movement.

        footprint:
            Derived footprint after movement.

        turnout_states:
            Turnout fouling results after movement.

        movement_limited:
            True if movement stopped before requested distance.

        stop_reason:
            Optional reason for early stop (e.g., "end_of_track",
            "no_valid_path", etc.)
    """

    requested_distance_ft: float
    actual_distance_ft: float

    prior_extent: ConsistExtent
    new_extent: ConsistExtent

    footprint: ConsistFootprint

    turnout_states: Dict[str, TurnoutFoulingState]

    movement_limited: bool = False
    stop_reason: MovementBlockReason = MovementBlockReason.NONE

    # -------------------------
    # Convenience properties
    # -------------------------

    @property
    def distance_shortfall_ft(self) -> float:
        """
        How much requested movement was not achieved.
        """
        return max(0.0, self.requested_distance_ft - self.actual_distance_ft)

    @property
    def moved_full_distance(self) -> bool:
        """
        True if full requested distance was achieved.
        """
        return not self.movement_limited

    # -------------------------
    # Debug helpers
    # -------------------------

    def summary(self) -> str:
        """
        Short human-readable summary for logging/debugging.
        """
        base = (
            f"Move {self.requested_distance_ft:.1f} ft "
            f"(actual {self.actual_distance_ft:.1f} ft)"
        )

        if self.movement_limited:
            reason = f", reason={self.stop_reason}" if self.stop_reason else ""
            return base + f" [LIMITED{reason}]"

        return base
