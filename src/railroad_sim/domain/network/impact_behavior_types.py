from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ConsistImpactBehavior:
    """
    Post-impact behavior allocation for one consist involved in an impact event.
    """

    consist_id: UUID
    bounce_distance_ft: float = 0.0
    push_through_distance_ft: float = 0.0
    ripple_depth: int = 0


@dataclass(frozen=True, slots=True)
class ImpactBehaviorResult:
    """
    Full post-impact behavior result for both consists involved in one event.
    """

    moved_consist: ConsistImpactBehavior
    other_consist: ConsistImpactBehavior
    incident_required: bool = False
