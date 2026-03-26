from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from uuid import UUID

from railroad_sim.domain.consist import Consist


class CouplingOutcome(str, Enum):
    """
    Result of evaluating/attempting a coupling after contact.
    """

    COUPLED = "coupled"
    NO_CONTACT = "no_contact"
    INVALID_CONTACT = "invalid_contact"
    OTHER_CONSIST_NOT_FOUND = "other_consist_not_found"
    INVALID_MOVEMENT_DIRECTION = "invalid_movement_direction"
    CONTACT_STOP_REQUIRED = "contact_stop_required"
    TOO_FAST_TO_COUPLE = "too_fast_to_couple"


@dataclass(frozen=True, slots=True)
class CouplingResult:
    """
    Result of attempting to couple a moved consist to another consist.
    """

    outcome: CouplingOutcome
    moved_consist_id: UUID
    other_consist_id: UUID | None = None
    merged_consist: Consist | None = None
