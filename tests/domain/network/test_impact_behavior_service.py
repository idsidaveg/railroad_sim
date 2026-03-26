from __future__ import annotations

from uuid import uuid4

from railroad_sim.domain.network.impact_behavior_service import ImpactBehaviorService
from railroad_sim.domain.network.impact_types import ImpactOutcome, ImpactResult


def test_evaluate_behavior_returns_no_effects_for_no_impact() -> None:
    service = ImpactBehaviorService()

    moved_id = uuid4()
    other_id = uuid4()

    impact_result = ImpactResult(
        outcome=ImpactOutcome.NO_IMPACT,
        moved_consist_id=moved_id,
        other_consist_id=other_id,
        severity_score=0.0,
    )

    result = service.evaluate_behavior(
        impact_result=impact_result,
        moved_mass_lb=120000.0,
        other_mass_lb=180000.0,
    )

    assert result.moved_consist.consist_id == moved_id
    assert result.other_consist.consist_id == other_id

    assert result.moved_consist.bounce_distance_ft == 0.0
    assert result.moved_consist.push_through_distance_ft == 0.0
    assert result.moved_consist.ripple_depth == 0

    assert result.other_consist.bounce_distance_ft == 0.0
    assert result.other_consist.push_through_distance_ft == 0.0
    assert result.other_consist.ripple_depth == 0

    assert result.incident_required is False


def test_soft_bounce_allocates_more_bounce_to_lighter_moved_consist() -> None:
    service = ImpactBehaviorService()

    moved_id = uuid4()
    other_id = uuid4()

    impact_result = ImpactResult(
        outcome=ImpactOutcome.SOFT_BOUNCE,
        moved_consist_id=moved_id,
        other_consist_id=other_id,
        severity_score=1800000.0,
    )

    result = service.evaluate_behavior(
        impact_result=impact_result,
        moved_mass_lb=100000.0,
        other_mass_lb=300000.0,
    )

    assert result.moved_consist.consist_id == moved_id
    assert result.other_consist.consist_id == other_id

    assert (
        result.moved_consist.bounce_distance_ft
        > result.other_consist.bounce_distance_ft
    )
    assert result.moved_consist.push_through_distance_ft == 0.0
    assert result.other_consist.push_through_distance_ft == 0.0
    assert result.moved_consist.ripple_depth == 0
    assert result.other_consist.ripple_depth == 0
    assert result.incident_required is False


def test_hard_collision_allocates_more_push_and_ripple_to_lighter_other_consist() -> (
    None
):
    service = ImpactBehaviorService()

    moved_id = uuid4()
    other_id = uuid4()

    impact_result = ImpactResult(
        outcome=ImpactOutcome.HARD_COLLISION,
        moved_consist_id=moved_id,
        other_consist_id=other_id,
        severity_score=4500000.0,
    )

    result = service.evaluate_behavior(
        impact_result=impact_result,
        moved_mass_lb=300000.0,
        other_mass_lb=100000.0,
    )

    assert result.moved_consist.consist_id == moved_id
    assert result.other_consist.consist_id == other_id

    assert (
        result.other_consist.push_through_distance_ft
        > result.moved_consist.push_through_distance_ft
    )
    assert result.other_consist.ripple_depth > result.moved_consist.ripple_depth
    assert result.moved_consist.bounce_distance_ft == 0.0
    assert result.other_consist.bounce_distance_ft == 0.0
    assert result.incident_required is False


def test_hard_collision_highest_band_requires_incident() -> None:
    service = ImpactBehaviorService()

    moved_id = uuid4()
    other_id = uuid4()

    impact_result = ImpactResult(
        outcome=ImpactOutcome.HARD_COLLISION,
        moved_consist_id=moved_id,
        other_consist_id=other_id,
        severity_score=6500000.0,
    )

    result = service.evaluate_behavior(
        impact_result=impact_result,
        moved_mass_lb=200000.0,
        other_mass_lb=200000.0,
    )

    assert result.incident_required is True
    assert result.moved_consist.push_through_distance_ft > 0.0
    assert result.other_consist.push_through_distance_ft > 0.0
    assert result.moved_consist.ripple_depth >= 1
    assert result.other_consist.ripple_depth >= 1


def test_zero_total_mass_splits_effects_evenly() -> None:
    service = ImpactBehaviorService()

    moved_id = uuid4()
    other_id = uuid4()

    impact_result = ImpactResult(
        outcome=ImpactOutcome.SOFT_BOUNCE,
        moved_consist_id=moved_id,
        other_consist_id=other_id,
        severity_score=1800000.0,
    )

    result = service.evaluate_behavior(
        impact_result=impact_result,
        moved_mass_lb=0.0,
        other_mass_lb=0.0,
    )

    assert (
        result.moved_consist.bounce_distance_ft
        == result.other_consist.bounce_distance_ft
    )
    assert result.moved_consist.ripple_depth == 0
    assert result.other_consist.ripple_depth == 0


def test_negative_moved_mass_raises() -> None:
    service = ImpactBehaviorService()

    impact_result = ImpactResult(
        outcome=ImpactOutcome.SOFT_BOUNCE,
        moved_consist_id=uuid4(),
        other_consist_id=uuid4(),
        severity_score=1800000.0,
    )

    try:
        service.evaluate_behavior(
            impact_result=impact_result,
            moved_mass_lb=-1.0,
            other_mass_lb=100000.0,
        )
    except ValueError as exc:
        assert str(exc) == "moved_mass_lb must be >= 0"
    else:
        raise AssertionError("Expected ValueError for negative moved_mass_lb")


def test_negative_other_mass_raises() -> None:
    service = ImpactBehaviorService()

    impact_result = ImpactResult(
        outcome=ImpactOutcome.SOFT_BOUNCE,
        moved_consist_id=uuid4(),
        other_consist_id=uuid4(),
        severity_score=1800000.0,
    )

    try:
        service.evaluate_behavior(
            impact_result=impact_result,
            moved_mass_lb=100000.0,
            other_mass_lb=-1.0,
        )
    except ValueError as exc:
        assert str(exc) == "other_mass_lb must be >= 0"
    else:
        raise AssertionError("Expected ValueError for negative other_mass_lb")
