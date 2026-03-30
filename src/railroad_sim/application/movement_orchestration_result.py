from __future__ import annotations

from dataclasses import dataclass

from railroad_sim.domain.network.consist_movement_types import MovementExecutionResult
from railroad_sim.domain.network.post_contact_resolution_service import (
    PostContactResolutionResult,
)


@dataclass(frozen=True, slots=True)
class MovementOrchestrationResult:
    movement_result: MovementExecutionResult
    post_contact_result: PostContactResolutionResult | None = None
