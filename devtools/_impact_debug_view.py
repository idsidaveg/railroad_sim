from __future__ import annotations


def render_impact_debug_block(
    *,
    movement_result,
    closing_speed_mph,
    impact_result,
    behavior_result,
    moved_mass_lb: float | None = None,
    other_mass_lb: float | None = None,
    moved_car_count: int | None = None,
    other_car_count: int | None = None,
) -> str:
    lines = []

    lines.append("")
    lines.append("=== IMPACT / CONTACT DEBUG ===")

    lines.append(f"contact_occurred : {movement_result.contact_occurred}")
    lines.append(f"stop_reason      : {movement_result.stop_reason}")
    lines.append(f"closing_speed    : {closing_speed_mph:.2f} mph")
    lines.append(f"impact_outcome   : {impact_result.outcome}")
    lines.append(f"severity_score   : {impact_result.severity_score:.2f}")
    if moved_mass_lb is not None and other_mass_lb is not None:
        lines.append(f"mass             : {moved_mass_lb:.1f} / {other_mass_lb:.1f}")
    lines.append(f"incident_required: {behavior_result.incident_required}")
    if moved_car_count is not None and other_car_count is not None:
        lines.append(f"cars             : {moved_car_count} / {other_car_count}")
    lines.append("")

    # Table
    lines.append("Consist | Bounce(ft) | Push(ft) | Ripple")
    lines.append("--------+------------+----------+-------")

    moved = behavior_result.moved_consist
    other = behavior_result.other_consist

    lines.append(
        "moved   | "
        f"{moved.bounce_distance_ft:10.3f} | "
        f"{moved.push_through_distance_ft:8.3f} | "
        f"{moved.ripple_depth}"
    )

    lines.append(
        "other   | "
        f"{other.bounce_distance_ft:10.3f} | "
        f"{other.push_through_distance_ft:8.3f} | "
        f"{other.ripple_depth}"
    )

    return "\n".join(lines)
