from __future__ import annotations

from uuid import uuid4

import pytest

from railroad_sim.domain.enums import (
    TrackCondition,
    TrackEnd,
)
from railroad_sim.domain.junction import Junction, JunctionRoute
from railroad_sim.domain.network.boundary_connection import BoundaryConnection
from railroad_sim.domain.network.movement_enums import (
    MovementBlockReason,
    MovementOptionKind,
)
from railroad_sim.domain.network.movement_service import MovementService
from railroad_sim.domain.network.rail_network import RailNetwork
from railroad_sim.domain.track import Track
from tests.support.junction_builders import (
    build_linear_connection_pair,
    make_connection_junction,
)
from tests.support.track_builders import endpoint_a, endpoint_b, make_track

# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


def build_simple_ab_network() -> tuple[
    RailNetwork, Track, Track, Junction, JunctionRoute
]:
    """
    A:B <-> B:A
    """
    network = RailNetwork(name="AB Network")

    track_a = make_track("Track A")
    track_b = make_track("Track B")

    network.add_track(track_a)
    network.add_track(track_b)

    junction, route_ab = make_connection_junction(
        name="J1",
        left_track=track_a,
        left_end=TrackEnd.B,
        right_track=track_b,
        right_end=TrackEnd.A,
        aligned=True,
    )

    network.add_junction(junction)

    return network, track_a, track_b, junction, route_ab


def build_simple_abc_network(
    middle_condition: TrackCondition = TrackCondition.CLEAR,
    align_ab: bool = True,
    align_bc: bool = True,
) -> tuple[
    RailNetwork, Track, Track, Track, Junction, Junction, JunctionRoute, JunctionRoute
]:
    """
    A:B <-> B:A
    B:B <-> C:A
    """
    network = RailNetwork(name="ABC Network")

    track_a = make_track("Track A")
    track_b = make_track("Track B", condition=middle_condition)
    track_c = make_track("Track C")

    for track in (track_a, track_b, track_c):
        network.add_track(track)

    junction_ab, junction_bc, route_ab, route_bc = build_linear_connection_pair(
        left_track=track_a,
        middle_track=track_b,
        right_track=track_c,
        align_left=align_ab,
        align_right=align_bc,
    )

    # Optional: preserve your original names if you care about debugger readability
    junction_ab.name = "J_AB"
    junction_bc.name = "J_BC"

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


def build_boundary_network() -> tuple[RailNetwork, Track, BoundaryConnection]:
    network = RailNetwork(name="Boundary Network")

    track_a = make_track("Track A")
    network.add_track(track_a)

    boundary = BoundaryConnection(
        local_endpoint=endpoint_a(track_a),
        remote_network_id=uuid4(),
        remote_track_id=uuid4(),
        remote_end=TrackEnd.B,
        name="Outbound West",
    )

    network.add_boundary_connection(boundary)

    return network, track_a, boundary


# ---------------------------------------------------------------------
# Immediate movement option tests
# ---------------------------------------------------------------------


def test_movement_options_from_track_returns_adjacent_track_option() -> None:
    network, track_a, track_b, junction, route_ab = build_simple_ab_network()
    service = MovementService(network)

    options = service.movement_options_from_track(track_a.track_id)

    track_options = [opt for opt in options if opt.kind is MovementOptionKind.TRACK]

    assert len(track_options) == 1

    option = track_options[0]
    assert option.source_track_id == track_a.track_id
    assert option.destination_track_id == track_b.track_id
    assert option.junction_id == junction.junction_id
    assert option.required_route == route_ab
    assert option.is_currently_aligned is True


def test_movement_options_from_endpoint_returns_boundary_option() -> None:
    network, track_a, boundary = build_boundary_network()
    service = MovementService(network)

    options = service.movement_options_from_endpoint(endpoint_a(track_a))

    boundary_options = [
        opt for opt in options if opt.kind is MovementOptionKind.BOUNDARY
    ]

    assert len(boundary_options) == 1

    option = boundary_options[0]
    assert option.source_track_id == track_a.track_id
    assert option.boundary_connection_id == boundary.connection_id
    assert option.destination_track_id is None


def test_boundary_exists_at_endpoint_true_only_for_matching_endpoint() -> None:
    network, track_a, boundary = build_boundary_network()
    service = MovementService(network)

    assert service.boundary_exists_at_endpoint(endpoint_a(track_a)) is True
    assert service.boundary_exists_at_endpoint(endpoint_b(track_a)) is False


# ---------------------------------------------------------------------
# Path discovery tests
# ---------------------------------------------------------------------


def test_find_path_between_tracks_returns_single_hop_path() -> None:
    network, track_a, track_b, junction, route_ab = build_simple_ab_network()
    service = MovementService(network)

    path = service.find_path_between_tracks(track_a.track_id, track_b.track_id)

    assert path is not None
    assert path.track_ids == (track_a.track_id, track_b.track_id)
    assert len(path.steps) == 1

    step = path.steps[0]
    assert step.from_track_id == track_a.track_id
    assert step.to_track_id == track_b.track_id
    assert step.junction_id == junction.junction_id
    assert step.required_route == route_ab
    assert step.is_currently_aligned is True


def test_find_path_between_tracks_returns_multi_hop_path() -> None:
    network, track_a, track_b, track_c, junction_ab, junction_bc, route_ab, route_bc = (
        build_simple_abc_network()
    )
    service = MovementService(network)

    path = service.find_path_between_tracks(track_a.track_id, track_c.track_id)

    assert path is not None
    assert path.track_ids == (track_a.track_id, track_b.track_id, track_c.track_id)
    assert len(path.steps) == 2

    assert path.steps[0].from_track_id == track_a.track_id
    assert path.steps[0].to_track_id == track_b.track_id
    assert path.steps[1].from_track_id == track_b.track_id
    assert path.steps[1].to_track_id == track_c.track_id


def test_find_path_between_tracks_same_source_and_destination_returns_trivial_path() -> (
    None
):
    network, track_a, track_b, junction, route_ab = build_simple_ab_network()
    service = MovementService(network)

    path = service.find_path_between_tracks(track_a.track_id, track_a.track_id)

    assert path is not None
    assert path.track_ids == (track_a.track_id,)
    assert path.steps == ()


# ---------------------------------------------------------------------
# Feasibility tests
# ---------------------------------------------------------------------


def test_can_move_between_tracks_returns_success_for_connected_clear_aligned_path() -> (
    None
):
    network, track_a, track_b, track_c, junction_ab, junction_bc, route_ab, route_bc = (
        build_simple_abc_network()
    )
    service = MovementService(network)

    result = service.can_move_between_tracks(track_a.track_id, track_c.track_id)

    assert result.path_exists is True
    assert result.can_move is True
    assert result.blocked_reason is MovementBlockReason.NONE
    assert result.path is not None
    assert result.path.track_ids == (
        track_a.track_id,
        track_b.track_id,
        track_c.track_id,
    )


def test_can_move_between_tracks_fails_when_intermediate_track_out_of_service() -> None:
    network, track_a, track_b, track_c, junction_ab, junction_bc, route_ab, route_bc = (
        build_simple_abc_network(middle_condition=TrackCondition.OUT_OF_SERVICE)
    )
    service = MovementService(network)

    result = service.can_move_between_tracks(track_a.track_id, track_c.track_id)

    assert result.path_exists is True
    assert result.can_move is False
    assert result.blocked_reason is MovementBlockReason.TRACK_CONDITION
    assert result.blocked_track_id == track_b.track_id
    assert result.path is not None
    assert result.path.track_ids == (
        track_a.track_id,
        track_b.track_id,
        track_c.track_id,
    )


def test_can_move_between_tracks_fails_when_required_route_is_misaligned() -> None:
    network, track_a, track_b, track_c, junction_ab, junction_bc, route_ab, route_bc = (
        build_simple_abc_network(align_bc=False)
    )
    service = MovementService(network)

    result = service.can_move_between_tracks(track_a.track_id, track_c.track_id)

    assert result.path_exists is True
    assert result.can_move is False
    assert result.blocked_reason is MovementBlockReason.ROUTE_MISALIGNED
    assert result.blocked_route == route_bc
    assert route_bc in result.misaligned_routes


def test_can_move_between_tracks_returns_no_path_for_disconnected_tracks() -> None:
    network = RailNetwork(name="Disconnected Network")

    track_a = make_track("Track A")
    track_b = make_track("Track B")

    network.add_track(track_a)
    network.add_track(track_b)

    service = MovementService(network)

    result = service.can_move_between_tracks(track_a.track_id, track_b.track_id)

    assert result.path_exists is False
    assert result.can_move is False
    assert result.blocked_reason is MovementBlockReason.NO_PATH
    assert result.path is None


def test_can_move_between_tracks_raises_for_unknown_source_track() -> None:
    network, track_a, track_b, junction, route_ab = build_simple_ab_network()
    service = MovementService(network)

    with pytest.raises(ValueError, match="not found"):
        service.can_move_between_tracks(uuid4(), track_b.track_id)


def test_can_move_between_tracks_raises_for_unknown_destination_track() -> None:
    network, track_a, track_b, junction, route_ab = build_simple_ab_network()
    service = MovementService(network)

    with pytest.raises(ValueError, match="not found"):
        service.can_move_between_tracks(track_a.track_id, uuid4())
