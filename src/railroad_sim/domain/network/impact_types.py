from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from uuid import UUID


class ImpactOutcome(str, Enum):
    """
    Result of evaluating a non-coupling contact event.
    """

    NO_IMPACT = "no_impact"
    SOFT_BOUNCE = "soft_bounce"
    HARD_COLLISION = "hard_collision"


@dataclass(frozen=True, slots=True)
class ImpactResult:
    """
    Result of evaluating what happened after contact when coupling did not occur.
    """

    outcome: ImpactOutcome
    moved_consist_id: UUID
    other_consist_id: UUID | None = None
    severity_score: float = 0.0
