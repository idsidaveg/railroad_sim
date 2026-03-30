from __future__ import annotations

from dataclasses import dataclass

from railroad_sim.domain.consist import Consist
from railroad_sim.domain.enums import TravelDirection
from railroad_sim.domain.network.consist_movement_types import MovementExecutionResult
from railroad_sim.domain.network.coupling_service import CouplingService
from railroad_sim.domain.network.coupling_types import CouplingResult
from railroad_sim.domain.network.impact_behavior_service import ImpactBehaviorService
from railroad_sim.domain.network.impact_behavior_types import ImpactBehaviorResult
from railroad_sim.domain.network.impact_damage_service import ImpactDamageService
from railroad_sim.domain.network.impact_service import ImpactService
from railroad_sim.domain.network.impact_types import ImpactResult
from railroad_sim.domain.network.relative_speed import compute_closing_speed_mph


@dataclass(frozen=True, slots=True)
class PostContactResolutionResult:
    coupling_result: CouplingResult
    impact_result: ImpactResult
    behavior_result: ImpactBehaviorResult


class PostContactResolutionService:
    """
    Orchestrates post-contact handling after movement has already occurred.

    Responsibilities:
    - coupling attempt
    - impact classification
    - behavior evaluation
    - damage application

    Non-responsibilities:
    - movement execution
    - footprint calculation
    - contact probing
    """

    def __init__(
        self,
        *,
        coupling_service: CouplingService | None = None,
        impact_service: ImpactService | None = None,
        impact_behavior_service: ImpactBehaviorService | None = None,
        impact_damage_service: ImpactDamageService | None = None,
    ) -> None:
        self._coupling = coupling_service or CouplingService()
        self._impact = impact_service or ImpactService()
        self._behavior = impact_behavior_service or ImpactBehaviorService()
        self._damage = impact_damage_service or ImpactDamageService()

    def resolve(
        self,
        *,
        movement_result: MovementExecutionResult,
        other_consists: tuple[Consist, ...],
        moved_speed_mph: float,
        other_speed_mph: float,
        other_direction: TravelDirection,
        moved_mass_lb: float,
        other_mass_lb: float,
        moved_car_count: int | None = None,
        other_car_count: int | None = None,
        moved_contact_from_front: bool,
        other_contact_from_front: bool,
        max_coupling_speed_mph: float = 4.0,
        hard_collision_speed_mph: float = 12.0,
    ) -> PostContactResolutionResult:
        closing_speed_mph = compute_closing_speed_mph(
            moved_speed_mph=moved_speed_mph,
            moved_direction=movement_result.new_extent.travel_direction,
            other_speed_mph=other_speed_mph,
            other_direction=other_direction,
        )

        coupling_result = self._coupling.try_couple(
            movement_result=movement_result,
            other_consists=other_consists,
            closing_speed_mph=closing_speed_mph,
            max_coupling_speed_mph=max_coupling_speed_mph,
        )

        impact_result = self._impact.evaluate_from_coupling_result(
            coupling_result=coupling_result,
            closing_speed_mph=closing_speed_mph,
            moved_mass_lb=moved_mass_lb,
            other_mass_lb=other_mass_lb,
            hard_collision_speed_mph=hard_collision_speed_mph,
        )

        behavior_result = self._behavior.evaluate_behavior(
            impact_result=impact_result,
            moved_mass_lb=moved_mass_lb,
            other_mass_lb=other_mass_lb,
            moved_car_count=moved_car_count,
            other_car_count=other_car_count,
        )

        other_consist = next(
            (
                consist
                for consist in other_consists
                if consist.consist_id == movement_result.contact_with_consist_id
            ),
            None,
        )

        if other_consist is not None:
            self._damage.apply_damage(
                impact_result=impact_result,
                behavior_result=behavior_result,
                moved_consist=movement_result.new_extent.consist,
                other_consist=other_consist,
                moved_contact_from_front=moved_contact_from_front,
                other_contact_from_front=other_contact_from_front,
            )

        return PostContactResolutionResult(
            coupling_result=coupling_result,
            impact_result=impact_result,
            behavior_result=behavior_result,
        )
