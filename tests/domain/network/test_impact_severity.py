from __future__ import annotations

import pytest

from railroad_sim.domain.network.impact_severity import compute_impact_severity


def test_compute_impact_severity_returns_speed_times_combined_mass() -> None:
    result = compute_impact_severity(
        closing_speed_mph=6.0,
        moved_mass_lb=120000.0,
        other_mass_lb=180000.0,
    )

    assert result == pytest.approx(1800000.0)


def test_compute_impact_severity_returns_zero_when_speed_is_zero() -> None:
    result = compute_impact_severity(
        closing_speed_mph=0.0,
        moved_mass_lb=120000.0,
        other_mass_lb=180000.0,
    )

    assert result == pytest.approx(0.0)


def test_compute_impact_severity_returns_zero_when_both_masses_are_zero() -> None:
    result = compute_impact_severity(
        closing_speed_mph=5.0,
        moved_mass_lb=0.0,
        other_mass_lb=0.0,
    )

    assert result == pytest.approx(0.0)


def test_compute_impact_severity_scales_with_higher_speed() -> None:
    lower = compute_impact_severity(
        closing_speed_mph=4.0,
        moved_mass_lb=100000.0,
        other_mass_lb=100000.0,
    )
    higher = compute_impact_severity(
        closing_speed_mph=8.0,
        moved_mass_lb=100000.0,
        other_mass_lb=100000.0,
    )

    assert higher == pytest.approx(lower * 2.0)


def test_compute_impact_severity_scales_with_higher_mass() -> None:
    lower = compute_impact_severity(
        closing_speed_mph=5.0,
        moved_mass_lb=100000.0,
        other_mass_lb=100000.0,
    )
    higher = compute_impact_severity(
        closing_speed_mph=5.0,
        moved_mass_lb=150000.0,
        other_mass_lb=150000.0,
    )

    assert higher == pytest.approx(lower * 1.5)


def test_compute_impact_severity_raises_for_negative_speed() -> None:
    with pytest.raises(ValueError, match="closing_speed_mph must be >= 0"):
        compute_impact_severity(
            closing_speed_mph=-1.0,
            moved_mass_lb=100000.0,
            other_mass_lb=100000.0,
        )


def test_compute_impact_severity_raises_for_negative_moved_mass() -> None:
    with pytest.raises(ValueError, match="moved_mass_lb must be >= 0"):
        compute_impact_severity(
            closing_speed_mph=5.0,
            moved_mass_lb=-100000.0,
            other_mass_lb=100000.0,
        )


def test_compute_impact_severity_raises_for_negative_other_mass() -> None:
    with pytest.raises(ValueError, match="other_mass_lb must be >= 0"):
        compute_impact_severity(
            closing_speed_mph=5.0,
            moved_mass_lb=100000.0,
            other_mass_lb=-100000.0,
        )
