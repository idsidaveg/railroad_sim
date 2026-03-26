from __future__ import annotations


def compute_impact_severity(
    *,
    closing_speed_mph: float,
    moved_mass_lb: float,
    other_mass_lb: float,
) -> float:
    """
    Compute a simple impact severity score.

    v1 model:
        severity = closing_speed_mph * (moved_mass_lb + other_mass_lb)

    This is not physically accurate, but provides a monotonic and
    scalable measure for simulation purposes.
    """

    if closing_speed_mph < 0:
        raise ValueError("closing_speed_mph must be >= 0")

    if moved_mass_lb < 0:
        raise ValueError("moved_mass_lb must be >= 0")

    if other_mass_lb < 0:
        raise ValueError("other_mass_lb must be >= 0")

    combined_mass = moved_mass_lb + other_mass_lb

    return closing_speed_mph * combined_mass
