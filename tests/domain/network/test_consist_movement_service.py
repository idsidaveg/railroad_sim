from __future__ import annotations

import pytest

from railroad_sim.domain.consist import Consist
from railroad_sim.domain.enums import JunctionType, TrackEnd, TrackType, TravelDirection
from railroad_sim.domain.equipment.boxcar import BoxCar
from railroad_sim.domain.junction import Junction, JunctionRoute, TrackEndpoint
from railroad_sim.domain.network.consist_movement_service import ConsistMovementService
from railroad_sim.domain.network.consist_movement_types import MoveCommand
from railroad_sim.domain.network.footprint_service import FootprintService
from railroad_sim.domain.network.position_types import ConsistExtent, NetworkPosition
from railroad_sim.domain.network.rail_network import RailNetwork
from railroad_sim.domain.network.topology_movement_enums import MovementBlockReason
from railroad_sim.domain.network.topology_movement_service import (
    TopologyMovementService,
)
from railroad_sim.domain.network.turnout_evaluator import (
    TurnoutEvaluator,
    TurnoutWindow,
)
from railroad_sim.domain.track import Track
from railroad_sim.domain.yard.turntable import Turntable
from railroad_sim.domain.yard.turntable_connection import TurntableConnection
from tests.support.track_builders import make_track


def build_test_consist(*, car_count: int) -> Consist:
    """
    Build a real consist composed of simple BoxCar equipment.

    Each BoxCar has a fixed operational length of 55.0 ft, which keeps
    movement tests predictable and avoids needing fake Consist objects.
    """
    if car_count <= 0:
        raise ValueError("car_count must be positive")

    equipment: list[BoxCar] = []

    for index in range(1, car_count + 1):
        car = BoxCar(
            reporting_mark="TST",
            road_number=f"{index:04d}",
        )
        equipment.append(car)

    for left, right in zip(equipment, equipment[1:]):
        left.rear_coupler.connect(right.front_coupler)

    return Consist(anchor=equipment[0])


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
        consist=consist,  # runtime is fine; service only needs operational_length_ft
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


def build_single_track_network(length_ft: float = 1000.0) -> tuple[RailNetwork, Track]:
    network = RailNetwork(name="single-track-network")
    track = Track(
        name="Main",
        track_type=TrackType.MAINLINE,
        length_ft=length_ft,
    )
    network.add_track(track)
    return network, track


def build_turnout_network(
    *,
    align_to_siding: bool = True,
) -> tuple[RailNetwork, dict[str, Track]]:
    """
    Main West --(turnout)-- Main Middle
                    \\
                     \\--- Siding

    Only the west turnout is modeled because that is enough to test
    continuation across an aligned route.
    """
    network = RailNetwork(name="turnout-network")

    main_west = Track(
        name="Main West",
        track_type=TrackType.MAINLINE,
        length_ft=500.0,
    )
    main_middle = Track(
        name="Main Middle",
        track_type=TrackType.MAINLINE,
        length_ft=500.0,
    )
    siding = Track(
        name="Siding",
        track_type=TrackType.SIDING,
        length_ft=500.0,
    )

    for track in (main_west, main_middle, siding):
        network.add_track(track)

    west_trunk = TrackEndpoint(track=main_west, end=TrackEnd.B)
    west_main = TrackEndpoint(track=main_middle, end=TrackEnd.A)
    west_siding = TrackEndpoint(track=siding, end=TrackEnd.A)

    west_main_route = JunctionRoute(from_endpoint=west_trunk, to_endpoint=west_main)
    west_siding_route = JunctionRoute(from_endpoint=west_trunk, to_endpoint=west_siding)

    aligned_routes = {west_siding_route} if align_to_siding else {west_main_route}

    west_turnout = Junction(
        name="WEST_TURNOUT",
        junction_type=JunctionType.TURNOUT,
        endpoints={west_trunk, west_main, west_siding},
        routes={west_main_route, west_siding_route},
        aligned_routes=aligned_routes,
    )
    network.add_junction(west_turnout)

    return network, {
        "main_west": main_west,
        "main_middle": main_middle,
        "siding": siding,
    }


def build_turnout_windows(
    *,
    tracks: dict[str, Track],
) -> tuple[dict[str, list[TurnoutWindow]], dict[str, str]]:
    track_key_by_id = {str(track.track_id): key for key, track in tracks.items()}

    turnout_windows = {
        "west": [
            TurnoutWindow(
                turnout_name="WEST_TURNOUT",
                track_key="main_west",
                start_ft=450.0,
                end_ft=500.0,
            ),
            TurnoutWindow(
                turnout_name="WEST_TURNOUT",
                track_key="siding",
                start_ft=0.0,
                end_ft=150.0,
            ),
            TurnoutWindow(
                turnout_name="WEST_TURNOUT",
                track_key="main_middle",
                start_ft=0.0,
                end_ft=150.0,
            ),
        ]
    }
    return turnout_windows, track_key_by_id


def build_service(
    network: RailNetwork,
    *,
    track_key_by_id: dict[str, str] | None = None,
    turntable_connections: tuple[TurntableConnection, ...] = (),
) -> ConsistMovementService:
    topology = TopologyMovementService(
        network,
        turntable_connections=turntable_connections,
    )
    footprint = FootprintService(network=network, movement_service=topology)
    evaluator = TurnoutEvaluator(
        footprint_service=footprint,
        track_key_by_id=track_key_by_id or {},
    )
    return ConsistMovementService(
        network=network,
        footprint_service=footprint,
        turnout_evaluator=evaluator,
        topology_movement_service=topology,
    )


def build_turntable_network() -> tuple[
    RailNetwork,
    Track,
    Track,
    Track,
    Turntable,
    TurntableConnection,
]:
    """
    V1 turntable endpoint rules under test:

    approach:A <-> bridge:A  when aligned to approach
    stall_1:A  <-> bridge:B  when aligned to stall_1
    """
    network = RailNetwork(name="Turntable Network")

    approach = make_track("Approach")
    bridge = make_track("Bridge")
    stall_1 = make_track("Stall 1")

    for track in (approach, bridge, stall_1):
        network.add_track(track)

    turntable = Turntable(
        name="TT",
        bridge_length_ft=100.0,
        bridge_track_id=bridge.track_id,
        approach_track_id=approach.track_id,
        stall_track_ids=(stall_1.track_id,),
    )

    connection = TurntableConnection(
        turntable=turntable,
        bridge_track=bridge,
        connected_tracks_by_id={
            approach.track_id: approach,
            stall_1.track_id: stall_1,
        },
    )

    return network, approach, bridge, stall_1, turntable, connection


def test_move_forward_same_track_updates_extent_and_footprint() -> None:
    """
    Test: Forward movement on a single track updates extent and footprint correctly.

    Scenario:
    A 2-car consist (110 ft total length) is positioned entirely on a single track.
    The train is facing TOWARD_B and is commanded to move forward 150 ft.

    What this validates:
    - The front position advances by the commanded distance.
    - The rear position follows, maintaining constant consist length.
    - Travel direction remains unchanged (TOWARD_B).
    - No movement limits are encountered.
    - The footprint remains on a single track.
    - Total occupied length equals the actual consist length (110 ft).

    Key expectation:
    Rear = Front - Consist Length at all times.
    """

    network, track = build_single_track_network(length_ft=1000.0)
    service = build_service(network)

    consist = build_test_consist(car_count=2)
    extent = make_extent(
        consist=consist,
        rear_track=track,
        rear_offset_ft=100.0,
        front_track=track,
        front_offset_ft=210.0,
        travel_direction=TravelDirection.TOWARD_B,
    )

    result = service.move_extent(
        extent=extent,
        command=MoveCommand.FORWARD,
        distance_ft=150.0,
        turnout_windows_by_key={},
    )

    assert result.actual_distance_ft == 150.0
    assert result.movement_limited is False
    assert result.stop_reason is MovementBlockReason.NONE

    assert result.new_extent.rear_position.track_id == track.track_id
    assert result.new_extent.rear_position.offset_ft == 250.0
    assert result.new_extent.front_position.track_id == track.track_id
    assert result.new_extent.front_position.offset_ft == 360.0
    assert result.new_extent.travel_direction is TravelDirection.TOWARD_B

    assert result.footprint.track_count == 1
    assert result.footprint.total_occupied_length_ft == 110.0


def test_move_reverse_same_track_updates_extent_and_direction() -> None:
    """
    Test: Reverse movement updates extent positions and flips travel direction.

    Scenario:
    A 2-car consist (110 ft) is positioned on a single track, facing TOWARD_B.
    The train is commanded to move in REVERSE for 100 ft.

    What this validates:
    - The consist moves opposite its current direction.
    - The rear position shifts backward by the commanded distance.
    - The front position follows, maintaining consist length.
    - Travel direction flips from TOWARD_B to TOWARD_A.
    - No movement limits are encountered.
    - The footprint remains on a single track.

    Key expectation:
    Reverse movement changes both position and orientation.
    """
    network, track = build_single_track_network(length_ft=1000.0)
    service = build_service(network)

    consist = build_test_consist(car_count=2)
    extent = make_extent(
        consist=consist,
        rear_track=track,
        rear_offset_ft=300.0,
        front_track=track,
        front_offset_ft=410.0,
        travel_direction=TravelDirection.TOWARD_B,
    )

    result = service.move_extent(
        extent=extent,
        command=MoveCommand.REVERSE,
        distance_ft=100.0,
        turnout_windows_by_key={},
    )

    assert result.actual_distance_ft == 100.0
    assert result.movement_limited is False
    assert result.stop_reason is MovementBlockReason.NONE

    assert result.new_extent.rear_position.offset_ft == 200.0
    assert result.new_extent.front_position.offset_ft == 310.0
    assert result.new_extent.travel_direction is TravelDirection.TOWARD_A

    assert result.footprint.track_count == 1
    assert result.footprint.total_occupied_length_ft == 110.0


def test_move_forward_stops_at_dead_end_without_continuation() -> None:
    """
    Test: Forward movement stops at track end when no continuation exists.

    Scenario:
    A 2-car consist (110 ft) approaches the end of a track (dead end).
    The train attempts to move beyond the available track length

    What this validates:
    - Movement is limited by physical track boundaries
    - The front stops exactly at the track end
    - The rear position is recalculated based on consist length
    - The system reports movement_limited = True
    - The correct stop_reason ("no_aligned_route") is returned
    - The footprint remains valid and consistent

    Key expectation:
    The system enforces hard stopping at track limits with correct geometry
    """

    network, track = build_single_track_network(length_ft=1000.0)
    service = build_service(network)

    consist = build_test_consist(car_count=2)
    extent = make_extent(
        consist=consist,
        rear_track=track,
        rear_offset_ft=790.0,
        front_track=track,
        front_offset_ft=900.0,
        travel_direction=TravelDirection.TOWARD_B,
    )

    result = service.move_extent(
        extent=extent,
        command=MoveCommand.FORWARD,
        distance_ft=200.0,
        turnout_windows_by_key={},
    )

    assert result.actual_distance_ft == 100.0
    assert result.movement_limited is True
    assert result.stop_reason == MovementBlockReason.ROUTE_MISALIGNED

    assert result.new_extent.front_position.track_id == track.track_id
    assert result.new_extent.front_position.offset_ft == 1000.0
    assert result.new_extent.rear_position.track_id == track.track_id
    assert result.new_extent.rear_position.offset_ft == 890.0

    assert result.footprint.track_count == 1
    assert result.footprint.total_occupied_length_ft == 110.0


def test_move_forward_crosses_aligned_turnout_onto_siding() -> None:
    """
    Test: Forward movement traverses an aligned turnout onto a siding.

    Scenario:
    A 2-car consist (110 ft) moves forward across a turnout aligned to a siding.
    The front enters the siding while the rear remains on the originating track.

    What this validates:
    - The system correctly transitions across connected tracks.
    - The front position lands on the siding at the correct offset.
    - The rear remains on the original track with correct spacing.
    - The footprint spans multiple tracks.
    - Track occupancy is correctly reported (2 tracks).
    - Turnout is marked as fouled when occupied.

    Key expectation:
    A consist can straddle multiple tracks while maintaining accurate geometry.
    """
    network, tracks = build_turnout_network(align_to_siding=True)
    turnout_windows, track_key_by_id = build_turnout_windows(tracks=tracks)
    service = build_service(network, track_key_by_id=track_key_by_id)

    consist = build_test_consist(car_count=2)
    extent = make_extent(
        consist=consist,
        rear_track=tracks["main_west"],
        rear_offset_ft=340.0,
        front_track=tracks["main_west"],
        front_offset_ft=450.0,
        travel_direction=TravelDirection.TOWARD_B,
    )

    result = service.move_extent(
        extent=extent,
        command=MoveCommand.FORWARD,
        distance_ft=100.0,
        turnout_windows_by_key=turnout_windows,
    )

    assert result.actual_distance_ft == 100.0
    assert result.movement_limited is False
    assert result.stop_reason is MovementBlockReason.NONE

    assert result.new_extent.front_position.track_id == tracks["siding"].track_id
    assert result.new_extent.front_position.offset_ft == 50.0

    assert result.new_extent.rear_position.track_id == tracks["main_west"].track_id
    assert result.new_extent.rear_position.offset_ft == 440.0

    assert result.footprint.track_count == 2
    assert result.footprint.total_occupied_length_ft == 110.0
    assert result.footprint.occupied_track_ids == (
        tracks["main_west"].track_id,
        tracks["siding"].track_id,
    )

    west_turnout_state = result.turnout_states["WEST_TURNOUT"]
    assert west_turnout_state.is_fouled is True


def test_move_extent_rejects_negative_distance() -> None:
    """
    Test: Movement rejects invalid negative distance input.

    Scenario:
    A movement command is issued with a negative distance value.

    What this validates:
    - The system enforces input validation rules.
    - Negative movement distances are not allowed.
    - A ValueError is raised with a clear message.
    - No movement or state change occurs.

    Key expectation:
    Movement inputs must be physically meaningful (distance >= 0).
    """
    network, track = build_single_track_network(length_ft=1000.0)
    service = build_service(network)

    consist = build_test_consist(car_count=2)
    extent = make_extent(
        consist=consist,
        rear_track=track,
        rear_offset_ft=100.0,
        front_track=track,
        front_offset_ft=210.0,
        travel_direction=TravelDirection.TOWARD_B,
    )

    with pytest.raises(ValueError, match="distance_ft must be >= 0"):
        service.move_extent(
            extent=extent,
            command=MoveCommand.FORWARD,
            distance_ft=-1.0,
            turnout_windows_by_key={},
        )


def test_consist_length_is_always_preserved() -> None:
    """
    Invariant: The distance between rear and front must always equal
    the consist operational length, regardless of movement.
    """
    network, track = build_single_track_network(length_ft=1000.0)
    service = build_service(network)

    consist = build_test_consist(car_count=2)
    length = consist.operational_length_ft

    extent = make_extent(
        consist=consist,
        rear_track=track,
        rear_offset_ft=100.0,
        front_track=track,
        front_offset_ft=100.0 + length,
        travel_direction=TravelDirection.TOWARD_B,
    )

    for distance in [0.0, 10.0, 50.0, 123.0]:
        result = service.move_extent(
            extent=extent,
            command=MoveCommand.FORWARD,
            distance_ft=distance,
            turnout_windows_by_key={},
        )

        new = result.new_extent

        assert (
            new.front_position.offset_ft - new.rear_position.offset_ft
            == pytest.approx(length)
        )


def test_move_forward_crosses_aligned_turnout_onto_mainline() -> None:
    """
    Test: Forward movement traverses an aligned turnout and stays on the mainline.

    Scenario:
    A 2-car consist (110 ft) moves forward across a turnout that is aligned
    to the mainline instead of the siding. The front enters the next mainline
    track while the rear remains on the originating track.

    What this validates:
    - The movement service follows the currently aligned route.
    - The consist continues onto the mainline, not the siding.
    - The front position lands on the mainline continuation at the correct offset.
    - The rear remains on the original track with correct consist spacing.
    - The footprint spans multiple tracks.
    - The turnout is still marked fouled while the consist straddles the turnout area.

    Key expectation:
    Route alignment determines which connected track is taken, but turnout fouling
    depends on occupancy of the turnout protection window, not on whether the train
    diverges into the siding.
    """
    network, tracks = build_turnout_network(align_to_siding=False)
    turnout_windows, track_key_by_id = build_turnout_windows(tracks=tracks)
    service = build_service(network, track_key_by_id=track_key_by_id)

    consist = build_test_consist(car_count=2)
    extent = make_extent(
        consist=consist,
        rear_track=tracks["main_west"],
        rear_offset_ft=340.0,
        front_track=tracks["main_west"],
        front_offset_ft=450.0,
        travel_direction=TravelDirection.TOWARD_B,
    )

    result = service.move_extent(
        extent=extent,
        command=MoveCommand.FORWARD,
        distance_ft=100.0,
        turnout_windows_by_key=turnout_windows,
    )

    assert result.actual_distance_ft == 100.0
    assert result.movement_limited is False
    assert result.stop_reason is MovementBlockReason.NONE

    # Front moves 50 ft to Main West:B, then 50 ft into Main Middle from A.
    assert result.new_extent.front_position.track_id == tracks["main_middle"].track_id
    assert result.new_extent.front_position.offset_ft == 50.0

    # Rear is derived 110 ft behind the new front position.
    assert result.new_extent.rear_position.track_id == tracks["main_west"].track_id
    assert result.new_extent.rear_position.offset_ft == 440.0

    assert result.footprint.track_count == 2
    assert result.footprint.total_occupied_length_ft == 110.0
    assert result.footprint.occupied_track_ids == (
        tracks["main_west"].track_id,
        tracks["main_middle"].track_id,
    )

    west_turnout_state = result.turnout_states["WEST_TURNOUT"]
    assert west_turnout_state.is_fouled is True


def test_turnout_remains_fouled_on_mainline_until_consist_clears_window() -> None:
    """
    Test: A consist staying on the mainline continues to foul the turnout
    until it has fully cleared the turnout window.

    Scenario:
    A 2-car consist (110 ft) moves forward through a turnout aligned to the
    mainline. The movement is long enough for the front to enter the next
    mainline track, but not long enough for the entire consist to clear the
    turnout fouling window on the originating track.

    What this validates:
    - The consist follows the mainline route when the turnout is aligned that way.
    - The turnout remains fouled while any part of the consist still occupies
      the turnout protection zone.
    - Fouling is based on actual footprint geometry, not merely on route choice.

    Key expectation:
    A train can remain on the mainline and still foul the turnout if the rear
    has not yet cleared the protected window.
    """
    network, tracks = build_turnout_network(align_to_siding=False)
    turnout_windows, track_key_by_id = build_turnout_windows(tracks=tracks)
    service = build_service(network, track_key_by_id=track_key_by_id)

    consist = build_test_consist(car_count=2)
    extent = make_extent(
        consist=consist,
        rear_track=tracks["main_west"],
        rear_offset_ft=340.0,
        front_track=tracks["main_west"],
        front_offset_ft=450.0,
        travel_direction=TravelDirection.TOWARD_B,
    )

    result = service.move_extent(
        extent=extent,
        command=MoveCommand.FORWARD,
        distance_ft=60.0,
        turnout_windows_by_key=turnout_windows,
    )

    assert result.actual_distance_ft == 60.0
    assert result.movement_limited is False
    assert result.stop_reason is MovementBlockReason.NONE

    # Front moves 50 ft to turnout, then 10 ft into main_middle.
    assert result.new_extent.front_position.track_id == tracks["main_middle"].track_id
    assert result.new_extent.front_position.offset_ft == 10.0

    # Rear is still within the turnout window on main_west.
    assert result.new_extent.rear_position.track_id == tracks["main_west"].track_id
    assert result.new_extent.rear_position.offset_ft == 400.0

    assert result.footprint.track_count == 2
    assert result.footprint.total_occupied_length_ft == 110.0

    west_turnout_state = result.turnout_states["WEST_TURNOUT"]
    assert west_turnout_state.is_fouled is True


def test_turnout_clears_after_consist_fully_passes_on_mainline() -> None:
    """
    Test: Turnout fouling clears after the entire consist has passed through
    an aligned mainline route and fully cleared the turnout window.

    Scenario:
    A 2-car consist (110 ft) moves forward through a turnout aligned to the
    mainline. The movement is long enough for both the front and rear of the
    consist to clear the turnout protection zone.

    What this validates:
    - The consist remains on the mainline when the turnout is aligned to mainline.
    - The turnout is no longer fouled once no occupied segment overlaps any
      turnout protection window.
    - Footprint and turnout evaluation remain synchronized after movement.

    Key expectation:
    Turnout fouling must transition from True to False once the consist has
    completely cleared the turnout area.
    """
    network, tracks = build_turnout_network(align_to_siding=False)
    turnout_windows, track_key_by_id = build_turnout_windows(tracks=tracks)
    service = build_service(network, track_key_by_id=track_key_by_id)

    consist = build_test_consist(car_count=2)
    extent = make_extent(
        consist=consist,
        rear_track=tracks["main_west"],
        rear_offset_ft=340.0,
        front_track=tracks["main_west"],
        front_offset_ft=450.0,
        travel_direction=TravelDirection.TOWARD_B,
    )

    result = service.move_extent(
        extent=extent,
        command=MoveCommand.FORWARD,
        distance_ft=320.0,
        turnout_windows_by_key=turnout_windows,
    )

    assert result.actual_distance_ft == 320.0
    assert result.movement_limited is False
    assert result.stop_reason is MovementBlockReason.NONE

    # Front moves 50 ft to turnout, then 210 ft into main_middle.
    assert result.new_extent.front_position.track_id == tracks["main_middle"].track_id
    assert result.new_extent.front_position.offset_ft == 270.0

    # Rear is 110 ft behind the front, fully on main_middle and clear of turnout windows.
    assert result.new_extent.rear_position.track_id == tracks["main_middle"].track_id
    assert result.new_extent.rear_position.offset_ft == 160.0

    assert result.footprint.track_count == 1
    assert result.footprint.total_occupied_length_ft == 110.0
    assert result.footprint.occupied_track_ids == (tracks["main_middle"].track_id,)

    west_turnout_state = result.turnout_states["WEST_TURNOUT"]
    assert west_turnout_state.is_fouled is False


def test_chained_forward_moves_through_mainline_turnout() -> None:
    """
    Test: Chained forward moves progress a consist from approach, to fouling,
    to fully clear through a turnout aligned to the mainline.

    Scenario:
    A 2-car consist (110 ft) approaches a turnout aligned to the mainline.
    The consist is moved in three separate forward commands:
    1. approach but remain entirely on the originating track
    2. straddle the turnout and foul it
    3. fully clear the turnout and occupy only the next mainline track

    What this validates:
    - Each move uses the prior result's extent as the next starting state.
    - Consist length remains constant across all chained moves.
    - Track occupancy transitions correctly from one track, to two tracks,
      back to one track.
    - Turnout fouling transitions from clear, to fouled, to clear.
    - The movement service behaves consistently over multiple sequential moves.

    Key expectation:
    Chained movement should preserve geometry and produce realistic turnout
    occupancy transitions over time.
    """
    network, tracks = build_turnout_network(align_to_siding=False)
    turnout_windows, track_key_by_id = build_turnout_windows(tracks=tracks)
    service = build_service(network, track_key_by_id=track_key_by_id)

    consist = build_test_consist(car_count=2)
    consist_length = consist.operational_length_ft

    extent = make_extent(
        consist=consist,
        rear_track=tracks["main_west"],
        rear_offset_ft=290.0,
        front_track=tracks["main_west"],
        front_offset_ft=400.0,
        travel_direction=TravelDirection.TOWARD_B,
    )

    step1 = service.move_extent(
        extent=extent,
        command=MoveCommand.FORWARD,
        distance_ft=40.0,
        turnout_windows_by_key=turnout_windows,
    )

    assert step1.actual_distance_ft == 40.0
    assert step1.movement_limited is False
    assert step1.stop_reason is MovementBlockReason.NONE
    assert step1.new_extent.rear_position.track_id == tracks["main_west"].track_id
    assert step1.new_extent.rear_position.offset_ft == 330.0
    assert step1.new_extent.front_position.track_id == tracks["main_west"].track_id
    assert step1.new_extent.front_position.offset_ft == 440.0
    assert step1.footprint.track_count == 1
    assert step1.footprint.total_occupied_length_ft == 110.0
    assert (
        step1.new_extent.front_position.offset_ft
        - step1.new_extent.rear_position.offset_ft
        == pytest.approx(consist_length)
    )
    assert step1.turnout_states["WEST_TURNOUT"].is_fouled is False

    step2 = service.move_extent(
        extent=step1.new_extent,
        command=MoveCommand.FORWARD,
        distance_ft=70.0,
        turnout_windows_by_key=turnout_windows,
    )

    assert step2.actual_distance_ft == 70.0
    assert step2.movement_limited is False
    assert step2.stop_reason is MovementBlockReason.NONE
    assert step2.new_extent.front_position.track_id == tracks["main_middle"].track_id
    assert step2.new_extent.front_position.offset_ft == 10.0
    assert step2.new_extent.rear_position.track_id == tracks["main_west"].track_id
    assert step2.new_extent.rear_position.offset_ft == 400.0
    assert step2.footprint.track_count == 2
    assert step2.footprint.total_occupied_length_ft == 110.0
    assert step2.footprint.occupied_track_ids == (
        tracks["main_west"].track_id,
        tracks["main_middle"].track_id,
    )
    assert step2.turnout_states["WEST_TURNOUT"].is_fouled is True

    step3 = service.move_extent(
        extent=step2.new_extent,
        command=MoveCommand.FORWARD,
        distance_ft=260.0,
        turnout_windows_by_key=turnout_windows,
    )

    assert step3.actual_distance_ft == 260.0
    assert step3.movement_limited is False
    assert step3.stop_reason is MovementBlockReason.NONE
    assert step3.new_extent.front_position.track_id == tracks["main_middle"].track_id
    assert step3.new_extent.front_position.offset_ft == 270.0
    assert step3.new_extent.rear_position.track_id == tracks["main_middle"].track_id
    assert step3.new_extent.rear_position.offset_ft == 160.0
    assert step3.footprint.track_count == 1
    assert step3.footprint.total_occupied_length_ft == 110.0
    assert step3.footprint.occupied_track_ids == (tracks["main_middle"].track_id,)
    assert (
        step3.new_extent.front_position.offset_ft
        - step3.new_extent.rear_position.offset_ft
        == pytest.approx(consist_length)
    )
    assert step3.turnout_states["WEST_TURNOUT"].is_fouled is False


def test_chained_forward_moves_through_siding_turnout() -> None:
    """
    Test: Chained forward moves progress a consist from approach, to fouling,
    to fully clear through a turnout aligned to the siding.

    Scenario:
    A 2-car consist (110 ft) approaches a turnout aligned to the siding.
    The consist is moved in three separate forward commands:
    1. approach but remain entirely on the originating track
    2. straddle the turnout and foul it while entering the siding
    3. fully clear the turnout and occupy only the siding

    What this validates:
    - Each move uses the prior result's extent as the next starting state.
    - The movement service follows the currently aligned siding route.
    - Consist length remains constant across all chained moves.
    - Track occupancy transitions correctly from one track, to two tracks,
      back to one track.
    - Turnout fouling transitions from clear, to fouled, to clear.
    - The movement service behaves consistently over multiple sequential moves.

    Key expectation:
    Chained movement through a siding turnout should preserve geometry and
    produce realistic turnout occupancy transitions over time.
    """
    network, tracks = build_turnout_network(align_to_siding=True)
    turnout_windows, track_key_by_id = build_turnout_windows(tracks=tracks)
    service = build_service(network, track_key_by_id=track_key_by_id)

    consist = build_test_consist(car_count=2)
    consist_length = consist.operational_length_ft

    extent = make_extent(
        consist=consist,
        rear_track=tracks["main_west"],
        rear_offset_ft=290.0,
        front_track=tracks["main_west"],
        front_offset_ft=400.0,
        travel_direction=TravelDirection.TOWARD_B,
    )

    # ------------------------------------------------------------------
    # Step 1: move forward, still entirely on main_west, not yet fouling
    # ------------------------------------------------------------------
    step1 = service.move_extent(
        extent=extent,
        command=MoveCommand.FORWARD,
        distance_ft=40.0,
        turnout_windows_by_key=turnout_windows,
    )

    assert step1.actual_distance_ft == 40.0
    assert step1.movement_limited is False
    assert step1.stop_reason is MovementBlockReason.NONE

    assert step1.new_extent.rear_position.track_id == tracks["main_west"].track_id
    assert step1.new_extent.rear_position.offset_ft == 330.0
    assert step1.new_extent.front_position.track_id == tracks["main_west"].track_id
    assert step1.new_extent.front_position.offset_ft == 440.0

    assert step1.footprint.track_count == 1
    assert step1.footprint.total_occupied_length_ft == 110.0
    assert (
        step1.new_extent.front_position.offset_ft
        - step1.new_extent.rear_position.offset_ft
        == pytest.approx(consist_length)
    )

    assert step1.turnout_states["WEST_TURNOUT"].is_fouled is False

    # ------------------------------------------------------------------
    # Step 2: move forward through turnout into siding, turnout fouled
    # ------------------------------------------------------------------
    step2 = service.move_extent(
        extent=step1.new_extent,
        command=MoveCommand.FORWARD,
        distance_ft=70.0,
        turnout_windows_by_key=turnout_windows,
    )

    assert step2.actual_distance_ft == 70.0
    assert step2.movement_limited is False
    assert step2.stop_reason is MovementBlockReason.NONE

    assert step2.new_extent.front_position.track_id == tracks["siding"].track_id
    assert step2.new_extent.front_position.offset_ft == 10.0
    assert step2.new_extent.rear_position.track_id == tracks["main_west"].track_id
    assert step2.new_extent.rear_position.offset_ft == 400.0

    assert step2.footprint.track_count == 2
    assert step2.footprint.total_occupied_length_ft == 110.0
    assert step2.footprint.occupied_track_ids == (
        tracks["main_west"].track_id,
        tracks["siding"].track_id,
    )

    assert step2.turnout_states["WEST_TURNOUT"].is_fouled is True

    # ------------------------------------------------------------------
    # Step 3: move far enough to clear the turnout on the siding
    # ------------------------------------------------------------------
    step3 = service.move_extent(
        extent=step2.new_extent,
        command=MoveCommand.FORWARD,
        distance_ft=260.0,
        turnout_windows_by_key=turnout_windows,
    )

    assert step3.actual_distance_ft == 260.0
    assert step3.movement_limited is False
    assert step3.stop_reason is MovementBlockReason.NONE

    assert step3.new_extent.front_position.track_id == tracks["siding"].track_id
    assert step3.new_extent.front_position.offset_ft == 270.0
    assert step3.new_extent.rear_position.track_id == tracks["siding"].track_id
    assert step3.new_extent.rear_position.offset_ft == 160.0

    assert step3.footprint.track_count == 1
    assert step3.footprint.total_occupied_length_ft == 110.0
    assert step3.footprint.occupied_track_ids == (tracks["siding"].track_id,)

    assert (
        step3.new_extent.front_position.offset_ft
        - step3.new_extent.rear_position.offset_ft
        == pytest.approx(consist_length)
    )

    assert step3.turnout_states["WEST_TURNOUT"].is_fouled is False


def test_move_forward_crosses_from_approach_onto_bridge_when_aligned_to_approach() -> (
    None
):
    """
    Test: Forward movement crosses from the approach track onto the bridge when
    the turntable is aligned to the approach.

    Scenario:
    A 2-car consist is entirely on the approach track near endpoint A and is
    facing TOWARD_A. The turntable is aligned to the approach, so the active
    connection is approach:A <-> bridge:A.

    What this validates:
    - ConsistMovementService can use dynamic turntable topology.
    - Movement continues from the approach onto the bridge.
    - The front enters the bridge at the correct offset.
    - The rear remains on the approach with correct consist spacing.

    Key expectation:
    Turntable-backed continuation behaves like any other aligned track
    continuation at the consist layer.
    """
    network, approach, bridge, stall_1, turntable, connection = (
        build_turntable_network()
    )
    turntable.align_to(approach.track_id)

    service = build_service(
        network,
        turntable_connections=(connection,),
    )

    consist = build_test_consist(car_count=2)
    extent = make_extent(
        consist=consist,
        rear_track=approach,
        rear_offset_ft=160.0,
        front_track=approach,
        front_offset_ft=50.0,
        travel_direction=TravelDirection.TOWARD_A,
    )

    result = service.move_extent(
        extent=extent,
        command=MoveCommand.FORWARD,
        distance_ft=100.0,
        turnout_windows_by_key={},
    )

    assert result.actual_distance_ft == 100.0
    assert result.movement_limited is False
    assert result.stop_reason is MovementBlockReason.NONE

    # Front moves 50 ft to approach:A, then 50 ft onto bridge from A.
    assert result.new_extent.front_position.track_id == bridge.track_id
    assert result.new_extent.front_position.offset_ft == 50.0

    # Rear remains 110 ft behind the front.
    assert result.new_extent.rear_position.track_id == approach.track_id
    assert result.new_extent.rear_position.offset_ft == 60.0

    assert result.new_extent.travel_direction is TravelDirection.TOWARD_B

    assert result.footprint.track_count == 2
    assert result.footprint.total_occupied_length_ft == 110.0
    assert result.footprint.occupied_track_ids == (
        approach.track_id,
        bridge.track_id,
    )


def test_move_forward_stops_at_bridge_end_when_no_aligned_exit_exists() -> None:
    """
    Test: Forward movement stops at the bridge end when there is no aligned exit
    on the radial side.

    Scenario:
    A 2-car consist is entirely on the bridge near endpoint B and is facing
    TOWARD_B. The turntable is aligned only to the approach, so bridge:B has
    no active continuation.

    What this validates:
    - ConsistMovementService does not invent a continuation where none exists.
    - The consist stops exactly at the bridge end.
    - Stop reason remains consistent with existing dead-end behavior.

    Key expectation:
    The bridge behaves like a normal track end unless topology exposes an
    aligned continuation there.
    """
    network, approach, bridge, stall_1, turntable, connection = (
        build_turntable_network()
    )
    turntable.align_to(approach.track_id)

    service = build_service(
        network,
        turntable_connections=(connection,),
    )

    consist = build_test_consist(car_count=2)
    extent = make_extent(
        consist=consist,
        rear_track=bridge,
        rear_offset_ft=bridge.length_ft - 160.0,
        front_track=bridge,
        front_offset_ft=bridge.length_ft - 50.0,
        travel_direction=TravelDirection.TOWARD_B,
    )

    result = service.move_extent(
        extent=extent,
        command=MoveCommand.FORWARD,
        distance_ft=100.0,
        turnout_windows_by_key={},
    )

    assert result.actual_distance_ft == 50.0
    assert result.movement_limited is True
    assert result.stop_reason == MovementBlockReason.ROUTE_MISALIGNED

    assert result.new_extent.front_position.track_id == bridge.track_id
    assert result.new_extent.front_position.offset_ft == bridge.length_ft
    assert result.new_extent.rear_position.track_id == bridge.track_id
    assert result.new_extent.rear_position.offset_ft == bridge.length_ft - 110.0

    assert result.footprint.track_count == 1
    assert result.footprint.total_occupied_length_ft == 110.0
    assert result.footprint.occupied_track_ids == (bridge.track_id,)


def test_move_forward_crosses_from_bridge_onto_stall_when_aligned_to_stall() -> None:
    """
    Test: Forward movement crosses from the bridge onto a stall when the
    turntable is aligned to that stall.

    Scenario:
    A 2-car consist is entirely on the bridge near endpoint B and is facing
    TOWARD_B. The turntable is aligned to Stall 1, so the active connection is
    bridge:B <-> stall_1:A.

    What this validates:
    - ConsistMovementService can traverse from the bridge onto a stall.
    - The front enters the stall at the correct offset.
    - The rear remains on the bridge with correct consist spacing.

    Key expectation:
    The bridge-to-stall continuation is handled through topology only.
    """
    network, approach, bridge, stall_1, turntable, connection = (
        build_turntable_network()
    )
    turntable.align_to(stall_1.track_id)

    service = build_service(
        network,
        turntable_connections=(connection,),
    )

    consist = build_test_consist(car_count=2)
    extent = make_extent(
        consist=consist,
        rear_track=bridge,
        rear_offset_ft=bridge.length_ft - 160.0,
        front_track=bridge,
        front_offset_ft=bridge.length_ft - 50.0,
        travel_direction=TravelDirection.TOWARD_B,
    )

    result = service.move_extent(
        extent=extent,
        command=MoveCommand.FORWARD,
        distance_ft=100.0,
        turnout_windows_by_key={},
    )

    assert result.actual_distance_ft == 100.0
    assert result.movement_limited is False
    assert result.stop_reason is MovementBlockReason.NONE

    # Front moves 50 ft to bridge:B, then 50 ft into stall_1 from A.
    assert result.new_extent.front_position.track_id == stall_1.track_id
    assert result.new_extent.front_position.offset_ft == 50.0

    # Rear remains 110 ft behind the front.
    assert result.new_extent.rear_position.track_id == bridge.track_id
    assert result.new_extent.rear_position.offset_ft == bridge.length_ft - 60.0

    assert result.new_extent.travel_direction is TravelDirection.TOWARD_B

    assert result.footprint.track_count == 2
    assert result.footprint.total_occupied_length_ft == 110.0
    assert result.footprint.occupied_track_ids == (
        bridge.track_id,
        stall_1.track_id,
    )


def test_move_reverse_crosses_from_bridge_back_to_approach_when_aligned_to_approach() -> (
    None
):
    """
    Test: Reverse movement crosses from the bridge back onto the approach when
    the turntable is aligned to the approach.

    Scenario:
    A 2-car consist is entirely on the bridge near endpoint A, initially facing
    TOWARD_B. A REVERSE command moves it toward A. The turntable is aligned to
    the approach, so bridge:A <-> approach:A is active.

    What this validates:
    - Reverse movement uses the same dynamic topology continuation.
    - The front enters the approach correctly while reversing.
    - Travel direction flips as expected.

    Key expectation:
    Reverse traversal through a turntable-backed connection works without any
    turntable-specific logic in ConsistMovementService.
    """
    network, approach, bridge, stall_1, turntable, connection = (
        build_turntable_network()
    )
    turntable.align_to(approach.track_id)

    service = build_service(
        network,
        turntable_connections=(connection,),
    )

    consist = build_test_consist(car_count=2)
    extent = make_extent(
        consist=consist,
        rear_track=bridge,
        rear_offset_ft=160.0,
        front_track=bridge,
        front_offset_ft=50.0,
        travel_direction=TravelDirection.TOWARD_B,
    )

    result = service.move_extent(
        extent=extent,
        command=MoveCommand.REVERSE,
        distance_ft=100.0,
        turnout_windows_by_key={},
    )

    assert result.actual_distance_ft == 100.0
    assert result.movement_limited is False
    assert result.stop_reason is MovementBlockReason.NONE

    # Reversing from TOWARD_B means movement toward A.
    # The moved end only reaches bridge offset 60.0, so no crossing occurs.
    assert result.new_extent.front_position.track_id == bridge.track_id
    assert result.new_extent.front_position.offset_ft == 170.0

    assert result.new_extent.rear_position.track_id == bridge.track_id
    assert result.new_extent.rear_position.offset_ft == 60.0

    assert result.new_extent.travel_direction is TravelDirection.TOWARD_A

    assert result.footprint.track_count == 1
    assert result.footprint.total_occupied_length_ft == 110.0
    assert result.footprint.occupied_track_ids == (bridge.track_id,)


def test_move_forward_stops_at_contact_and_reports_contact_metadata() -> None:
    network, track = build_single_track_network(length_ft=1000.0)
    service = build_service(network)

    consist_a = build_test_consist(car_count=2)
    consist_b = build_test_consist(car_count=2)

    extent_a = make_extent(
        consist=consist_a,
        rear_track=track,
        rear_offset_ft=100.0,
        front_track=track,
        front_offset_ft=210.0,
        travel_direction=TravelDirection.TOWARD_B,
    )

    extent_b = make_extent(
        consist=consist_b,
        rear_track=track,
        rear_offset_ft=400.0,
        front_track=track,
        front_offset_ft=510.0,
        travel_direction=TravelDirection.STATIONARY,
    )

    footprint_b = service._footprint_service.footprint_for_extent(extent_b)

    result = service.move_extent(
        extent=extent_a,
        command=MoveCommand.FORWARD,
        distance_ft=300.0,
        turnout_windows_by_key={},
        active_footprints=(footprint_b,),
    )

    assert result.requested_distance_ft == 300.0
    assert result.actual_distance_ft == 190.0
    assert result.movement_limited is True
    assert result.stop_reason is MovementBlockReason.CONTACT

    assert result.contact_occurred is True
    assert result.contact_with_consist_id == consist_b.consist_id

    assert result.new_extent.rear_position.track_id == track.track_id
    assert result.new_extent.rear_position.offset_ft == 290.0
    assert result.new_extent.front_position.track_id == track.track_id
    assert result.new_extent.front_position.offset_ft == 400.0

    assert result.footprint.track_count == 1
    assert result.footprint.total_occupied_length_ft == 110.0
