"""
Scenario 1: Freight Takes Siding

This scenario uses:
- real RailNetwork / Track / Junction topology
- real Consist objects with actual operational lengths
- FootprintService for multi-track occupancy
- TurnoutEvaluator for west/east switch fouling

Modeled district:
- Main West   : 3,000 ft
- Main Middle : 8,000 ft
- Main East   : 1,000 ft (or longer if you are testing extended territory)
- Siding      : 8,000 ft

Operational sequence:
- Eastbound freight takes the siding at the west turnout
- Westbound express military intermodal keeps the main
- After the express clears, the freight gets an all-clear and begins pulling
  back out via the east turnout
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from debug_equipment import build_debug_equipment

from railroad_sim.domain.consist import Consist
from railroad_sim.domain.enums import (
    JunctionType,
    MovementState,
    TrackEnd,
    TrackType,
    TravelDirection,
)
from railroad_sim.domain.junction import Junction, JunctionRoute, TrackEndpoint
from railroad_sim.domain.network.footprint_service import FootprintService
from railroad_sim.domain.network.position_types import ConsistExtent, NetworkPosition
from railroad_sim.domain.network.rail_network import RailNetwork
from railroad_sim.domain.network.turnout_evaluator import (
    TurnoutEvaluator,
    TurnoutWindow,
)
from railroad_sim.domain.network.turnout_occupancy import (
    TurnoutFoulingState,
    TurnoutZone,
)
from railroad_sim.domain.network.turnout_types import (
    TurnoutHand,
    TurnoutRouteKind,
)
from railroad_sim.domain.rolling_stock import RollingStock
from railroad_sim.domain.track import Track, TrackOccupancy


MAIN_WEST_LENGTH_FT = 3_000.0
MAIN_MIDDLE_LENGTH_FT = 8_000.0
MAIN_EAST_LENGTH_FT = 1_000.0
SIDING_LENGTH_FT = 8_000.0

TARGET_FREIGHT_LENGTH_FT = 6_500.0
TARGET_EXPRESS_LENGTH_FT = 3_200.0

TURNOUT_CLEARANCE_FT = 150.0


@dataclass(frozen=True)
class TrainPlacement:
    rear_track: str
    rear_offset_ft: float
    front_track: str
    front_offset_ft: float
    direction: TravelDirection
    speed_mph: float
    movement_state: MovementState


class ScenarioStage(NamedTuple):
    key: str
    title: str
    freight: TrainPlacement
    express: TrainPlacement | None = None
    note: str | None = None


@dataclass(frozen=True)
class TrainTurnoutReport:
    train_label: str
    turnout_name: str
    is_fouled: bool


def print_section(title: str) -> None:
    print(title)
    print("=" * 80)


def build_scenario_network() -> tuple[RailNetwork, dict[str, Track]]:
    """
    Build a topologically-correct meet/pass district:

        Main West --(west turnout)-- Main Middle --(east turnout)-- Main East
                           \\                                  //
                            \\----------- Siding -------------//

    Turnout locations exist as real network boundaries.
    """
    network = RailNetwork(name="Scenario 1 - Freight Takes Siding")

    main_west = Track(
        name="Main West",
        track_type=TrackType.MAINLINE,
        length_ft=MAIN_WEST_LENGTH_FT,
    )
    main_middle = Track(
        name="Main Middle",
        track_type=TrackType.MAINLINE,
        length_ft=MAIN_MIDDLE_LENGTH_FT,
    )
    main_east = Track(
        name="Main East",
        track_type=TrackType.MAINLINE,
        length_ft=MAIN_EAST_LENGTH_FT,
    )
    siding = Track(
        name="Siding",
        track_type=TrackType.SIDING,
        length_ft=SIDING_LENGTH_FT,
    )

    for track in (main_west, main_middle, main_east, siding):
        network.add_track(track)

    west_trunk = TrackEndpoint(track=main_west, end=TrackEnd.B)
    west_main = TrackEndpoint(track=main_middle, end=TrackEnd.A)
    west_siding = TrackEndpoint(track=siding, end=TrackEnd.A)

    west_main_route = JunctionRoute(from_endpoint=west_trunk, to_endpoint=west_main)
    west_siding_route = JunctionRoute(from_endpoint=west_trunk, to_endpoint=west_siding)

    west_turnout = Junction(
        name="WEST_TURNOUT",
        junction_type=JunctionType.TURNOUT,
        endpoints={west_trunk, west_main, west_siding},
        routes={west_main_route, west_siding_route},
        aligned_routes={west_main_route},
    )
    network.add_junction(west_turnout)

    east_trunk = TrackEndpoint(track=main_east, end=TrackEnd.A)
    east_main = TrackEndpoint(track=main_middle, end=TrackEnd.B)
    east_siding = TrackEndpoint(track=siding, end=TrackEnd.B)

    east_main_route = JunctionRoute(from_endpoint=east_trunk, to_endpoint=east_main)
    east_siding_route = JunctionRoute(from_endpoint=east_trunk, to_endpoint=east_siding)

    east_turnout = Junction(
        name="EAST_TURNOUT",
        junction_type=JunctionType.TURNOUT,
        endpoints={east_trunk, east_main, east_siding},
        routes={east_main_route, east_siding_route},
        aligned_routes={east_main_route},
    )
    network.add_junction(east_turnout)

    return network, {
        "main_west": main_west,
        "main_middle": main_middle,
        "main_east": main_east,
        "siding": siding,
    }


def build_turnout_zones() -> dict[str, TurnoutZone]:
    return {
        "west": TurnoutZone(
            name="WEST_TURNOUT",
            clearance_length_ft=TURNOUT_CLEARANCE_FT,
            hand=TurnoutHand.RIGHT,
            route_kind=TurnoutRouteKind.DIVERGING,
        ),
        "east": TurnoutZone(
            name="EAST_TURNOUT",
            clearance_length_ft=TURNOUT_CLEARANCE_FT,
            hand=TurnoutHand.LEFT,
            route_kind=TurnoutRouteKind.DIVERGING,
        ),
    }


def build_turnout_windows(
    turnout_zones: dict[str, TurnoutZone],
) -> dict[str, list[TurnoutWindow]]:
    west_clear = turnout_zones["west"].clearance_length_ft
    east_clear = turnout_zones["east"].clearance_length_ft

    return {
        "west": [
            TurnoutWindow(
                turnout_name=turnout_zones["west"].name,
                track_key="main_west",
                start_ft=max(0.0, MAIN_WEST_LENGTH_FT - west_clear),
                end_ft=MAIN_WEST_LENGTH_FT,
            ),
            TurnoutWindow(
                turnout_name=turnout_zones["west"].name,
                track_key="main_middle",
                start_ft=0.0,
                end_ft=min(MAIN_MIDDLE_LENGTH_FT, west_clear),
            ),
            TurnoutWindow(
                turnout_name=turnout_zones["west"].name,
                track_key="siding",
                start_ft=0.0,
                end_ft=min(SIDING_LENGTH_FT, west_clear),
            ),
        ],
        "east": [
            TurnoutWindow(
                turnout_name=turnout_zones["east"].name,
                track_key="main_middle",
                start_ft=max(0.0, MAIN_MIDDLE_LENGTH_FT - east_clear),
                end_ft=MAIN_MIDDLE_LENGTH_FT,
            ),
            TurnoutWindow(
                turnout_name=turnout_zones["east"].name,
                track_key="main_east",
                start_ft=0.0,
                end_ft=min(MAIN_EAST_LENGTH_FT, east_clear),
            ),
            TurnoutWindow(
                turnout_name=turnout_zones["east"].name,
                track_key="siding",
                start_ft=max(0.0, SIDING_LENGTH_FT - east_clear),
                end_ft=SIDING_LENGTH_FT,
            ),
        ],
    }


def couple_chain(equipment: list[RollingStock]) -> Consist:
    if not equipment:
        raise ValueError("equipment list cannot be empty")

    for left, right in zip(equipment, equipment[1:]):
        left.rear_coupler.connect(right.front_coupler)

    return Consist(anchor=equipment[0])


def build_freight_consist(
    target_length_ft: float = TARGET_FREIGHT_LENGTH_FT,
) -> Consist:
    """
    Build a long mixed freight until its actual operational length
    reaches/exceeds the target.
    """
    lead_set = build_debug_equipment()
    second_set = build_debug_equipment()

    equipment: list[RollingStock] = [
        lead_set["loco"],
        second_set["loco"],
    ]

    caboose_set = build_debug_equipment()
    caboose = caboose_set["caboose"]

    current_length = (
        sum(car.operational_length_ft for car in equipment)
        + caboose.operational_length_ft
    )

    while current_length < target_length_ft:
        candidate_set = build_debug_equipment()
        car_block: list[RollingStock] = [
            candidate_set["boxcar"],
            candidate_set["tankcar"],
            candidate_set["intermodal"],
            candidate_set["gondola"],
        ]

        equipment.extend(car_block)
        current_length += sum(car.operational_length_ft for car in car_block)

    equipment.append(caboose)
    return couple_chain(equipment)


def build_express_consist(
    target_length_ft: float = TARGET_EXPRESS_LENGTH_FT,
) -> Consist:
    """
    Build a shorter express military intermodal.
    """
    equipment_1 = build_debug_equipment()
    equipment_2 = build_debug_equipment()

    loco_1 = equipment_1["loco"]
    loco_2 = equipment_2["loco"]

    loco_1.rename_equipment("MILX", "0001")
    loco_2.rename_equipment("MILX", "0002")

    equipment: list[RollingStock] = [loco_1, loco_2]

    current_length = sum(car.operational_length_ft for car in equipment)

    while current_length < target_length_ft:
        car_set = build_debug_equipment()
        intermodal = car_set["intermodal"]
        equipment.append(intermodal)
        current_length += intermodal.operational_length_ft

    return couple_chain(equipment)


def make_extent(
    *,
    consist: Consist,
    rear_track: Track,
    rear_offset_ft: float,
    front_track: Track,
    front_offset_ft: float,
    travel_direction: TravelDirection,
) -> ConsistExtent:
    return ConsistExtent(
        consist=consist,
        rear_position=NetworkPosition(
            track_id=rear_track.track_id,
            offset_ft=rear_offset_ft,
        ),
        front_position=NetworkPosition(
            track_id=front_track.track_id,
            offset_ft=front_offset_ft,
        ),
        travel_direction=travel_direction,
    )


def clear_track_occupancies(tracks: dict[str, Track]) -> None:
    for track in tracks.values():
        track.occupancies.clear()


def apply_extent_to_network(
    *,
    footprint_service: FootprintService,
    extent: ConsistExtent,
    tracks_by_id: dict[str, Track],
    travel_direction: TravelDirection,
    speed_mph: float,
    movement_state: MovementState,
) -> None:
    footprint = footprint_service.footprint_for_extent(extent)

    for segment in footprint.segments:
        track = tracks_by_id[str(segment.track_id)]
        track.add_occupancy(
            TrackOccupancy(
                consist=extent.consist,
                rear_offset_ft=segment.rear_offset_ft,
                front_offset_ft=segment.front_offset_ft,
                travel_direction=travel_direction,
                speed_mph=speed_mph,
                movement_state=movement_state,
            )
        )


def make_fouling_state_map(
    reports: list[TrainTurnoutReport],
) -> dict[tuple[str, str], TurnoutFoulingState]:
    result: dict[tuple[str, str], TurnoutFoulingState] = {}
    for report in reports:
        result[(report.train_label, report.turnout_name)] = TurnoutFoulingState(
            turnout_name=report.turnout_name,
            is_fouled=report.is_fouled,
        )
    return result


def print_network_summary(network: RailNetwork) -> None:
    print_section("NETWORK TOPOLOGY")
    print(network.topology_summary())
    print()
    print(network.graph_debugger_summary())
    print()


def print_train_roster(
    *,
    freight_consist: Consist,
    express_consist: Consist,
) -> None:
    print_section("TRAIN LENGTHS")
    print(
        f"Freight actual length : {freight_consist.operational_length_ft:.0f} ft "
        f"({len(freight_consist.ordered_equipment())} units)"
    )
    print(
        f"Express actual length : {express_consist.operational_length_ft:.0f} ft "
        f"({len(express_consist.ordered_equipment())} units)"
    )
    print()


def print_extent_report(
    *,
    title: str,
    footprint_service: FootprintService,
    extent: ConsistExtent,
    expected_length_ft: float,
    track_lookup_by_id: dict[str, Track],
) -> None:
    validation = footprint_service.validate_extent(extent)
    if not validation.is_valid:
        raise ValueError(f"{title} extent invalid: {validation.reason.value}")

    path_names = [
        track_lookup_by_id[str(track_id)].name
        for track_id in validation.path_track_ids
    ]

    footprint = footprint_service.footprint_for_extent(extent)
    actual_length = footprint.total_occupied_length_ft

    if actual_length != expected_length_ft:
        raise ValueError(
            f"{title} length mismatch: expected {expected_length_ft:.0f} ft, "
            f"got {actual_length:.0f} ft"
        )

    print(title)
    print("-" * 80)
    print(
        f"rear position   : "
        f"{track_lookup_by_id[str(extent.rear_position.track_id)].name} "
        f"@ {extent.rear_position.offset_ft:.0f} ft"
    )
    print(
        f"front position  : "
        f"{track_lookup_by_id[str(extent.front_position.track_id)].name} "
        f"@ {extent.front_position.offset_ft:.0f} ft"
    )
    print(f"path            : {' -> '.join(path_names)}")
    print(f"track count     : {len(path_names)}")
    print(f"occupied length : {actual_length:.0f} ft")
    print()


def print_track_state(
    *,
    tracks: dict[str, Track],
) -> None:
    print_section("TRACK STATE")

    for key in ("main_west", "main_middle", "main_east", "siding"):
        track = tracks[key]
        state = "OCCUPIED" if track.is_occupied() else "CLEAR"

        print(f"{track.name}")
        print("-" * 80)
        print(f"length_ft       : {track.length_ft:.0f}")
        print(f"state           : {state}")
        print(f"ranges          : {track.occupied_ranges()}")
        print(f"overlapping?    : {track.has_overlapping_occupancies()}")
        print(f"opposing move?  : {track.has_opposing_movements()}")

        if track.occupancies:
            print("occupancies")
            for index, occupancy in enumerate(track.occupancies, start=1):
                print(
                    f"  [{index}] {occupancy.consist.anchor.equipment_id:<12} "
                    f"{occupancy.rear_offset_ft:>7.0f} -> {occupancy.front_offset_ft:<7.0f} "
                    f"{occupancy.travel_direction.value:<10} "
                    f"{occupancy.movement_state.value:<10} "
                    f"{occupancy.speed_mph:>5.1f} mph"
                )
        print()


def print_turnout_state(
    *,
    turnout_zones: dict[str, TurnoutZone],
    fouling_reports: list[TrainTurnoutReport],
    freight_consist: Consist,
    tracks: dict[str, Track],
) -> None:
    report_map = make_fouling_state_map(fouling_reports)
    turnout_names = {
        "west": turnout_zones["west"].name,
        "east": turnout_zones["east"].name,
    }

    freight_on_main = any(
        occupancy.consist is freight_consist
        for key in ("main_west", "main_middle", "main_east")
        for occupancy in tracks[key].occupancies
    )

    freight_west_fouled = report_map[("Freight", turnout_names["west"])].is_fouled
    freight_east_fouled = report_map[("Freight", turnout_names["east"])].is_fouled

    freight_fully_in_clear = (
        not freight_on_main
        and not freight_west_fouled
        and not freight_east_fouled
    )

    print_section("TURNOUT / FOULING STATE")

    for key in ("west", "east"):
        zone = turnout_zones[key]
        turnout_name = zone.name

        print(f"{turnout_name}")
        print("-" * 80)
        print(f"hand            : {zone.hand.value}")
        print(f"route_kind      : {zone.route_kind.value}")
        print(f"clearance_ft    : {zone.clearance_length_ft:.0f}")

        for train_label in ("Freight", "Express"):
            state = report_map.get((train_label, turnout_name))
            if state is None:
                print(f"{train_label:<16}: not present")
            else:
                print(f"{train_label:<16}: fouled={state.is_fouled}")
        print()

    print(f"freight_clear_of_main : {not freight_on_main}")
    print(f"freight_fully_in_clear: {freight_fully_in_clear}")
    print(f"freight_clear_of_east_turnout: {not freight_east_fouled}")
    print()


def build_scenario_stages(
    *,
    freight_length_ft: float,
    express_length_ft: float,
) -> tuple[ScenarioStage, ...]:
    """
    Define placements using the real segmented topology.
    """

    if freight_length_ft <= MAIN_WEST_LENGTH_FT:
        a_freight = TrainPlacement(
            rear_track="main_west",
            rear_offset_ft=MAIN_WEST_LENGTH_FT - freight_length_ft,
            front_track="main_west",
            front_offset_ft=MAIN_WEST_LENGTH_FT,
            direction=TravelDirection.TOWARD_B,
            speed_mph=20.0,
            movement_state=MovementState.MOVING,
        )
    else:
        a_freight = TrainPlacement(
            rear_track="main_west",
            rear_offset_ft=0.0,
            front_track="main_middle",
            front_offset_ft=freight_length_ft - MAIN_WEST_LENGTH_FT,
            direction=TravelDirection.TOWARD_B,
            speed_mph=20.0,
            movement_state=MovementState.MOVING,
        )

    b_siding_part = min(
        SIDING_LENGTH_FT - 500.0,
        max(1_500.0, freight_length_ft - MAIN_WEST_LENGTH_FT + 500.0),
    )
    b_rear_main_west = MAIN_WEST_LENGTH_FT + b_siding_part - freight_length_ft
    if b_rear_main_west < 0:
        raise ValueError("Freight is too long for Stage B geometry.")
    b_freight = TrainPlacement(
        rear_track="main_west",
        rear_offset_ft=b_rear_main_west,
        front_track="siding",
        front_offset_ft=b_siding_part,
        direction=TravelDirection.TOWARD_B,
        speed_mph=10.0,
        movement_state=MovementState.MOVING,
    )

    c_freight = TrainPlacement(
        rear_track="siding",
        rear_offset_ft=0.0,
        front_track="siding",
        front_offset_ft=freight_length_ft,
        direction=TravelDirection.TOWARD_B,
        speed_mph=5.0,
        movement_state=MovementState.MOVING,
    )

    d_rear_siding = TURNOUT_CLEARANCE_FT + 200.0
    d_front_siding = d_rear_siding + freight_length_ft
    if d_front_siding > SIDING_LENGTH_FT - TURNOUT_CLEARANCE_FT:
        raise ValueError(
            "Freight cannot clear both turnouts within the siding. "
            "Increase siding length or shorten the train."
        )
    d_freight = TrainPlacement(
        rear_track="siding",
        rear_offset_ft=d_rear_siding,
        front_track="siding",
        front_offset_ft=d_front_siding,
        direction=TravelDirection.TOWARD_B,
        speed_mph=0.0,
        movement_state=MovementState.STATIONARY,
    )

    e_express_front_on_middle = min(600.0, MAIN_MIDDLE_LENGTH_FT)
    e_express_rear_on_west = (
        MAIN_WEST_LENGTH_FT + e_express_front_on_middle - express_length_ft
    )
    if e_express_rear_on_west < 0:
        raise ValueError("Express is too long for Stage E west-turnout geometry.")
    e_express = TrainPlacement(
        rear_track="main_west",
        rear_offset_ft=e_express_rear_on_west,
        front_track="main_middle",
        front_offset_ft=e_express_front_on_middle,
        direction=TravelDirection.TOWARD_A,
        speed_mph=40.0,
        movement_state=MovementState.MOVING,
    )

    if express_length_ft >= MAIN_MIDDLE_LENGTH_FT - (2 * TURNOUT_CLEARANCE_FT):
        raise ValueError("Express is too long to fit fully between turnouts without fouling.")
    f_rear_middle = TURNOUT_CLEARANCE_FT + 500.0
    f_front_middle = f_rear_middle + express_length_ft
    if f_front_middle > MAIN_MIDDLE_LENGTH_FT - TURNOUT_CLEARANCE_FT:
        raise ValueError("Express Stage F does not fit between turnout clearance limits.")
    f_express = TrainPlacement(
        rear_track="main_middle",
        rear_offset_ft=f_rear_middle,
        front_track="main_middle",
        front_offset_ft=f_front_middle,
        direction=TravelDirection.TOWARD_A,
        speed_mph=40.0,
        movement_state=MovementState.MOVING,
    )

    g_express_front_on_east = min(600.0, MAIN_EAST_LENGTH_FT)
    g_express_rear_on_middle = (
        MAIN_MIDDLE_LENGTH_FT + g_express_front_on_east - express_length_ft
    )
    if g_express_rear_on_middle < 0:
        raise ValueError("Express is too long for Stage G east-turnout geometry.")
    g_express = TrainPlacement(
        rear_track="main_middle",
        rear_offset_ft=g_express_rear_on_middle,
        front_track="main_east",
        front_offset_ft=g_express_front_on_east,
        direction=TravelDirection.TOWARD_A,
        speed_mph=40.0,
        movement_state=MovementState.MOVING,
    )

    h_freight = d_freight

    i_front_on_main_east = min(600.0, MAIN_EAST_LENGTH_FT)
    i_rear_on_siding = SIDING_LENGTH_FT + i_front_on_main_east - freight_length_ft
    if i_rear_on_siding < 0:
        raise ValueError("Freight is too long for Stage I east-turnout geometry.")
    i_freight = TrainPlacement(
        rear_track="siding",
        rear_offset_ft=i_rear_on_siding,
        front_track="main_east",
        front_offset_ft=i_front_on_main_east,
        direction=TravelDirection.TOWARD_B,
        speed_mph=8.0,
        movement_state=MovementState.MOVING,
    )

    j_front_on_main_east = min(900.0, MAIN_EAST_LENGTH_FT)
    j_rear_on_siding = SIDING_LENGTH_FT + j_front_on_main_east - freight_length_ft
    if j_rear_on_siding < 0:
        raise ValueError("Freight is too long for Stage J east-turnout geometry.")
    j_freight = TrainPlacement(
        rear_track="siding",
        rear_offset_ft=j_rear_on_siding,
        front_track="main_east",
        front_offset_ft=j_front_on_main_east,
        direction=TravelDirection.TOWARD_B,
        speed_mph=12.0,
        movement_state=MovementState.MOVING,
    )

    if MAIN_EAST_LENGTH_FT >= freight_length_ft + TURNOUT_CLEARANCE_FT:
        k_rear_on_main_east = TURNOUT_CLEARANCE_FT + 50.0
        k_front_on_main_east = k_rear_on_main_east + freight_length_ft

        if k_front_on_main_east > MAIN_EAST_LENGTH_FT:
            raise ValueError(
                "Stage K on Main East exceeds modeled eastward main length."
            )

        k_freight = TrainPlacement(
            rear_track="main_east",
            rear_offset_ft=k_rear_on_main_east,
            front_track="main_east",
            front_offset_ft=k_front_on_main_east,
            direction=TravelDirection.TOWARD_B,
            speed_mph=15.0,
            movement_state=MovementState.MOVING,
        )
    else:
        k_front_on_main_east = MAIN_EAST_LENGTH_FT
        k_rear_on_main_middle = (
            MAIN_MIDDLE_LENGTH_FT + k_front_on_main_east - freight_length_ft
        )

        if k_rear_on_main_middle < TURNOUT_CLEARANCE_FT:
            raise ValueError(
                "Freight is too long to clear the east turnout on the main "
                "within the modeled district."
            )

        if k_rear_on_main_middle > MAIN_MIDDLE_LENGTH_FT:
            raise ValueError("Stage K rear offset exceeds Main Middle length.")

        k_freight = TrainPlacement(
            rear_track="main_middle",
            rear_offset_ft=k_rear_on_main_middle,
            front_track="main_east",
            front_offset_ft=k_front_on_main_east,
            direction=TravelDirection.TOWARD_B,
            speed_mph=15.0,
            movement_state=MovementState.MOVING,
        )

    return (
        ScenarioStage(
            key="a",
            title="Stage A - Freight fully on main, approaching the west turnout",
            freight=a_freight,
        ),
        ScenarioStage(
            key="b",
            title="Stage B - Freight partially into siding, fouling west turnout",
            freight=b_freight,
        ),
        ScenarioStage(
            key="c",
            title="Stage C - Freight just fully inside siding",
            freight=c_freight,
            note="Main is clear here, but turnout clearance still depends on exact rear/front location.",
        ),
        ScenarioStage(
            key="d",
            title="Stage D - Freight fully in the clear on the siding",
            freight=d_freight,
            note="This is the proper hold-in-the-hole condition.",
        ),
        ScenarioStage(
            key="e",
            title="Stage E - Express enters from the west and fouls west turnout",
            freight=d_freight,
            express=e_express,
        ),
        ScenarioStage(
            key="f",
            title="Stage F - Express on the main between turnouts",
            freight=d_freight,
            express=f_express,
        ),
        ScenarioStage(
            key="g",
            title="Stage G - Express reaches the east side and fouls east turnout",
            freight=d_freight,
            express=g_express,
        ),
        ScenarioStage(
            key="h",
            title="Stage H - Express clear, all-clear signal for freight to re-enter main",
            freight=h_freight,
            note="Dispatcher gives the freight an all-clear after the express fully clears the district.",
        ),
        ScenarioStage(
            key="i",
            title="Stage I - Freight begins pulling out, fouling east turnout",
            freight=i_freight,
        ),
        ScenarioStage(
            key="j",
            title="Stage J - Freight farther onto main, still fouling east turnout",
            freight=j_freight,
        ),
        ScenarioStage(
            key="k",
            title="Stage K - Freight fully back on main and clear of the turnout",
            freight=k_freight,
            note=(
                "Freight has re-established on the main and is clear of the east turnout."
                if MAIN_EAST_LENGTH_FT >= freight_length_ft + TURNOUT_CLEARANCE_FT
                else
                "Freight has re-established on the main, but still fouls the east turnout. "
                "Additional mainline territory east of the control point is required to "
                "show the freight fully clear of the turnout."
            ),
        ),
    )


def run_stage(
    *,
    stage: ScenarioStage,
    tracks: dict[str, Track],
    footprint_service: FootprintService,
    track_lookup_by_id: dict[str, Track],
    track_key_by_id: dict[str, str],
    turnout_zones: dict[str, TurnoutZone],
    freight_consist: Consist,
    express_consist: Consist,
) -> None:
    clear_track_occupancies(tracks)

    turnout_windows = build_turnout_windows(turnout_zones)
    evaluator = TurnoutEvaluator(
        footprint_service=footprint_service,
        track_key_by_id=track_key_by_id,
    )

    freight_extent = make_extent(
        consist=freight_consist,
        rear_track=tracks[stage.freight.rear_track],
        rear_offset_ft=stage.freight.rear_offset_ft,
        front_track=tracks[stage.freight.front_track],
        front_offset_ft=stage.freight.front_offset_ft,
        travel_direction=stage.freight.direction,
    )

    print_section(stage.title)
    print_extent_report(
        title="Freight extent",
        footprint_service=footprint_service,
        extent=freight_extent,
        expected_length_ft=freight_consist.operational_length_ft,
        track_lookup_by_id=track_lookup_by_id,
    )

    apply_extent_to_network(
        footprint_service=footprint_service,
        extent=freight_extent,
        tracks_by_id=track_lookup_by_id,
        travel_direction=stage.freight.direction,
        speed_mph=stage.freight.speed_mph,
        movement_state=stage.freight.movement_state,
    )

    freight_turnout_states = evaluator.evaluate_extent(
        extent=freight_extent,
        turnout_windows_by_key=turnout_windows,
    )

    active_turnout_reports = [
        TrainTurnoutReport(
            train_label="Freight",
            turnout_name=state.turnout_name,
            is_fouled=state.is_fouled,
        )
        for state in freight_turnout_states.values()
    ]

    if stage.express is not None:
        express_extent = make_extent(
            consist=express_consist,
            rear_track=tracks[stage.express.rear_track],
            rear_offset_ft=stage.express.rear_offset_ft,
            front_track=tracks[stage.express.front_track],
            front_offset_ft=stage.express.front_offset_ft,
            travel_direction=stage.express.direction,
        )

        print_extent_report(
            title="Express extent",
            footprint_service=footprint_service,
            extent=express_extent,
            expected_length_ft=express_consist.operational_length_ft,
            track_lookup_by_id=track_lookup_by_id,
        )

        apply_extent_to_network(
            footprint_service=footprint_service,
            extent=express_extent,
            tracks_by_id=track_lookup_by_id,
            travel_direction=stage.express.direction,
            speed_mph=stage.express.speed_mph,
            movement_state=stage.express.movement_state,
        )

        express_turnout_states = evaluator.evaluate_extent(
            extent=express_extent,
            turnout_windows_by_key=turnout_windows,
        )

        active_turnout_reports.extend(
            TrainTurnoutReport(
                train_label="Express",
                turnout_name=state.turnout_name,
                is_fouled=state.is_fouled,
            )
            for state in express_turnout_states.values()
        )
    else:
        for turnout_name in (
            turnout_zones["west"].name,
            turnout_zones["east"].name,
        ):
            active_turnout_reports.append(
                TrainTurnoutReport(
                    train_label="Express",
                    turnout_name=turnout_name,
                    is_fouled=False,
                )
            )

    print_track_state(tracks=tracks)
    print_turnout_state(
        turnout_zones=turnout_zones,
        fouling_reports=active_turnout_reports,
        freight_consist=freight_consist,
        tracks=tracks,
    )

    if stage.note:
        print("NOTE")
        print("-" * 80)
        print(stage.note)
        print()


def run_scenario(selected_stage: str | None = None) -> None:
    Consist._reset_registry_for_tests()

    freight_consist = build_freight_consist()
    express_consist = build_express_consist()

    network, tracks = build_scenario_network()
    turnout_zones = build_turnout_zones()
    footprint_service = FootprintService(network=network)
    track_lookup_by_id = {str(track.track_id): track for track in tracks.values()}
    track_key_by_id = {str(track.track_id): key for key, track in tracks.items()}

    stages = build_scenario_stages(
        freight_length_ft=freight_consist.operational_length_ft,
        express_length_ft=express_consist.operational_length_ft,
    )

    print_network_summary(network)
    print_train_roster(
        freight_consist=freight_consist,
        express_consist=express_consist,
    )

    for stage in stages:
        if selected_stage is not None and stage.key != selected_stage.lower():
            continue

        run_stage(
            stage=stage,
            tracks=tracks,
            footprint_service=footprint_service,
            track_lookup_by_id=track_lookup_by_id,
            track_key_by_id=track_key_by_id,
            turnout_zones=turnout_zones,
            freight_consist=freight_consist,
            express_consist=express_consist,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Scenario 1: freight takes siding using real topology, "
            "real consist lengths, track occupancy, and turnout fouling."
        )
    )
    parser.add_argument(
        "stage",
        nargs="?",
        default=None,
        choices=["a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k"],
        help="Run only one stage: a, b, c, d, e, f, g, h, i, j, or k",
    )
    args = parser.parse_args()

    run_scenario(args.stage)
