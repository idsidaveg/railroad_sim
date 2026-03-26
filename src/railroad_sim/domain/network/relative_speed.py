from __future__ import annotations

from railroad_sim.domain.enums import TravelDirection


def compute_closing_speed_mph(
    *,
    moved_speed_mph: float,
    moved_direction: TravelDirection,
    other_speed_mph: float,
    other_direction: TravelDirection,
) -> float:
    """
    Compute non-negative closing speed between two consists.

    Rules:
    - same direction -> absolute speed difference
    - opposite directions -> speed sum
    - if either consist is stationary, this naturally reduces to the
      moving consist's speed or the difference/sum as appropriate
    """

    if moved_speed_mph < 0:
        raise ValueError("moved_speed_mph must be >= 0")

    if other_speed_mph < 0:
        raise ValueError("other_speed_mph must be >= 0")

    if moved_direction is TravelDirection.STATIONARY:
        return other_speed_mph

    if other_direction is TravelDirection.STATIONARY:
        return moved_speed_mph

    if moved_direction is other_direction:
        return abs(moved_speed_mph - other_speed_mph)

    return moved_speed_mph + other_speed_mph
