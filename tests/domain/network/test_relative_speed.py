from __future__ import annotations

import pytest

from railroad_sim.domain.enums import TravelDirection
from railroad_sim.domain.network.relative_speed import compute_closing_speed_mph


def test_same_direction_returns_speed_difference() -> None:
    result = compute_closing_speed_mph(
        moved_speed_mph=3.0,
        moved_direction=TravelDirection.TOWARD_B,
        other_speed_mph=1.0,
        other_direction=TravelDirection.TOWARD_B,
    )

    assert result == pytest.approx(2.0)


def test_opposite_directions_returns_speed_sum() -> None:
    result = compute_closing_speed_mph(
        moved_speed_mph=2.0,
        moved_direction=TravelDirection.TOWARD_B,
        other_speed_mph=1.0,
        other_direction=TravelDirection.TOWARD_A,
    )

    assert result == pytest.approx(3.0)


def test_stationary_other_returns_moved_speed() -> None:
    result = compute_closing_speed_mph(
        moved_speed_mph=2.5,
        moved_direction=TravelDirection.TOWARD_B,
        other_speed_mph=0.0,
        other_direction=TravelDirection.STATIONARY,
    )

    assert result == pytest.approx(2.5)


def test_stationary_moved_returns_other_speed() -> None:
    result = compute_closing_speed_mph(
        moved_speed_mph=0.0,
        moved_direction=TravelDirection.STATIONARY,
        other_speed_mph=1.5,
        other_direction=TravelDirection.TOWARD_A,
    )

    assert result == pytest.approx(1.5)


def test_both_stationary_returns_zero() -> None:
    result = compute_closing_speed_mph(
        moved_speed_mph=0.0,
        moved_direction=TravelDirection.STATIONARY,
        other_speed_mph=0.0,
        other_direction=TravelDirection.STATIONARY,
    )

    assert result == pytest.approx(0.0)


def test_negative_moved_speed_raises() -> None:
    with pytest.raises(ValueError, match="moved_speed_mph must be >= 0"):
        compute_closing_speed_mph(
            moved_speed_mph=-1.0,
            moved_direction=TravelDirection.TOWARD_B,
            other_speed_mph=1.0,
            other_direction=TravelDirection.TOWARD_A,
        )


def test_negative_other_speed_raises() -> None:
    with pytest.raises(ValueError, match="other_speed_mph must be >= 0"):
        compute_closing_speed_mph(
            moved_speed_mph=1.0,
            moved_direction=TravelDirection.TOWARD_B,
            other_speed_mph=-1.0,
            other_direction=TravelDirection.TOWARD_A,
        )
