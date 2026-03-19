import sys
from pathlib import Path
from typing import TypedDict
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from debug_equipment import build_debug_equipment

from railroad_sim.domain.consist import Consist
from railroad_sim.domain.enums import (
    JunctionType,
    MovementState,
    TrackCondition,
    TrackEnd,
    TrackTrafficRule,
    TrackType,
    TravelDirection,
)
from railroad_sim.domain.junction import Junction, JunctionRoute, TrackEndpoint
from railroad_sim.domain.network.boundary_connection import BoundaryConnection
from railroad_sim.domain.network.footprint_service import FootprintService
from railroad_sim.domain.network.position_types import ConsistExtent, NetworkPosition
from railroad_sim.domain.network.rail_network import RailNetwork
from railroad_sim.domain.network.topology_movement_service import (
    TopologyMovementService,
)
from railroad_sim.domain.track import Track, TrackOccupancy


class DebugNetworkContext(TypedDict):
    j_west: Junction
    j_east: Junction
    j_yard: Junction
    j_west_route: JunctionRoute
    turnout_main_route: JunctionRoute
    turnout_siding_route: JunctionRoute
    j_yard_route: JunctionRoute
    boundary: BoundaryConnection


# -----------------------------------------------------------------------------
# Formatting helpers
# -----------------------------------------------------------------------------


def rule(width: int = 88, char: str = "=") -> str:
    return char * width


def section(title: str) -> None:
    print(rule())
    print(title)
    print(rule())


# -----------------------------------------------------------------------------
# Consist helpers
# -----------------------------------------------------------------------------


def make_debug_equipment_consist() -> Consist:
    """
    Build the same mixed consist used by the other debug tools.

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

    return Consist(anchor=loco)


# -----------------------------------------------------------------------------
# Network builders
# -----------------------------------------------------------------------------


def endpoint(track: Track, end: TrackEnd) -> TrackEndpoint:
    return TrackEndpoint(track=track, end=end)


def route(
    from_track: Track,
    from_end: TrackEnd,
    to_track: Track,
    to_end: TrackEnd,
) -> JunctionRoute:
    return JunctionRoute(
        from_endpoint=endpoint(from_track, from_end),
        to_endpoint=endpoint(to_track, to_end),
    )


def build_debug_network() -> tuple[RailNetwork, dict[str, Track], DebugNetworkContext]:
    network = RailNetwork(name="Pacific North - Dispatcher Sandbox")

    tracks: dict[str, Track] = {
        "main_1": Track(
            name="Main 1",
            track_type=TrackType.MAINLINE,
            length_ft=5000,
            traffic_rule=TrackTrafficRule.BIDIRECTIONAL,
        ),
        "main_2": Track(
            name="Main 2",
            track_type=TrackType.MAINLINE,
            length_ft=5000,
            traffic_rule=TrackTrafficRule.BIDIRECTIONAL,
        ),
        "main_3": Track(
            name="Main 3",
            track_type=TrackType.MAINLINE,
            length_ft=5000,
            traffic_rule=TrackTrafficRule.BIDIRECTIONAL,
        ),
        "siding_1": Track(
            name="Siding 1",
            track_type=TrackType.SIDING,
            length_ft=2200,
            traffic_rule=TrackTrafficRule.BIDIRECTIONAL,
        ),
        "yard_lead": Track(
            name="Yard Lead",
            track_type=TrackType.YARD,
            length_ft=1800,
            traffic_rule=TrackTrafficRule.A_TO_B_ONLY,
        ),
    }

    for track in tracks.values():
        network.add_track(track)

    j_west_route = route(tracks["main_1"], TrackEnd.B, tracks["main_2"], TrackEnd.A)
    j_west = Junction(
        name="J-WEST",
        junction_type=JunctionType.CONNECTION,
        endpoints={j_west_route.from_endpoint, j_west_route.to_endpoint},
        routes={j_west_route},
        aligned_routes={j_west_route},
    )
    network.add_junction(j_west)

    turnout_main_route = route(
        tracks["main_2"], TrackEnd.B, tracks["main_3"], TrackEnd.A
    )
    turnout_siding_route = route(
        tracks["main_2"], TrackEnd.B, tracks["siding_1"], TrackEnd.A
    )
    j_east = Junction(
        name="J-EAST",
        junction_type=JunctionType.TURNOUT,
        endpoints={
            turnout_main_route.from_endpoint,
            turnout_main_route.to_endpoint,
            turnout_siding_route.to_endpoint,
        },
        routes={turnout_main_route, turnout_siding_route},
        aligned_routes={turnout_main_route},
    )
    network.add_junction(j_east)

    j_yard_route = route(tracks["main_3"], TrackEnd.B, tracks["yard_lead"], TrackEnd.A)
    j_yard = Junction(
        name="J-YARD",
        junction_type=JunctionType.CONNECTION,
        endpoints={j_yard_route.from_endpoint, j_yard_route.to_endpoint},
        routes={j_yard_route},
        aligned_routes={j_yard_route},
    )
    network.add_junction(j_yard)

    boundary = BoundaryConnection(
        local_endpoint=endpoint(tracks["main_1"], TrackEnd.A),
        remote_network_id=uuid4(),
        remote_track_id=uuid4(),
        remote_end=TrackEnd.B,
        name="West Staging Connection",
    )
    network.add_boundary_connection(boundary)

    context: DebugNetworkContext = {
        "j_west": j_west,
        "j_east": j_east,
        "j_yard": j_yard,
        "j_west_route": j_west_route,
        "turnout_main_route": turnout_main_route,
        "turnout_siding_route": turnout_siding_route,
        "j_yard_route": j_yard_route,
        "boundary": boundary,
    }

    return network, tracks, context


# -----------------------------------------------------------------------------
# Occupancy / footprint helpers
# -----------------------------------------------------------------------------


def clear_all_occupancies(network: RailNetwork) -> None:
    for track in network.tracks.values():
        track.occupancies.clear()


def apply_extent_to_tracks(
    network: RailNetwork,
    extent: ConsistExtent,
    *,
    speed_mph: float,
    movement_state: MovementState,
) -> None:
    clear_all_occupancies(network)

    footprint_service = FootprintService(network)
    footprint = footprint_service.footprint_for_extent(extent)

    for segment in footprint.segments:
        track = network.get_track(segment.track_id)
        track.add_occupancy(
            TrackOccupancy(
                consist=extent.consist,
                rear_offset_ft=segment.rear_offset_ft,
                front_offset_ft=segment.front_offset_ft,
                travel_direction=extent.travel_direction,
                speed_mph=speed_mph,
                movement_state=movement_state,
            )
        )


# -----------------------------------------------------------------------------
# Reporting helpers
# -----------------------------------------------------------------------------


def format_endpoint(ep: TrackEndpoint) -> str:
    return f"{ep.track.name}:{ep.end.value}"


def format_route(route_obj: JunctionRoute) -> str:
    return (
        f"{format_endpoint(route_obj.from_endpoint)}"
        f" -> "
        f"{format_endpoint(route_obj.to_endpoint)}"
    )


def print_network_summaries(network: RailNetwork) -> None:
    section("TOPOLOGY SUMMARY")
    print(network.topology_summary())
    print()
    section("GRAPH DEBUGGER SUMMARY")
    print(network.graph_debugger_summary())
    print()


def print_track_inventory(network: RailNetwork) -> None:
    section("TRACK INVENTORY")
    for track in network.tracks.values():
        print(
            f"{track.name:<10} "
            f"type={track.track_type.value:<10} "
            f"length={track.length_ft:>6.0f}ft "
            f"condition={track.condition.value:<14} "
            f"rule={track.traffic_rule.value}"
        )
    print()


def print_junction_state(context: DebugNetworkContext) -> None:
    section("JUNCTION ALIGNMENT")
    for junction in (context["j_west"], context["j_east"], context["j_yard"]):
        print(f"{junction.name} ({junction.junction_type.value})")
        for rt in sorted(junction.routes, key=format_route):
            aligned = "ALIGNED" if rt in junction.aligned_routes else "NOT ALIGNED"
            print(f"  {aligned:<12} {format_route(rt)}")
        print()


def print_movement_options(network: RailNetwork, track: Track) -> None:
    service = TopologyMovementService(network)
    section(f"MOVEMENT OPTIONS FROM {track.name.upper()}")
    options = service.movement_options_from_track(track.track_id)

    if not options:
        print("(none)\n")
        return

    for option in options:
        source = format_endpoint(option.source_endpoint)

        if option.kind.value == "boundary":
            print(f"{source} -> BOUNDARY [{option.boundary_connection_id}]")
            continue

        destination = (
            format_endpoint(option.destination_endpoint)
            if option.destination_endpoint is not None
            else "(unknown)"
        )
        route_text = (
            format_route(option.required_route)
            if option.required_route is not None
            else "(none)"
        )
        aligned = "aligned" if option.is_currently_aligned else "misaligned"

        print(
            f"{source} -> {destination} "
            f"via junction={option.junction_id} "
            f"route=({route_text}) "
            f"[{aligned}]"
        )
    print()


def print_path_report(network: RailNetwork, from_track: Track, to_track: Track) -> None:
    service = TopologyMovementService(network)
    result = service.can_move_between_tracks(from_track.track_id, to_track.track_id)

    section(f"PATH REPORT: {from_track.name} -> {to_track.name}")
    print(f"path_exists    : {result.path_exists}")
    print(f"can_move       : {result.can_move}")
    print(f"blocked_reason : {result.blocked_reason.value}")

    if result.path is not None:
        print(
            "track_path     : "
            + " -> ".join(network.get_track(tid).name for tid in result.path.track_ids)
        )
        print("steps          :")
        for step in result.path.steps:
            aligned = "aligned" if step.is_currently_aligned else "misaligned"
            print(
                "  "
                + f"{format_endpoint(step.from_endpoint)}"
                + f" -> {format_endpoint(step.to_endpoint)} "
                + f"[{aligned}]"
            )

    if result.blocked_track_id is not None:
        print(f"blocked_track  : {network.get_track(result.blocked_track_id).name}")

    if result.blocked_route is not None:
        print(f"blocked_route  : {format_route(result.blocked_route)}")

    print()


def print_extent_report(network: RailNetwork, extent: ConsistExtent) -> None:
    footprint_service = FootprintService(network)
    validation = footprint_service.validate_extent(extent)

    section("CONSIST EXTENT / FOOTPRINT")
    print(f"extent valid   : {validation.is_valid}")
    print(f"reason         : {validation.reason.value}")

    if not validation.is_valid:
        print()
        return

    print(
        "path_tracks     : "
        + " -> ".join(network.get_track(tid).name for tid in validation.path_track_ids)
    )

    footprint = footprint_service.footprint_for_extent(extent)
    print(f"track_count     : {footprint.track_count}")
    print(f"total_length_ft : {footprint.total_occupied_length_ft:.1f}")
    print("segments        :")
    for segment in footprint.segments:
        track = network.get_track(segment.track_id)
        print(
            f"  {track.name:<10} "
            f"{segment.rear_offset_ft:>7.1f} -> {segment.front_offset_ft:<7.1f} "
            f"len={segment.length_ft:.1f}"
        )
    print()


def print_track_occupancy_status(network: RailNetwork) -> None:
    section("TRACK OCCUPANCY STATUS")
    for track in network.tracks.values():
        occupancy_flag = "OCCUPIED" if track.is_occupied() else "CLEAR"
        availability_flag = "AVAILABLE" if track.is_available() else "OUT"
        overlap_flag = "OVERLAP" if track.has_overlapping_occupancies() else "-"
        opposing_flag = "OPPOSING" if track.has_opposing_movements() else "-"

        print(
            f"{track.name:<10} "
            f"state={occupancy_flag:<8} "
            f"availability={availability_flag:<9} "
            f"overlap={overlap_flag:<8} "
            f"opposing={opposing_flag}"
        )

        for occupancy in track.occupancies:
            consist_label = describe_consist(occupancy.consist)
            print(
                "  "
                + f"{consist_label:<18} "
                + f"{occupancy.rear_offset_ft:>7.1f} -> {occupancy.front_offset_ft:<7.1f} "
                + f"dir={occupancy.travel_direction.value:<10} "
                + f"speed={occupancy.speed_mph:<5.1f} "
                + f"state={occupancy.movement_state.value}"
            )
        print()


def describe_consist(consist: Consist) -> str:
    ordered = consist.ordered_equipment()
    head = ordered[0]
    tail = ordered[-1]
    return f"{head.equipment_short_name} {head.equipment_id} .. {tail.equipment_id}"


# -----------------------------------------------------------------------------
# Demo scenario
# -----------------------------------------------------------------------------


def build_demo_extent(network_tracks: dict[str, Track]) -> ConsistExtent:
    consist = make_debug_equipment_consist()

    return ConsistExtent(
        consist=consist,
        rear_position=NetworkPosition(
            track_id=network_tracks["main_1"].track_id,
            offset_ft=4200,
        ),
        front_position=NetworkPosition(
            track_id=network_tracks["main_2"].track_id,
            offset_ft=1700,
        ),
        travel_direction=TravelDirection.TOWARD_B,
    )


def main() -> None:
    network, tracks, context = build_debug_network()
    extent = build_demo_extent(tracks)

    print_network_summaries(network)
    print_track_inventory(network)
    print_junction_state(context)

    print_movement_options(network, tracks["main_1"])
    print_movement_options(network, tracks["main_2"])

    print_path_report(network, tracks["main_1"], tracks["main_3"])
    print_path_report(network, tracks["main_1"], tracks["siding_1"])
    print_path_report(network, tracks["main_1"], tracks["yard_lead"])

    print_extent_report(network, extent)
    apply_extent_to_tracks(
        network,
        extent,
        speed_mph=18.0,
        movement_state=MovementState.MOVING,
    )
    print_track_occupancy_status(network)

    section("TURNOUT REALIGNMENT TEST")
    context["j_east"].aligned_routes = {context["turnout_siding_route"]}
    print("J-EAST aligned to siding route.")
    print()
    print_junction_state(context)
    print_path_report(network, tracks["main_1"], tracks["main_3"])
    print_path_report(network, tracks["main_1"], tracks["siding_1"])

    section("TRACK CONDITION BLOCK TEST")
    tracks["main_3"].condition = TrackCondition.OUT_OF_SERVICE
    print("Main 3 marked OUT_OF_SERVICE.")
    print()
    print_track_inventory(network)
    print_path_report(network, tracks["main_1"], tracks["main_3"])
    print_path_report(network, tracks["main_1"], tracks["yard_lead"])


if __name__ == "__main__":
    main()
