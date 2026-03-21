from __future__ import annotations

from uuid import uuid4

import pytest

from railroad_sim.domain.consist import Consist
from railroad_sim.domain.enums import (
    JunctionType,
    TravelDirection,
)
from railroad_sim.domain.junction import Junction, JunctionRoute, TrackEndpoint
from railroad_sim.domain.network.footprint_service import FootprintService
from railroad_sim.domain.network.position_types import (
    ConsistExtent,
    ExtentValidationReason,
    NetworkPosition,
)
from railroad_sim.domain.network.rail_network import RailNetwork
from railroad_sim.domain.network.topology_movement_service import (
    TopologyMovementService,
)
from railroad_sim.domain.rolling_stock import RollingStock
from railroad_sim.domain.track import Track
from tests.support.track_builders import make_track


@pytest.fixture(autouse=True)
def reset_consist_registry() -> None:
    Consist._reset_registry_for_tests()


def ep_a(track: Track) -> TrackEndpoint:
    from railroad_sim.domain.enums import TrackEnd

    return TrackEndpoint(track=track, end=TrackEnd.A)


def ep_b(track: Track) -> TrackEndpoint:
    from railroad_sim.domain.enums import TrackEnd

    return TrackEndpoint(track=track, end=TrackEnd.B)


def make_consist() -> Consist:
    """
    Build a minimal valid one-car consist for footprint tests.
    """
    car = RollingStock(reporting_mark="TST", road_number="1001")
    return Consist(anchor=car)


def build_single_track_network() -> tuple[RailNetwork, Track]:
    network = RailNetwork(name="Single Track Network")
    track_a = make_track("Track A")
    network.add_track(track_a)
    return network, track_a


def build_linear_abc_network() -> tuple[
    RailNetwork,
    Track,
    Track,
    Track,
    Junction,
    Junction,
    JunctionRoute,
    JunctionRoute,
]:
    network = RailNetwork(name="ABC Network")

    track_a = make_track("Track A")
    track_b = make_track("Track B")
    track_c = make_track("Track C")

    for track in (track_a, track_b, track_c):
        network.add_track(track)

    route_ab = JunctionRoute(
        from_endpoint=ep_b(track_a),
        to_endpoint=ep_a(track_b),
    )
    route_bc = JunctionRoute(
        from_endpoint=ep_b(track_b),
        to_endpoint=ep_a(track_c),
    )

    junction_ab = Junction(
        name="J_AB",
        junction_type=JunctionType.CONNECTION,
        endpoints={ep_b(track_a), ep_a(track_b)},
        routes={route_ab},
        aligned_routes={route_ab},
    )

    junction_bc = Junction(
        name="J_BC",
        junction_type=JunctionType.CONNECTION,
        endpoints={ep_b(track_b), ep_a(track_c)},
        routes={route_bc},
        aligned_routes={route_bc},
    )

    network.add_junction(junction_ab)
    network.add_junction(junction_bc)

    return (
        network,
        track_a,
        track_b,
        track_c,
        junction_ab,
        junction_bc,
        route_ab,
        route_bc,
    )


def build_disconnected_network() -> tuple[RailNetwork, Track, Track]:
    network = RailNetwork(name="Disconnected Network")
    track_a = make_track("Track A")
    track_z = make_track("Track Z")

    network.add_track(track_a)
    network.add_track(track_z)

    return network, track_a, track_z


def test_validate_extent_returns_valid_for_same_track_extent() -> None:
    network, track_a = build_single_track_network()
    service = FootprintService(network)
    consist = make_consist()

    extent = ConsistExtent(
        consist=consist,
        rear_position=NetworkPosition(track_id=track_a.track_id, offset_ft=200.0),
        front_position=NetworkPosition(track_id=track_a.track_id, offset_ft=380.0),
        travel_direction=TravelDirection.STATIONARY,
    )

    result = service.validate_extent(extent)

    assert result.is_valid is True
    assert result.reason is ExtentValidationReason.VALID
    assert result.path_track_ids == (track_a.track_id,)


def test_validate_extent_returns_invalid_for_same_track_reversed_offsets() -> None:
    network, track_a = build_single_track_network()
    service = FootprintService(network)
    consist = make_consist()

    extent = ConsistExtent(
        consist=consist,
        rear_position=NetworkPosition(track_id=track_a.track_id, offset_ft=700.0),
        front_position=NetworkPosition(track_id=track_a.track_id, offset_ft=300.0),
        travel_direction=TravelDirection.STATIONARY,
    )

    result = service.validate_extent(extent)

    assert result.is_valid is False
    assert result.reason is ExtentValidationReason.SAME_TRACK_OFFSETS_INVALID
    assert result.path_track_ids == ()


def test_validate_extent_returns_invalid_for_unknown_rear_track() -> None:
    network, track_a = build_single_track_network()
    service = FootprintService(network)
    consist = make_consist()

    extent = ConsistExtent(
        consist=consist,
        rear_position=NetworkPosition(track_id=uuid4(), offset_ft=100.0),
        front_position=NetworkPosition(track_id=track_a.track_id, offset_ft=300.0),
        travel_direction=TravelDirection.STATIONARY,
    )

    result = service.validate_extent(extent)

    assert result.is_valid is False
    assert result.reason is ExtentValidationReason.UNKNOWN_REAR_TRACK
    assert result.path_track_ids == ()


def test_validate_extent_returns_invalid_for_unknown_front_track() -> None:
    network, track_a = build_single_track_network()
    service = FootprintService(network)
    consist = make_consist()

    extent = ConsistExtent(
        consist=consist,
        rear_position=NetworkPosition(track_id=track_a.track_id, offset_ft=100.0),
        front_position=NetworkPosition(track_id=uuid4(), offset_ft=300.0),
        travel_direction=TravelDirection.STATIONARY,
    )

    result = service.validate_extent(extent)

    assert result.is_valid is False
    assert result.reason is ExtentValidationReason.UNKNOWN_FRONT_TRACK
    assert result.path_track_ids == ()


def test_validate_extent_returns_invalid_for_rear_offset_out_of_range() -> None:
    network, track_a = build_single_track_network()
    service = FootprintService(network)
    consist = make_consist()

    extent = ConsistExtent(
        consist=consist,
        rear_position=NetworkPosition(track_id=track_a.track_id, offset_ft=1200.0),
        front_position=NetworkPosition(track_id=track_a.track_id, offset_ft=1300.0),
        travel_direction=TravelDirection.STATIONARY,
    )

    result = service.validate_extent(extent)

    assert result.is_valid is False
    assert result.reason is ExtentValidationReason.REAR_OFFSET_OUT_OF_RANGE
    assert result.path_track_ids == ()


def test_validate_extent_returns_invalid_for_front_offset_out_of_range() -> None:
    network, track_a = build_single_track_network()
    service = FootprintService(network)
    consist = make_consist()

    extent = ConsistExtent(
        consist=consist,
        rear_position=NetworkPosition(track_id=track_a.track_id, offset_ft=100.0),
        front_position=NetworkPosition(track_id=track_a.track_id, offset_ft=1300.0),
        travel_direction=TravelDirection.STATIONARY,
    )

    result = service.validate_extent(extent)

    assert result.is_valid is False
    assert result.reason is ExtentValidationReason.FRONT_OFFSET_OUT_OF_RANGE
    assert result.path_track_ids == ()


def test_validate_extent_returns_valid_for_multi_track_extent() -> None:
    network, track_a, track_b, track_c, *_ = build_linear_abc_network()
    service = FootprintService(network)
    consist = make_consist()

    extent = ConsistExtent(
        consist=consist,
        rear_position=NetworkPosition(track_id=track_a.track_id, offset_ft=400.0),
        front_position=NetworkPosition(track_id=track_c.track_id, offset_ft=250.0),
        travel_direction=TravelDirection.TOWARD_B,
    )

    result = service.validate_extent(extent)

    assert result.is_valid is True
    assert result.reason is ExtentValidationReason.VALID
    assert result.path_track_ids == (
        track_a.track_id,
        track_b.track_id,
        track_c.track_id,
    )


def test_validate_extent_returns_invalid_when_no_path_exists() -> None:
    network, track_a, track_z = build_disconnected_network()
    service = FootprintService(network)
    consist = make_consist()

    extent = ConsistExtent(
        consist=consist,
        rear_position=NetworkPosition(track_id=track_a.track_id, offset_ft=100.0),
        front_position=NetworkPosition(track_id=track_z.track_id, offset_ft=250.0),
        travel_direction=TravelDirection.TOWARD_B,
    )

    result = service.validate_extent(extent)

    assert result.is_valid is False
    assert result.reason is ExtentValidationReason.NO_PATH
    assert result.path_track_ids == ()


def test_footprint_for_extent_returns_single_segment_for_same_track_extent() -> None:
    network, track_a = build_single_track_network()
    service = FootprintService(network)
    consist = make_consist()

    extent = ConsistExtent(
        consist=consist,
        rear_position=NetworkPosition(track_id=track_a.track_id, offset_ft=200.0),
        front_position=NetworkPosition(track_id=track_a.track_id, offset_ft=380.0),
        travel_direction=TravelDirection.STATIONARY,
    )

    footprint = service.footprint_for_extent(extent)

    assert footprint.consist is consist
    assert footprint.track_count == 1
    assert footprint.occupied_track_ids == (track_a.track_id,)
    assert footprint.total_occupied_length_ft == pytest.approx(180.0)

    segment = footprint.segments[0]
    assert segment.track_id == track_a.track_id
    assert segment.rear_offset_ft == pytest.approx(200.0)
    assert segment.front_offset_ft == pytest.approx(380.0)
    assert segment.length_ft == pytest.approx(180.0)


def test_footprint_for_extent_returns_multi_track_segments() -> None:
    network, track_a, track_b, track_c, *_ = build_linear_abc_network()
    service = FootprintService(network)
    consist = make_consist()

    extent = ConsistExtent(
        consist=consist,
        rear_position=NetworkPosition(track_id=track_a.track_id, offset_ft=400.0),
        front_position=NetworkPosition(track_id=track_c.track_id, offset_ft=250.0),
        travel_direction=TravelDirection.TOWARD_B,
    )

    footprint = service.footprint_for_extent(extent)

    assert footprint.consist is consist
    assert footprint.track_count == 3
    assert footprint.occupied_track_ids == (
        track_a.track_id,
        track_b.track_id,
        track_c.track_id,
    )

    seg_a, seg_b, seg_c = footprint.segments

    assert seg_a.track_id == track_a.track_id
    assert seg_a.rear_offset_ft == pytest.approx(400.0)
    assert seg_a.front_offset_ft == pytest.approx(track_a.length_ft)

    assert seg_b.track_id == track_b.track_id
    assert seg_b.rear_offset_ft == pytest.approx(0.0)
    assert seg_b.front_offset_ft == pytest.approx(track_b.length_ft)

    assert seg_c.track_id == track_c.track_id
    assert seg_c.rear_offset_ft == pytest.approx(0.0)
    assert seg_c.front_offset_ft == pytest.approx(250.0)

    assert footprint.total_occupied_length_ft == pytest.approx(600.0 + 1000.0 + 250.0)


def test_footprint_for_extent_raises_for_invalid_extent() -> None:
    network, track_a = build_single_track_network()
    service = FootprintService(network)
    consist = make_consist()

    extent = ConsistExtent(
        consist=consist,
        rear_position=NetworkPosition(track_id=track_a.track_id, offset_ft=800.0),
        front_position=NetworkPosition(track_id=track_a.track_id, offset_ft=300.0),
        travel_direction=TravelDirection.STATIONARY,
    )

    with pytest.raises(ValueError, match="Invalid consist extent"):
        service.footprint_for_extent(extent)


def test_occupied_track_ids_for_extent_returns_same_track_id_for_same_track_extent() -> (
    None
):
    network, track_a = build_single_track_network()
    service = FootprintService(network)
    consist = make_consist()

    extent = ConsistExtent(
        consist=consist,
        rear_position=NetworkPosition(track_id=track_a.track_id, offset_ft=100.0),
        front_position=NetworkPosition(track_id=track_a.track_id, offset_ft=200.0),
        travel_direction=TravelDirection.STATIONARY,
    )

    track_ids = service.occupied_track_ids_for_extent(extent)

    assert track_ids == (track_a.track_id,)


def test_occupied_track_ids_for_extent_returns_ordered_multi_track_path() -> None:
    network, track_a, track_b, track_c, *_ = build_linear_abc_network()
    service = FootprintService(network)
    consist = make_consist()

    extent = ConsistExtent(
        consist=consist,
        rear_position=NetworkPosition(track_id=track_a.track_id, offset_ft=50.0),
        front_position=NetworkPosition(track_id=track_c.track_id, offset_ft=500.0),
        travel_direction=TravelDirection.TOWARD_B,
    )

    track_ids = service.occupied_track_ids_for_extent(extent)

    assert track_ids == (
        track_a.track_id,
        track_b.track_id,
        track_c.track_id,
    )


def test_occupied_track_ids_for_extent_raises_for_invalid_extent() -> None:
    network, track_a = build_single_track_network()
    service = FootprintService(network)
    consist = make_consist()

    extent = ConsistExtent(
        consist=consist,
        rear_position=NetworkPosition(track_id=track_a.track_id, offset_ft=700.0),
        front_position=NetworkPosition(track_id=track_a.track_id, offset_ft=300.0),
        travel_direction=TravelDirection.STATIONARY,
    )

    with pytest.raises(ValueError, match="Invalid consist extent"):
        service.occupied_track_ids_for_extent(extent)


def test_footprint_for_extent_counts_remaining_bridge_length_when_spanning_bridge_to_stall() -> (
    None
):
    from railroad_sim.domain.enums import TravelDirection
    from railroad_sim.domain.network.position_types import (
        ConsistExtent,
        NetworkPosition,
    )
    from railroad_sim.domain.yard.turntable import Turntable
    from railroad_sim.domain.yard.turntable_connection import TurntableConnection

    network = RailNetwork(name="Turntable Footprint Network")

    bridge = make_track("Bridge", length_ft=150.0)
    stall_1 = make_track("Stall 1", length_ft=200.0)

    network.add_track(bridge)
    network.add_track(stall_1)

    turntable = Turntable(
        name="TT",
        bridge_length_ft=150.0,
        bridge_track_id=bridge.track_id,
        approach_track_id=uuid4(),  # unused in this test
        stall_track_ids=(stall_1.track_id,),
    )
    turntable.align_to(stall_1.track_id)

    connection = TurntableConnection(
        turntable=turntable,
        bridge_track=bridge,
        connected_tracks_by_id={
            stall_1.track_id: stall_1,
        },
    )

    service = FootprintService(
        network=network,
        movement_service=TopologyMovementService(
            network,
            turntable_connections=(connection,),
        ),
    )
    consist = make_consist()

    extent = ConsistExtent(
        consist=consist,
        rear_position=NetworkPosition(track_id=bridge.track_id, offset_ft=50.0),
        front_position=NetworkPosition(track_id=stall_1.track_id, offset_ft=28.0),
        travel_direction=TravelDirection.TOWARD_B,
    )

    footprint = service.footprint_for_extent(extent)

    assert footprint.track_count == 2
    assert footprint.occupied_track_ids == (bridge.track_id, stall_1.track_id)

    seg_bridge, seg_stall = footprint.segments

    assert seg_bridge.rear_offset_ft == pytest.approx(50.0)
    assert seg_bridge.front_offset_ft == pytest.approx(150.0)

    assert seg_stall.rear_offset_ft == pytest.approx(0.0)
    assert seg_stall.front_offset_ft == pytest.approx(28.0)

    assert footprint.total_occupied_length_ft == pytest.approx(128.0)
