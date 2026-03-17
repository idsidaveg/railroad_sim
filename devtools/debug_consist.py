import argparse
import os
import sys
from pathlib import Path
from typing import TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from debug_equipment import DebugEquipmentSet, build_debug_equipment

from railroad_sim.domain.consist import Consist
from railroad_sim.domain.switching_service import SwitchingService
from railroad_sim.presentation.ascii.consist_renderer import (
    render_consist,
    render_consist_boxed,
)


class DebugConsistSet(TypedDict):
    consist: Consist
    equipment: DebugEquipmentSet


SCENARIO_ALIASES: dict[str, str] = {
    "s": "summary",
    "sa": "split_after",
    "sb": "split_before",
    "ca": "cut_after",
    "cb": "cut_before",
    "ap": "append",
    "ins": "insert",
    "so": "setout",
    "pu": "pickup_rear",
    "pum": "pickup_middle",
}

VALID_SCENARIOS: tuple[str, ...] = (
    "summary",
    "split_after",
    "split_before",
    "cut_after",
    "cut_before",
    "append",
    "insert",
    "setout",
    "pickup_rear",
    "pickup_middle",
)

HELP_COMMANDS: set[str] = {"help", "list", "menu", "?"}
EXIT_COMMANDS: set[str] = {"exit", "quit", "q"}
CLEAR_COMMANDS: set[str] = {"clear", "cls", "c"}
RERUN_COMMANDS: set[str] = {"rerun", "repeat", "r"}


def build_debug_consist() -> DebugConsistSet:
    """
    Build a mixed consist from the debug equipment set.

    Order:
        LOCO -> BOXCAR -> TANKCAR -> INTERMODAL -> GONDOLA -> CABOOSE
    """
    Consist._reset_registry_for_tests()

    equipment = build_debug_equipment()

    loco = equipment["loco"]
    boxcar = equipment["boxcar"]
    tankcar = equipment["tankcar"]
    intermodal = equipment["intermodal"]
    gondola = equipment["gondola"]
    caboose = equipment["caboose"]

    loco.rear_coupler.connect(boxcar.front_coupler)
    boxcar.rear_coupler.connect(tankcar.front_coupler)
    tankcar.rear_coupler.connect(intermodal.front_coupler)
    intermodal.rear_coupler.connect(gondola.front_coupler)
    gondola.rear_coupler.connect(caboose.front_coupler)

    consist = Consist(anchor=loco)

    return {
        "consist": consist,
        "equipment": equipment,
    }


def clear_screen() -> None:
    """
    Clear the terminal screen.
    """
    os.system("cls" if os.name == "nt" else "clear")


def _neighbor_text(coupler) -> str:
    if coupler.connected_to is None:
        return "None"

    other = coupler.connected_to
    return f"{other.owner.equipment_id}:{other.position.name}"


def normalize_scenario_name(name: str) -> str:
    """
    Normalize a scenario name or alias to the canonical scenario name.
    """
    cleaned = name.strip().lower()
    return SCENARIO_ALIASES.get(cleaned, cleaned)


def print_available_commands() -> None:
    """
    Print the available scenarios and helper commands.
    """
    print("Available scenarios")
    print("=" * 80)
    print("  summary        (alias: s)")
    print("  split_after    (alias: sa)")
    print("  split_before   (alias: sb)")
    print("  cut_after      (alias: ca)")
    print("  cut_before     (alias: cb)")
    print("  append         (alias: ap)")
    print("  insert         (alias: ins)")
    print("  setout         (alias: so)")
    print("  pickup_rear    (alias: pu)")
    print("  pickup_middle  (alias: pum)")
    print()
    print("Other commands")
    print("=" * 80)
    print("  help, list, menu, ?   Show this command list")
    print("  rerun, repeat, r      Re-run the last successful scenario")
    print("  clear, cls, c         Clear the terminal screen")
    print("  exit, quit, q         Leave the interactive shell")
    print()


def print_consist_summary(consist: Consist, title: str = "Consist Summary") -> None:
    """
    Print a concise operational summary of the consist.
    """
    ordered = consist.ordered_equipment()

    print(title)
    print("=" * 80)
    print(f"consist_id       : {consist.consist_id}")
    print(f"anchor           : {consist.anchor.equipment_id}")
    print(f"equipment count  : {len(ordered)}")
    print()

    print("Ordered Equipment")
    print("=" * 80)

    for index, car in enumerate(ordered):
        print(f"[{index}] {car.equipment_id}")
        print(f"     class      : {car.equipment_class}")
        print(f"     short_name : {car.equipment_short_name}")
        print(f"     asset_id   : {car.asset_id}")
        print(f"     front      : {_neighbor_text(car.front_coupler)}")
        print(f"     rear       : {_neighbor_text(car.rear_coupler)}")
        print()

    print("Exposed Ends")
    print("=" * 80)
    print(f"head equipment   : {consist.head_end.equipment_id}")
    print(f"head coupler     : {_neighbor_text(consist.head_end.front_coupler)}")
    print(f"rear equipment   : {consist.rear_end.equipment_id}")
    print(f"rear coupler     : {_neighbor_text(consist.rear_end.rear_coupler)}")
    print()


def print_consist_manifest(consist: Consist, title: str = "Consist Manifest") -> None:
    """
    Print a one-line manifest view of the consist.
    """
    ordered = consist.ordered_equipment()

    print(title)
    print("=" * 80)
    for index, car in enumerate(ordered):
        print(
            f"{index:>2}  "
            f"{car.equipment_id:<12}  "
            f"{car.equipment_class:<12}  "
            f"{car.equipment_short_name}"
        )
    print()


def print_compact_render(consist: Consist, title: str) -> None:
    """
    Print the compact renderer for a consist.
    """
    print(title)
    print("=" * 80)
    print(render_consist(consist))
    print()


def print_boxed_render(consist: Consist, title: str) -> None:
    """
    Print the boxed renderer for a consist.
    """
    print(title)
    print("=" * 80)
    print(render_consist_boxed(consist))
    print()


def print_two_consists(
    left: Consist,
    right: Consist,
    *,
    left_title: str,
    right_title: str,
) -> None:
    print_boxed_render(left, left_title)
    print_boxed_render(right, right_title)


def print_three_consists(
    left: Consist,
    middle: Consist,
    right: Consist,
    *,
    left_title: str,
    middle_title: str,
    right_title: str,
) -> None:
    print_boxed_render(left, left_title)
    print_boxed_render(middle, middle_title)
    print_boxed_render(right, right_title)


def print_section(title: str) -> None:
    """
    Print a major section heading for a scenario.
    """
    print(title)
    print("=" * 80)


def debug_split_after() -> None:
    """
    Low-level consist split after the intermodal car.
    """
    debug_data = build_debug_consist()
    consist = debug_data["consist"]
    equipment = debug_data["equipment"]

    intermodal = equipment["intermodal"]

    print_boxed_render(consist, "Before consist.split_after(intermodal)")

    left, right = consist.split_after(intermodal)

    print_two_consists(
        left,
        right,
        left_title="Left consist after split_after(intermodal)",
        right_title="Right consist after split_after(intermodal)",
    )


def debug_split_before() -> None:
    """
    Low-level consist split before the tankcar.
    """
    debug_data = build_debug_consist()
    consist = debug_data["consist"]
    equipment = debug_data["equipment"]

    tankcar = equipment["tankcar"]

    print_boxed_render(consist, "Before consist.split_before(tankcar)")

    left, right = consist.split_before(tankcar)

    print_two_consists(
        left,
        right,
        left_title="Left consist after split_before(tankcar)",
        right_title="Right consist after split_before(tankcar)",
    )


def debug_cut_after() -> None:
    """
    Railroad-style cut after the tankcar.
    """
    debug_data = build_debug_consist()
    consist = debug_data["consist"]
    equipment = debug_data["equipment"]

    tankcar = equipment["tankcar"]

    print_boxed_render(consist, "Before SwitchingService.cut_after(tankcar)")

    left, right = SwitchingService.cut_after(consist, tankcar)

    print_two_consists(
        left,
        right,
        left_title="Left consist after cut_after(tankcar)",
        right_title="Right consist after cut_after(tankcar)",
    )


def debug_cut_before() -> None:
    """
    Railroad-style cut before the tankcar.
    """
    debug_data = build_debug_consist()
    consist = debug_data["consist"]
    equipment = debug_data["equipment"]

    tankcar = equipment["tankcar"]

    print_boxed_render(consist, "Before SwitchingService.cut_before(tankcar)")

    left, right = SwitchingService.cut_before(consist, tankcar)

    print_two_consists(
        left,
        right,
        left_title="Left consist after cut_before(tankcar)",
        right_title="Right consist after cut_before(tankcar)",
    )


def debug_append_consist() -> None:
    """
    Build two smaller consists and append the second onto the first.

    Consist A:
        LOCO -> BOXCAR -> TANKCAR

    Consist B:
        INTERMODAL -> GONDOLA -> CABOOSE
    """
    Consist._reset_registry_for_tests()

    equipment = build_debug_equipment()

    loco = equipment["loco"]
    boxcar = equipment["boxcar"]
    tankcar = equipment["tankcar"]
    intermodal = equipment["intermodal"]
    gondola = equipment["gondola"]
    caboose = equipment["caboose"]

    loco.rear_coupler.connect(boxcar.front_coupler)
    boxcar.rear_coupler.connect(tankcar.front_coupler)
    consist_a = Consist(anchor=loco)

    intermodal.rear_coupler.connect(gondola.front_coupler)
    gondola.rear_coupler.connect(caboose.front_coupler)
    consist_b = Consist(anchor=intermodal)

    print_boxed_render(consist_a, "Consist A before append_consist")
    print_boxed_render(consist_b, "Consist B before append_consist")

    combined = SwitchingService.append_consist(consist_a, consist_b)

    print_boxed_render(combined, "Combined consist after append_consist")
    print_consist_summary(combined, "Combined consist summary after append_consist")


def debug_insert_block() -> None:
    """
    Insert a block into an existing consist.

    Base consist:
        LOCO -> BOXCAR -> GONDOLA -> CABOOSE

    Inserted block:
        TANKCAR -> INTERMODAL

    Result:
        LOCO -> BOXCAR -> TANKCAR -> INTERMODAL -> GONDOLA -> CABOOSE
    """
    Consist._reset_registry_for_tests()

    equipment = build_debug_equipment()

    loco = equipment["loco"]
    boxcar = equipment["boxcar"]
    tankcar = equipment["tankcar"]
    intermodal = equipment["intermodal"]
    gondola = equipment["gondola"]
    caboose = equipment["caboose"]

    loco.rear_coupler.connect(boxcar.front_coupler)
    boxcar.rear_coupler.connect(gondola.front_coupler)
    gondola.rear_coupler.connect(caboose.front_coupler)
    base_consist = Consist(anchor=loco)

    tankcar.rear_coupler.connect(intermodal.front_coupler)
    block_consist = Consist(anchor=tankcar)

    print_boxed_render(base_consist, "Base consist before insert_block")
    print_boxed_render(block_consist, "Block consist before insert_block")

    combined = SwitchingService.insert_block(base_consist, boxcar, block_consist)

    print_boxed_render(combined, "Combined consist after insert_block")
    print_consist_summary(combined, "Combined consist summary after insert_block")


def debug_setout() -> None:
    """
    Set out the tank car from the middle of the train.

    Starting consist:
        LOCO -> BOXCAR -> TANKCAR -> INTERMODAL -> GONDOLA -> CABOOSE

    Intermediate state:
        Left block   -> LOCO -> BOXCAR
        Setout block -> TANKCAR
        Right block  -> INTERMODAL -> GONDOLA -> CABOOSE

    Final state:
        Road consist -> LOCO -> BOXCAR -> INTERMODAL -> GONDOLA -> CABOOSE
        Setout block -> TANKCAR
    """
    # Pass 1: show the intermediate split state.
    debug_data = build_debug_consist()
    consist = debug_data["consist"]
    equipment = debug_data["equipment"]

    tankcar = equipment["tankcar"]

    print_section("=== STARTING STATE ===")
    print_boxed_render(
        consist, "Starting consist before setout_block(tankcar, tankcar)"
    )

    left, remainder = consist.split_before(tankcar)
    setout_block, right = remainder.split_after(tankcar)

    print_section("=== INTERMEDIATE STATE ===")
    print_three_consists(
        left,
        setout_block,
        right,
        left_title="Intermediate left block after split_before(tankcar)",
        middle_title="Intermediate setout block after split_after(tankcar)",
        right_title="Intermediate right block after split_after(tankcar)",
    )

    # Pass 2: rebuild from scratch so the real operation runs on a fresh consist.
    debug_data = build_debug_consist()
    consist = debug_data["consist"]
    equipment = debug_data["equipment"]

    tankcar = equipment["tankcar"]

    road_consist, setout_consist = SwitchingService.setout_block(
        consist,
        tankcar,
        tankcar,
    )

    print_section("=== FINAL STATE ===")
    print_two_consists(
        road_consist,
        setout_consist,
        left_title="Final road consist after setout_block(tankcar, tankcar)",
        right_title="Final setout consist on spur",
    )


def debug_pickup_rear() -> None:
    """
    Pick up a single car and add it to the rear of the road train.

    Road consist:
        LOCO -> BOXCAR -> INTERMODAL -> GONDOLA -> CABOOSE

    Pickup block:
        TANKCAR

    Result:
        LOCO -> BOXCAR -> INTERMODAL -> GONDOLA -> CABOOSE -> TANKCAR
    """
    Consist._reset_registry_for_tests()

    equipment = build_debug_equipment()

    loco = equipment["loco"]
    boxcar = equipment["boxcar"]
    tankcar = equipment["tankcar"]
    intermodal = equipment["intermodal"]
    gondola = equipment["gondola"]
    caboose = equipment["caboose"]

    loco.rear_coupler.connect(boxcar.front_coupler)
    boxcar.rear_coupler.connect(intermodal.front_coupler)
    intermodal.rear_coupler.connect(gondola.front_coupler)
    gondola.rear_coupler.connect(caboose.front_coupler)
    road_consist = Consist(anchor=loco)

    pickup_consist = Consist(anchor=tankcar)

    print_section("=== STARTING STATE ===")
    print_boxed_render(
        road_consist, "Road consist before pickup_block(..., after_car=None)"
    )
    print_boxed_render(
        pickup_consist, "Pickup block before pickup_block(..., after_car=None)"
    )

    combined = SwitchingService.pickup_block(road_consist, pickup_consist)

    print_section("=== FINAL STATE ===")
    print_boxed_render(
        combined, "Combined consist after pickup_block(..., after_car=None)"
    )
    print_consist_summary(combined, "Combined consist summary after rear pickup")


def debug_pickup_middle() -> None:
    """
    Pick up a single car and insert it into the middle of the road train.

    Road consist:
        LOCO -> BOXCAR -> INTERMODAL -> GONDOLA -> CABOOSE

    Pickup block:
        TANKCAR

    Result:
        LOCO -> BOXCAR -> TANKCAR -> INTERMODAL -> GONDOLA -> CABOOSE
    """
    Consist._reset_registry_for_tests()

    equipment = build_debug_equipment()

    loco = equipment["loco"]
    boxcar = equipment["boxcar"]
    tankcar = equipment["tankcar"]
    intermodal = equipment["intermodal"]
    gondola = equipment["gondola"]
    caboose = equipment["caboose"]

    loco.rear_coupler.connect(boxcar.front_coupler)
    boxcar.rear_coupler.connect(intermodal.front_coupler)
    intermodal.rear_coupler.connect(gondola.front_coupler)
    gondola.rear_coupler.connect(caboose.front_coupler)
    road_consist = Consist(anchor=loco)

    pickup_consist = Consist(anchor=tankcar)

    print_section("=== STARTING STATE ===")
    print_boxed_render(
        road_consist, "Road consist before pickup_block(..., after_car=boxcar)"
    )
    print_boxed_render(
        pickup_consist, "Pickup block before pickup_block(..., after_car=boxcar)"
    )

    combined = SwitchingService.pickup_block(
        road_consist,
        pickup_consist,
        after_car=boxcar,
    )

    print_section("=== FINAL STATE ===")
    print_boxed_render(
        combined, "Combined consist after pickup_block(..., after_car=boxcar)"
    )
    print_consist_summary(combined, "Combined consist summary after middle pickup")


def run_scenario(name: str) -> str:
    """
    Run one debug scenario by name.

    Returns the canonical scenario name that was run.
    """
    scenario = normalize_scenario_name(name)

    print(f"Running Scenario {scenario}")
    print("=" * 80)

    if scenario == "summary":
        debug_data = build_debug_consist()
        consist = debug_data["consist"]
        print_compact_render(consist, "Compact consist render")
        print_boxed_render(consist, "Boxed consist render")
        print_consist_manifest(consist)
        print_consist_summary(consist)
        return scenario

    if scenario == "split_after":
        debug_split_after()
        return scenario

    if scenario == "split_before":
        debug_split_before()
        return scenario

    if scenario == "cut_after":
        debug_cut_after()
        return scenario

    if scenario == "cut_before":
        debug_cut_before()
        return scenario

    if scenario == "append":
        debug_append_consist()
        return scenario

    if scenario == "insert":
        debug_insert_block()
        return scenario

    if scenario == "setout":
        debug_setout()
        return scenario

    if scenario == "pickup_rear":
        debug_pickup_rear()
        return scenario

    if scenario == "pickup_middle":
        debug_pickup_middle()
        return scenario

    raise ValueError(f"Unknown scenario: {name}")


def interactive_shell() -> None:
    """
    Run an interactive command loop for consist debugging.
    """
    last_scenario: str | None = None

    print("Debug Consist Interactive Shell")
    print("=" * 80)
    print("Type a scenario name, an alias, 'help' for options, or 'exit' to quit.")
    print()

    print_available_commands()

    while True:
        try:
            raw = input("debug_consist> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            print("Exiting debug shell.")
            break

        if not raw:
            continue

        command = raw.lower()

        if command in EXIT_COMMANDS:
            print("Exiting debug shell.")
            break

        if command in HELP_COMMANDS:
            print()
            print_available_commands()
            continue

        if command in CLEAR_COMMANDS:
            clear_screen()
            print("Screen cleared.")
            print("-" * 80)
            continue

        if command in RERUN_COMMANDS:
            if last_scenario is None:
                print("No previous scenario has been run yet.")
                print("Run one first, then use 'rerun'.")
            else:
                try:
                    last_scenario = run_scenario(last_scenario)
                except Exception as exc:
                    print(f"Unexpected error while re-running scenario: {exc}")

            print("-" * 80)
            print()
            continue

        try:
            last_scenario = run_scenario(command)
        except ValueError as exc:
            print(f"Error: {exc}")
            print("Type 'help' to see the valid options.")
        except Exception as exc:
            print(f"Unexpected error: {exc}")

        print("-" * 80)
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Debug consist-building and switching scenarios."
    )
    parser.add_argument(
        "scenario",
        nargs="?",
        default=None,
        choices=[*VALID_SCENARIOS, *SCENARIO_ALIASES.keys()],
        help="Scenario to run once. If omitted, interactive mode starts.",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Start the interactive scenario shell.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all valid scenarios and aliases.",
    )

    args = parser.parse_args()

    if args.list:
        print_available_commands()
    elif args.interactive or args.scenario is None:
        interactive_shell()
    else:
        run_scenario(args.scenario)
