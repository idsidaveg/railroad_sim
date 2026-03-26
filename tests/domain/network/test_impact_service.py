from __future__ import annotations

from uuid import uuid4

from railroad_sim.domain.network.coupling_types import CouplingOutcome, CouplingResult
from railroad_sim.domain.network.impact_service import ImpactService
from railroad_sim.domain.network.impact_types import ImpactOutcome


def test_evaluate_from_coupling_result_returns_no_impact_for_coupled() -> None:
    service = ImpactService()

    moved_consist_id = uuid4()
    other_consist_id = uuid4()

    coupling_result = CouplingResult(
        outcome=CouplingOutcome.COUPLED,
        moved_consist_id=moved_consist_id,
        other_consist_id=other_consist_id,
        merged_consist=None,
    )

    result = service.evaluate_from_coupling_result(
        coupling_result=coupling_result,
        closing_speed_mph=3.0,
        moved_mass_lb=120000.0,
        other_mass_lb=180000.0,
    )

    assert result.outcome is ImpactOutcome.NO_IMPACT
    assert result.moved_consist_id == moved_consist_id
    assert result.other_consist_id == other_consist_id
    assert result.severity_score == 900000.0


def test_evaluate_from_coupling_result_returns_soft_bounce_for_too_fast_to_couple() -> (
    None
):
    service = ImpactService()

    moved_consist_id = uuid4()
    other_consist_id = uuid4()

    coupling_result = CouplingResult(
        outcome=CouplingOutcome.TOO_FAST_TO_COUPLE,
        moved_consist_id=moved_consist_id,
        other_consist_id=other_consist_id,
        merged_consist=None,
    )

    result = service.evaluate_from_coupling_result(
        coupling_result=coupling_result,
        closing_speed_mph=6.0,
        moved_mass_lb=120000.0,
        other_mass_lb=180000.0,
    )

    assert result.outcome is ImpactOutcome.SOFT_BOUNCE
    assert result.moved_consist_id == moved_consist_id
    assert result.other_consist_id == other_consist_id
    assert result.severity_score == 1800000.0


def test_evaluate_from_coupling_result_returns_hard_collision_at_or_above_threshold() -> (
    None
):
    service = ImpactService()

    moved_consist_id = uuid4()
    other_consist_id = uuid4()

    coupling_result = CouplingResult(
        outcome=CouplingOutcome.TOO_FAST_TO_COUPLE,
        moved_consist_id=moved_consist_id,
        other_consist_id=other_consist_id,
        merged_consist=None,
    )

    result = service.evaluate_from_coupling_result(
        coupling_result=coupling_result,
        closing_speed_mph=12.0,
        moved_mass_lb=120000.0,
        other_mass_lb=180000.0,
    )

    assert result.outcome is ImpactOutcome.HARD_COLLISION
    assert result.moved_consist_id == moved_consist_id
    assert result.other_consist_id == other_consist_id
    assert result.severity_score == 3600000.0


def test_evaluate_from_coupling_result_returns_no_impact_for_non_contact_outcome() -> (
    None
):
    service = ImpactService()

    moved_consist_id = uuid4()

    coupling_result = CouplingResult(
        outcome=CouplingOutcome.NO_CONTACT,
        moved_consist_id=moved_consist_id,
        other_consist_id=None,
        merged_consist=None,
    )

    result = service.evaluate_from_coupling_result(
        coupling_result=coupling_result,
        closing_speed_mph=0.0,
        moved_mass_lb=120000.0,
        other_mass_lb=0.0,
    )

    assert result.outcome is ImpactOutcome.NO_IMPACT
    assert result.moved_consist_id == moved_consist_id
    assert result.other_consist_id is None
    assert result.severity_score == 0.0
