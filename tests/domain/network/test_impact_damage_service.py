from railroad_sim.domain.consist import Consist
from railroad_sim.domain.enums import DamageRating, RollingStockCondition
from railroad_sim.domain.equipment.boxcar import BoxCar
from railroad_sim.domain.network.impact_behavior_types import (
    ConsistImpactBehavior,
    ImpactBehaviorResult,
)
from railroad_sim.domain.network.impact_damage_service import ImpactDamageService
from railroad_sim.domain.network.impact_types import ImpactOutcome, ImpactResult


def build_consist(car_count: int) -> Consist:
    cars = []

    for i in range(car_count):
        car = BoxCar(reporting_mark="TST", road_number=f"{i + 1:04d}")
        cars.append(car)

    for left, right in zip(cars, cars[1:]):
        left.rear_coupler.connect(right.front_coupler)

    return Consist(anchor=cars[0])


def test_apply_damage_hard_collision_marks_correct_impact_end_cars_and_couplers() -> (
    None
):
    Consist._reset_registry_for_tests()

    moved = build_consist(2)
    other = build_consist(2)

    service = ImpactDamageService()

    impact_result = ImpactResult(
        outcome=ImpactOutcome.HARD_COLLISION,
        moved_consist_id=moved.consist_id,
        other_consist_id=other.consist_id,
        severity_score=3_504_000.0,
    )

    behavior_result = ImpactBehaviorResult(
        moved_consist=ConsistImpactBehavior(
            consist_id=moved.consist_id,
            bounce_distance_ft=0.0,
            push_through_distance_ft=0.5,
            ripple_depth=1,
        ),
        other_consist=ConsistImpactBehavior(
            consist_id=other.consist_id,
            bounce_distance_ft=0.0,
            push_through_distance_ft=0.5,
            ripple_depth=1,
        ),
        incident_required=False,
    )

    service.apply_damage(
        impact_result=impact_result,
        behavior_result=behavior_result,
        moved_consist=moved,
        other_consist=other,
        moved_contact_from_front=True,
        other_contact_from_front=False,
    )

    moved_order = moved.ordered_equipment()
    other_order = other.ordered_equipment()

    moved_impact_car = moved_order[0]
    moved_non_impact_car = moved_order[1]

    other_non_impact_car = other_order[0]
    other_impact_car = other_order[1]

    assert moved_impact_car.condition is RollingStockCondition.DAMAGED
    assert moved_impact_car.damage_rating is DamageRating.MODERATE
    assert moved_impact_car.front_coupler.is_damaged is True
    assert moved_impact_car.front_coupler.damage_rating is DamageRating.MODERATE
    assert moved_impact_car.rear_coupler.is_damaged is True
    assert moved_impact_car.rear_coupler.damage_rating is DamageRating.MODERATE

    assert moved_non_impact_car.condition is RollingStockCondition.IN_SERVICE
    assert moved_non_impact_car.damage_rating is None
    assert moved_non_impact_car.front_coupler.is_damaged is False
    assert moved_non_impact_car.rear_coupler.is_damaged is False

    assert other_impact_car.condition is RollingStockCondition.DAMAGED
    assert other_impact_car.damage_rating is DamageRating.MODERATE
    assert other_impact_car.front_coupler.is_damaged is True
    assert other_impact_car.front_coupler.damage_rating is DamageRating.MODERATE
    assert other_impact_car.rear_coupler.is_damaged is True
    assert other_impact_car.rear_coupler.damage_rating is DamageRating.MODERATE

    assert other_non_impact_car.condition is RollingStockCondition.IN_SERVICE
    assert other_non_impact_car.damage_rating is None
    assert other_non_impact_car.front_coupler.is_damaged is False
    assert other_non_impact_car.rear_coupler.is_damaged is False

    Consist._reset_registry_for_tests()


def test_apply_damage_incident_level_upgrades_lead_impacted_car_to_severe() -> None:
    Consist._reset_registry_for_tests()

    moved = build_consist(2)
    other = build_consist(2)

    service = ImpactDamageService()

    impact_result = ImpactResult(
        outcome=ImpactOutcome.HARD_COLLISION,
        moved_consist_id=moved.consist_id,
        other_consist_id=other.consist_id,
        severity_score=6_132_000.0,
    )

    behavior_result = ImpactBehaviorResult(
        moved_consist=ConsistImpactBehavior(
            consist_id=moved.consist_id,
            bounce_distance_ft=0.0,
            push_through_distance_ft=2.0,
            ripple_depth=2,
        ),
        other_consist=ConsistImpactBehavior(
            consist_id=other.consist_id,
            bounce_distance_ft=0.0,
            push_through_distance_ft=2.0,
            ripple_depth=2,
        ),
        incident_required=True,
    )

    service.apply_damage(
        impact_result=impact_result,
        behavior_result=behavior_result,
        moved_consist=moved,
        other_consist=other,
        moved_contact_from_front=True,
        other_contact_from_front=False,
    )

    moved_order = moved.ordered_equipment()
    other_order = other.ordered_equipment()

    moved_impact_car = moved_order[0]
    moved_ripple_car = moved_order[1]

    other_ripple_car = other_order[0]
    other_impact_car = other_order[1]

    assert moved_impact_car.condition is RollingStockCondition.DAMAGED
    assert moved_impact_car.damage_rating is DamageRating.SEVERE
    assert moved_impact_car.front_coupler.is_damaged is True
    assert moved_impact_car.front_coupler.damage_rating is DamageRating.SEVERE
    assert moved_impact_car.rear_coupler.is_damaged is True
    assert moved_impact_car.rear_coupler.damage_rating is DamageRating.SEVERE

    assert moved_ripple_car.condition is RollingStockCondition.DAMAGED
    assert moved_ripple_car.damage_rating is DamageRating.MODERATE
    assert moved_ripple_car.front_coupler.is_damaged is True
    assert moved_ripple_car.front_coupler.damage_rating is DamageRating.MODERATE
    assert moved_ripple_car.rear_coupler.is_damaged is True
    assert moved_ripple_car.rear_coupler.damage_rating is DamageRating.MODERATE

    assert other_impact_car.condition is RollingStockCondition.DAMAGED
    assert other_impact_car.damage_rating is DamageRating.SEVERE
    assert other_impact_car.front_coupler.is_damaged is True
    assert other_impact_car.front_coupler.damage_rating is DamageRating.SEVERE
    assert other_impact_car.rear_coupler.is_damaged is True
    assert other_impact_car.rear_coupler.damage_rating is DamageRating.SEVERE

    assert other_ripple_car.condition is RollingStockCondition.DAMAGED
    assert other_ripple_car.damage_rating is DamageRating.MODERATE
    assert other_ripple_car.front_coupler.is_damaged is True
    assert other_ripple_car.front_coupler.damage_rating is DamageRating.MODERATE
    assert other_ripple_car.rear_coupler.is_damaged is True
    assert other_ripple_car.rear_coupler.damage_rating is DamageRating.MODERATE

    Consist._reset_registry_for_tests()
