from __future__ import annotations

from railroad_sim.domain.network.coupling_types import CouplingOutcome, CouplingResult
from railroad_sim.domain.network.impact_severity import compute_impact_severity
from railroad_sim.domain.network.impact_types import ImpactOutcome, ImpactResult


class ImpactService:
    """
    Post-contact impact evaluation for cases where coupling did not occur.

    v1 behavior:
    - COUPLED -> NO_IMPACT
    - TOO_FAST_TO_COUPLE -> SOFT_BOUNCE
    - all other non-coupled outcomes -> NO_IMPACT

    This keeps the first implementation intentionally small and leaves room
    for future escalation into damage/collision logic.
    """

    def evaluate_from_coupling_result(
        self,
        *,
        coupling_result: CouplingResult,
        closing_speed_mph: float,
        moved_mass_lb: float,
        other_mass_lb: float,
        hard_collision_speed_mph: float = 12.0,
    ) -> ImpactResult:
        if closing_speed_mph < 0:
            raise ValueError("closing_speed_mph must be >= 0")

        if hard_collision_speed_mph < 0:
            raise ValueError("hard_collision_speed_mph must be >= 0")

        severity_score = compute_impact_severity(
            closing_speed_mph=closing_speed_mph,
            moved_mass_lb=moved_mass_lb,
            other_mass_lb=other_mass_lb,
        )

        if coupling_result.outcome is CouplingOutcome.COUPLED:
            return ImpactResult(
                outcome=ImpactOutcome.NO_IMPACT,
                moved_consist_id=coupling_result.moved_consist_id,
                other_consist_id=coupling_result.other_consist_id,
                severity_score=severity_score,
            )

        if coupling_result.outcome is CouplingOutcome.TOO_FAST_TO_COUPLE:
            if closing_speed_mph >= hard_collision_speed_mph:
                return ImpactResult(
                    outcome=ImpactOutcome.HARD_COLLISION,
                    moved_consist_id=coupling_result.moved_consist_id,
                    other_consist_id=coupling_result.other_consist_id,
                    severity_score=severity_score,
                )

            return ImpactResult(
                outcome=ImpactOutcome.SOFT_BOUNCE,
                moved_consist_id=coupling_result.moved_consist_id,
                other_consist_id=coupling_result.other_consist_id,
                severity_score=severity_score,
            )

        return ImpactResult(
            outcome=ImpactOutcome.NO_IMPACT,
            moved_consist_id=coupling_result.moved_consist_id,
            other_consist_id=coupling_result.other_consist_id,
            severity_score=severity_score,
        )
