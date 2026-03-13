from __future__ import annotations

from uuid import uuid4

import pytest

from railroad_sim.domain.enums import JunctionType, TrackEnd
from railroad_sim.domain.junction import Junction
from railroad_sim.domain.network.boundary_connection import BoundaryConnection
from railroad_sim.domain.network.rail_network import RailNetwork
from railroad_sim.domain.track import Track
from tests.support.junction_builders import make_connection_junction, make_route
from tests.support.track_builders import endpoint_a, endpoint_b, make_track


def make_simple_junction(track_a: Track, track_b: Track) -> Junction:
    junction, _route = make_connection_junction(
        name="JCT-1",
        left_track=track_a,
        left_end=TrackEnd.B,
        right_track=track_b,
        right_end=TrackEnd.A,
        aligned=True,
    )
    return junction


def test_network_name_must_not_be_blank():
    with pytest.raises(ValueError, match="must not be blank"):
        RailNetwork(name="")


def test_add_track_registers_track():
    network = RailNetwork(name="Main Subdivision")
    track = make_track("Main 1", length_ft=5000)

    network.add_track(track)

    assert network.get_track(track.track_id) is track


def test_add_track_rejects_duplicate_track_id():
    network = RailNetwork(name="Main Subdivision")
    track = make_track("Main 1", length_ft=5000)

    network.add_track(track)

    duplicate = make_track("Main 1 Duplicate", length_ft=4000)
    duplicate.track_id = track.track_id

    with pytest.raises(ValueError, match="already exists"):
        network.add_track(duplicate)


def test_get_track_raises_for_unknown_track():
    network = RailNetwork(name="Main Subdivision")

    with pytest.raises(ValueError, match="not found"):
        network.get_track(uuid4())


def test_add_junction_registers_junction():
    network = RailNetwork(name="Terminal")

    track_a = make_track("A", length_ft=1000)
    track_b = make_track("B", length_ft=1000)

    network.add_track(track_a)
    network.add_track(track_b)

    junction = make_simple_junction(track_a, track_b)

    network.add_junction(junction)

    assert network.get_junction(junction.junction_id) is junction


def test_add_junction_rejects_duplicate_junction_id():
    network = RailNetwork(name="Terminal")

    track_a = make_track("A", length_ft=1000)
    track_b = make_track("B", length_ft=1000)

    network.add_track(track_a)
    network.add_track(track_b)

    junction1, _route1 = make_connection_junction(
        name="J1",
        left_track=track_a,
        left_end=TrackEnd.B,
        right_track=track_b,
        right_end=TrackEnd.A,
    )
    network.add_junction(junction1)

    junction2, _route2 = make_connection_junction(
        name="J2",
        left_track=track_a,
        left_end=TrackEnd.B,
        right_track=track_b,
        right_end=TrackEnd.A,
    )
    junction2.junction_id = junction1.junction_id

    with pytest.raises(ValueError, match="already exists"):
        network.add_junction(junction2)


def test_add_junction_rejects_unknown_track_reference():
    network = RailNetwork(name="Terminal")

    track_a = make_track("A", length_ft=1000)
    track_b = make_track("B", length_ft=1000)

    network.add_track(track_a)

    route = make_route(
        from_track=track_a,
        from_end=TrackEnd.B,
        to_track=track_b,
        to_end=TrackEnd.A,
    )

    junction = Junction(
        name="JCT-1",
        junction_type=JunctionType.CONNECTION,
        endpoints={endpoint_b(track_a), endpoint_a(track_b)},
        routes={route},
        aligned_routes={route},
    )

    with pytest.raises(ValueError, match="not registered"):
        network.add_junction(junction)


def test_get_junction_raises_for_unknown_junction():
    network = RailNetwork(name="Terminal")

    with pytest.raises(ValueError, match="not found"):
        network.get_junction(uuid4())


def test_junctions_for_track_returns_matching_junctions():
    network = RailNetwork(name="Terminal")

    track_a = make_track("A", length_ft=1000)
    track_b = make_track("B", length_ft=1000)
    track_c = make_track("C", length_ft=1000)

    for track in (track_a, track_b, track_c):
        network.add_track(track)

    junction1, _route1 = make_connection_junction(
        name="J1",
        left_track=track_a,
        left_end=TrackEnd.B,
        right_track=track_b,
        right_end=TrackEnd.A,
    )
    junction2, _route2 = make_connection_junction(
        name="J2",
        left_track=track_b,
        left_end=TrackEnd.B,
        right_track=track_c,
        right_end=TrackEnd.A,
    )

    network.add_junction(junction1)
    network.add_junction(junction2)

    result = network.junctions_for_track(track_b.track_id)

    assert junction1 in result
    assert junction2 in result
    assert len(result) == 2


def test_junctions_for_track_raises_for_unknown_track():
    network = RailNetwork(name="Terminal")

    with pytest.raises(ValueError, match="not found"):
        network.junctions_for_track(uuid4())


def test_junctions_for_endpoint_returns_matching_junctions():
    network = RailNetwork(name="Terminal")

    track_a = make_track("A", length_ft=1000)
    track_b = make_track("B", length_ft=1000)

    network.add_track(track_a)
    network.add_track(track_b)

    junction = make_simple_junction(track_a, track_b)
    network.add_junction(junction)

    result = network.junctions_for_endpoint(endpoint_b(track_a))

    assert result == [junction]


def test_junctions_for_endpoint_raises_for_unknown_track():
    network = RailNetwork(name="Terminal")

    unknown_track = make_track("Ghost", length_ft=1000)
    endpoint = endpoint_a(unknown_track)

    with pytest.raises(ValueError, match="not registered"):
        network.junctions_for_endpoint(endpoint)


def test_connected_tracks_returns_direct_connections():
    network = RailNetwork(name="Terminal")

    track_a = make_track("A", length_ft=1000)
    track_b = make_track("B", length_ft=1000)
    track_c = make_track("C", length_ft=1000)

    for track in (track_a, track_b, track_c):
        network.add_track(track)

    junction1, _route1 = make_connection_junction(
        name="J1",
        left_track=track_a,
        left_end=TrackEnd.B,
        right_track=track_b,
        right_end=TrackEnd.A,
    )
    junction2, _route2 = make_connection_junction(
        name="J2",
        left_track=track_b,
        left_end=TrackEnd.B,
        right_track=track_c,
        right_end=TrackEnd.A,
    )

    network.add_junction(junction1)
    network.add_junction(junction2)

    connected_to_b = network.connected_tracks(track_b.track_id)

    assert track_a in connected_to_b
    assert track_c in connected_to_b
    assert len(connected_to_b) == 2


def test_connected_tracks_raises_for_unknown_track():
    network = RailNetwork(name="Terminal")

    with pytest.raises(ValueError, match="not found"):
        network.connected_tracks(uuid4())


def test_add_boundary_connection_registers_connection():
    network = RailNetwork(name="Division A")
    track = make_track("Main", length_ft=5000)
    network.add_track(track)

    connection = BoundaryConnection(
        local_endpoint=endpoint_b(track),
        remote_network_id=uuid4(),
        remote_track_id=uuid4(),
        remote_end=TrackEnd.A,
        name="To Division B",
    )

    network.add_boundary_connection(connection)

    assert connection.connection_id in network.boundary_connections


def test_add_boundary_connection_rejects_duplicate_connection_id():
    network = RailNetwork(name="Division A")
    track = make_track("Main", length_ft=5000)
    network.add_track(track)

    connection1 = BoundaryConnection(
        local_endpoint=endpoint_b(track),
        remote_network_id=uuid4(),
        remote_track_id=uuid4(),
        remote_end=TrackEnd.A,
    )

    connection2 = BoundaryConnection(
        local_endpoint=endpoint_b(track),
        remote_network_id=uuid4(),
        remote_track_id=uuid4(),
        remote_end=TrackEnd.A,
    )
    connection2.connection_id = connection1.connection_id

    network.add_boundary_connection(connection1)

    with pytest.raises(ValueError, match="already exists"):
        network.add_boundary_connection(connection2)


def test_add_boundary_connection_rejects_unknown_local_track():
    network = RailNetwork(name="Division A")
    unknown_track = make_track("Ghost", length_ft=5000)

    connection = BoundaryConnection(
        local_endpoint=endpoint_a(unknown_track),
        remote_network_id=uuid4(),
        remote_track_id=uuid4(),
        remote_end=TrackEnd.B,
    )

    with pytest.raises(ValueError, match="not registered"):
        network.add_boundary_connection(connection)


def test_boundary_connections_for_track_returns_matching_connections():
    network = RailNetwork(name="Division A")
    track_a = make_track("A", length_ft=5000)
    track_b = make_track("B", length_ft=5000)

    network.add_track(track_a)
    network.add_track(track_b)

    connection1 = BoundaryConnection(
        local_endpoint=endpoint_a(track_a),
        remote_network_id=uuid4(),
        remote_track_id=uuid4(),
        remote_end=TrackEnd.B,
    )
    connection2 = BoundaryConnection(
        local_endpoint=endpoint_b(track_a),
        remote_network_id=uuid4(),
        remote_track_id=uuid4(),
        remote_end=TrackEnd.A,
    )
    connection3 = BoundaryConnection(
        local_endpoint=endpoint_a(track_b),
        remote_network_id=uuid4(),
        remote_track_id=uuid4(),
        remote_end=TrackEnd.B,
    )

    network.add_boundary_connection(connection1)
    network.add_boundary_connection(connection2)
    network.add_boundary_connection(connection3)

    result = network.boundary_connections_for_track(track_a.track_id)

    assert connection1 in result
    assert connection2 in result
    assert connection3 not in result
    assert len(result) == 2


def test_boundary_connections_for_endpoint_returns_matching_connections():
    network = RailNetwork(name="Division A")
    track = make_track("Main", length_ft=5000)
    network.add_track(track)

    endpoint = endpoint_b(track)

    connection1 = BoundaryConnection(
        local_endpoint=endpoint,
        remote_network_id=uuid4(),
        remote_track_id=uuid4(),
        remote_end=TrackEnd.A,
    )
    connection2 = BoundaryConnection(
        local_endpoint=endpoint_a(track),
        remote_network_id=uuid4(),
        remote_track_id=uuid4(),
        remote_end=TrackEnd.B,
    )

    network.add_boundary_connection(connection1)
    network.add_boundary_connection(connection2)

    result = network.boundary_connections_for_endpoint(endpoint)

    assert result == [connection1]


def test_topology_summary_includes_tracks_junctions_and_connectivity():
    network = RailNetwork(name="Sample Network")

    track_a = make_track("A", length_ft=1000)
    track_b = make_track("B", length_ft=1000)

    network.add_track(track_a)
    network.add_track(track_b)

    junction = make_simple_junction(track_a, track_b)
    network.add_junction(junction)

    summary = network.topology_summary()

    assert "RailNetwork: Sample Network" in summary
    assert "Tracks" in summary
    assert "A (A,B)" in summary
    assert "B (A,B)" in summary
    assert "Junctions" in summary
    assert "JCT-1" in summary
    assert "Connectivity" in summary
    assert "A -> B" in summary or "B -> A" in summary


def test_graph_edges_returns_junction_and_boundary_edges():
    network = RailNetwork(name="Sample Network")

    track_a = make_track("A", length_ft=1000)
    track_b = make_track("B", length_ft=1000)

    network.add_track(track_a)
    network.add_track(track_b)

    junction = make_simple_junction(track_a, track_b)
    network.add_junction(junction)

    boundary = BoundaryConnection(
        local_endpoint=endpoint_a(track_a),
        remote_network_id=uuid4(),
        remote_track_id=uuid4(),
        remote_end=TrackEnd.B,
    )
    network.add_boundary_connection(boundary)

    edges = network.graph_edges()

    assert ("A:B", "B:A", "junction:JCT-1") in edges
    assert ("B:A", "A:B", "junction:JCT-1") in edges

    boundary_edges = [edge for edge in edges if edge[2] == "boundary"]
    assert len(boundary_edges) == 1
    assert boundary_edges[0][0] == "A:A"
    assert boundary_edges[0][1].startswith("remote:")


def test_graph_debugger_summary_lists_endpoints_and_edges():
    network = RailNetwork(name="Sample Network")

    track_a = make_track("A", length_ft=1000)
    track_b = make_track("B", length_ft=1000)

    network.add_track(track_a)
    network.add_track(track_b)

    junction = make_simple_junction(track_a, track_b)
    network.add_junction(junction)

    summary = network.graph_debugger_summary()

    assert "RailNetwork Graph: Sample Network" in summary
    assert "Endpoints" in summary
    assert "A:A" in summary
    assert "A:B" in summary
    assert "B:A" in summary
    assert "B:B" in summary
    assert "Edges" in summary
    assert "A:B -> B:A [junction:JCT-1]" in summary


def test_graph_debugger_summary_lists_none_when_no_boundary_edges():
    network = RailNetwork(name="Sample Network")
    track = make_track("Solo", length_ft=1000)
    network.add_track(track)

    summary = network.graph_debugger_summary()

    assert "Boundary Edges" in summary
    assert "(none)" in summary
