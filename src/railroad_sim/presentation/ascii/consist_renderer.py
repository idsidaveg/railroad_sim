from __future__ import annotations

from railroad_sim.domain.consist import Consist
from railroad_sim.domain.rolling_stock import RollingStock


def _format_equipment(eq: RollingStock) -> str:
    """
    Convert rolling stock into a compact one-line label.

    Expected format:
        SHORT_NAME:EQUIPMENT_ID

    Example:
        LOCO:BNSF 4721
        RFR:UP 500001
    """
    short_name = getattr(eq, "equipment_short_name", eq.equipment_class)
    equipment_id = eq.equipment_id
    return f"{short_name}:{equipment_id}"


def render_consist(consist: Consist) -> str:
    """
    Render a consist using the default compact style.
    """
    return render_consist_compact(consist)


def render_consist_compact(consist: Consist) -> str:
    """
    Render a consist as a compact single-line ASCII diagram.

    Example:

    HEAD
    [LOCO:BNSF 4721]──[RFR:UP 500001]──[TANK:UTLX 100001]
    TAIL
    """
    equipment = consist.ordered_equipment()

    if not equipment:
        return "HEAD\n[EMPTY CONSIST]\nTAIL"

    cars = [f"[{_format_equipment(eq)}]" for eq in equipment]
    line = "──".join(cars)

    return "\n".join(
        [
            "HEAD",
            line,
            "TAIL",
        ]
    )


def render_consist_boxed(consist: Consist) -> str:
    """
    Render a consist as a multi-line boxed ASCII diagram.

    Example:

    HEAD

    ┌─────────────────┐ ┌─────────────────┐
    │ LOCO            │─│ RFR             │
    │ BNSF 4721       │ │ UP 500001       │
    └─────────────────┘ └─────────────────┘

    TAIL
    """
    equipment = consist.ordered_equipment()

    if not equipment:
        return "HEAD\n\n[EMPTY CONSIST]\n\nTAIL"

    max_short_name_len = max(
        len(getattr(eq, "equipment_short_name", eq.equipment_class)) for eq in equipment
    )
    max_equipment_id_len = max(len(eq.equipment_id) for eq in equipment)

    # One leading space inside the box before content.
    inner_width = max(max_short_name_len, max_equipment_id_len) + 1

    top_parts: list[str] = []
    mid1_parts: list[str] = []
    mid2_parts: list[str] = []
    bot_parts: list[str] = []

    for index, eq in enumerate(equipment):
        short_name = getattr(eq, "equipment_short_name", eq.equipment_class)
        equipment_id = eq.equipment_id

        top = f"┌{'─' * inner_width}┐"
        mid1 = f"│ {short_name:<{inner_width - 1}}│"
        mid2 = f"│ {equipment_id:<{inner_width - 1}}│"
        bot = f"└{'─' * inner_width}┘"

        top_parts.append(top)
        mid1_parts.append(mid1)
        mid2_parts.append(mid2)
        bot_parts.append(bot)

        if index < len(equipment) - 1:
            top_parts.append(" ")
            mid1_parts.append("─")
            mid2_parts.append(" ")
            bot_parts.append(" ")

    return "\n".join(
        [
            "HEAD",
            "",
            "".join(top_parts),
            "".join(mid1_parts),
            "".join(mid2_parts),
            "".join(bot_parts),
            "",
            "TAIL",
        ]
    )
