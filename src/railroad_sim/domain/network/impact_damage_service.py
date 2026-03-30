from __future__ import annotations

from datetime import datetime

from railroad_sim.domain.consist import Consist
from railroad_sim.domain.couplers import Coupler
from railroad_sim.domain.enums import DamageRating
from railroad_sim.domain.network.impact_behavior_types import ImpactBehaviorResult
from railroad_sim.domain.network.impact_types import ImpactOutcome, ImpactResult
from railroad_sim.domain.rolling_stock import RollingStock


class ImpactDamageService:
    """
    Apply collision damage to rolling stock and couplers after impact behavior
    has already been computed.

    This service does not classify impacts and does not compute behavior.
    It only maps an existing ImpactResult + ImpactBehaviorResult onto the
    actual equipment involved.
    """

    def apply_damage(
        self,
        *,
        impact_result: ImpactResult,
        behavior_result: ImpactBehaviorResult,
        moved_consist: Consist,
        other_consist: Consist,
        moved_contact_from_front: bool,
        other_contact_from_front: bool,
        occurred_at: datetime | None = None,
        location: str | None = None,
        related_train_id: str | None = None,
    ) -> None:
        if impact_result.outcome is not ImpactOutcome.HARD_COLLISION:
            return

        self._apply_consist_damage(
            consist=moved_consist,
            ripple_depth=behavior_result.moved_consist.ripple_depth,
            contact_from_front=moved_contact_from_front,
            incident_required=behavior_result.incident_required,
            occurred_at=occurred_at,
            location=location,
            related_train_id=related_train_id,
        )

        self._apply_consist_damage(
            consist=other_consist,
            ripple_depth=behavior_result.other_consist.ripple_depth,
            contact_from_front=other_contact_from_front,
            incident_required=behavior_result.incident_required,
            occurred_at=occurred_at,
            location=location,
            related_train_id=related_train_id,
        )

    def _apply_consist_damage(
        self,
        *,
        consist: Consist,
        ripple_depth: int,
        contact_from_front: bool,
        incident_required: bool,
        occurred_at: datetime | None,
        location: str | None,
        related_train_id: str | None,
    ) -> None:
        if ripple_depth <= 0:
            return

        ordered = consist.ordered_equipment()
        impacted_cars = (
            ordered[:ripple_depth] if contact_from_front else ordered[-ripple_depth:]
        )
        if not contact_from_front:
            impacted_cars = list(reversed(impacted_cars))

        for idx, car in enumerate(impacted_cars):
            if idx == 0:
                damage_rating = (
                    DamageRating.SEVERE if incident_required else DamageRating.MODERATE
                )
            else:
                damage_rating = DamageRating.MODERATE

            car.mark_collision_damage(
                damage_rating=damage_rating,
                occurred_at=occurred_at,
                details=(
                    f"Impact damage applied from collision propagation; "
                    f"position={idx + 1} of {len(impacted_cars)}."
                ),
                location=location,
                related_train_id=related_train_id,
            )

            self._mark_both_couplers_damaged(car, damage_rating=damage_rating)

    def _mark_both_couplers_damaged(
        self,
        car: RollingStock,
        *,
        damage_rating: DamageRating,
    ) -> None:
        self._mark_coupler_damaged(car.front_coupler, damage_rating=damage_rating)
        self._mark_coupler_damaged(car.rear_coupler, damage_rating=damage_rating)

    def _mark_coupler_damaged(
        self,
        coupler: Coupler,
        *,
        damage_rating: DamageRating,
    ) -> None:
        coupler.mark_damaged(damage_rating=damage_rating)
