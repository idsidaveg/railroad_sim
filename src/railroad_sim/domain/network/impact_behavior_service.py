from __future__ import annotations

from railroad_sim.domain.network.impact_behavior_types import (
    ConsistImpactBehavior,
    ImpactBehaviorResult,
)
from railroad_sim.domain.network.impact_types import ImpactOutcome, ImpactResult


class ImpactBehaviorService:
    """
    Derive post-impact behavior for both consists from impact outcome,
    severity, and relative mass.

    v1 rules:
    - NO_IMPACT:
        * no bounce
        * no push-through
        * no ripple
        * no incident

    - SOFT_BOUNCE:
        * bounce only
        * no push-through
        * no ripple
        * no incident

    - HARD_COLLISION:
        * no bounce
        * push-through allowed
        * ripple depth allocated to both consists
        * incident may be required for highest severity band

    Mass rule:
    - lighter consist absorbs more effect
    - heavier consist absorbs less effect
    """

    def evaluate_behavior(
        self,
        *,
        impact_result: ImpactResult,
        moved_mass_lb: float,
        other_mass_lb: float,
        moved_car_count: int | None = None,
        other_car_count: int | None = None,
    ) -> ImpactBehaviorResult:
        if moved_mass_lb < 0:
            raise ValueError("moved_mass_lb must be >= 0")

        if other_mass_lb < 0:
            raise ValueError("other_mass_lb must be >= 0")

        total_mass_lb = moved_mass_lb + other_mass_lb

        # If both masses are zero, split evenly to avoid divide-by-zero.
        if total_mass_lb == 0:
            moved_share = 0.5
            other_share = 0.5
        else:
            # Lighter consist gets larger effect share.
            moved_share = other_mass_lb / total_mass_lb
            other_share = moved_mass_lb / total_mass_lb

        moved_behavior = ConsistImpactBehavior(
            consist_id=impact_result.moved_consist_id,
        )
        other_behavior = ConsistImpactBehavior(
            consist_id=impact_result.other_consist_id
            if impact_result.other_consist_id is not None
            else impact_result.moved_consist_id,
        )

        if impact_result.outcome is ImpactOutcome.NO_IMPACT:
            return ImpactBehaviorResult(
                moved_consist=moved_behavior,
                other_consist=other_behavior,
                incident_required=False,
            )

        if impact_result.outcome is ImpactOutcome.SOFT_BOUNCE:
            base_bounce_ft = self._soft_bounce_distance_ft(impact_result.severity_score)

            moved_behavior = ConsistImpactBehavior(
                consist_id=impact_result.moved_consist_id,
                bounce_distance_ft=round(base_bounce_ft * moved_share, 3),
                push_through_distance_ft=0.0,
                ripple_depth=0,
            )
            other_behavior = ConsistImpactBehavior(
                consist_id=impact_result.other_consist_id
                if impact_result.other_consist_id is not None
                else impact_result.moved_consist_id,
                bounce_distance_ft=round(base_bounce_ft * other_share, 3),
                push_through_distance_ft=0.0,
                ripple_depth=0,
            )

            return ImpactBehaviorResult(
                moved_consist=moved_behavior,
                other_consist=other_behavior,
                incident_required=False,
            )

        if impact_result.outcome is ImpactOutcome.HARD_COLLISION:
            base_push_ft = self._hard_collision_push_distance_ft(
                impact_result.severity_score
            )
            base_ripple = self._hard_collision_ripple_depth(
                impact_result.severity_score
            )
            incident_required = impact_result.severity_score >= 6_000_000.0

            moved_behavior = ConsistImpactBehavior(
                consist_id=impact_result.moved_consist_id,
                bounce_distance_ft=0.0,
                push_through_distance_ft=round(base_push_ft * moved_share, 3),
                ripple_depth=self._cap_ripple_depth(
                    self._allocate_ripple_depth(base_ripple, moved_share),
                    moved_car_count,
                ),
            )
            other_behavior = ConsistImpactBehavior(
                consist_id=impact_result.other_consist_id
                if impact_result.other_consist_id is not None
                else impact_result.moved_consist_id,
                bounce_distance_ft=0.0,
                push_through_distance_ft=round(base_push_ft * other_share, 3),
                ripple_depth=self._cap_ripple_depth(
                    self._allocate_ripple_depth(base_ripple, other_share),
                    other_car_count,
                ),
            )

            return ImpactBehaviorResult(
                moved_consist=moved_behavior,
                other_consist=other_behavior,
                incident_required=incident_required,
            )

        raise ValueError(f"Unsupported ImpactOutcome: {impact_result.outcome}")

    def _soft_bounce_distance_ft(self, severity_score: float) -> float:
        if severity_score < 1_500_000.0:
            return 0.5
        if severity_score < 2_500_000.0:
            return 1.5
        return 3.0

    def _hard_collision_push_distance_ft(self, severity_score: float) -> float:
        if severity_score < 4_000_000.0:
            return 1.0
        if severity_score < 6_000_000.0:
            return 3.0
        return 4.0

    def _hard_collision_ripple_depth(self, severity_score: float) -> int:
        if severity_score < 4_000_000.0:
            return 1
        if severity_score < 6_000_000.0:
            return 2
        return 3

    def _allocate_ripple_depth(self, base_depth: int, share: float) -> int:
        if base_depth <= 0:
            return 0

        if share < 0.34:
            return max(1, base_depth - 1)
        if share < 0.67:
            return base_depth
        return base_depth + 1

    def _cap_ripple_depth(self, ripple_depth: int, car_count: int | None) -> int:
        if ripple_depth <= 0:
            return 0

        if car_count is None:
            return ripple_depth

        if car_count <= 0:
            return 0

        return min(ripple_depth, car_count)
