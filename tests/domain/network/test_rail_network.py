from uuid import UUID, uuid4

import pytest

from railroad_sim.domain.enums import JunctionType, TrackEnd, TrackType
from railroad_sim.domain.junction import Junction, JunctionRoute, TrackEndpoint
from railroad_sim.domain.network.boundary_connection import BoundaryConnection
from railroad_sim.domain.network.rail_network import RailNetwork
from railroad_sim.domain.track import Track


def make_track(name: str) -> Track:
    return Track(
        name=name,
        track_type=TrackType.MAINLINE,
        length_ft=1000,
    )


def make_endpoint(track: Track, end: TrackEnd) -> TrackEndpoint:
    return TrackEndpoint(track=track, end=end)


def make_simple_junction(track_a: Track, track_b: Track) -> Junction:
    endpoint_a = make_endpoint(track_a, TrackEnd.B)
    endpoint_b = make_endpoint(track_b, TrackEnd.A)
    route = JunctionRoute(from_endpoint=endpoint_a, to_endpoint=endpoint_b)

    return Junction(
        name="JCT-1",
        junction_type=JunctionType.CONNECTION,
        endpoints={endpoint_a, endpoint_b},
        routes={route},
    )


def test_rail_network_creation_with_required_fields():
    network = RailNetwork(name="Pacific North")

    assert network.name == "Pacific North"
    assert network.tracks == {}
    assert network.junctions == {}
    assert network.boundary_connections == {}


def test_rail_network_generates_network_id_by_default():
    network = RailNetwork(name="Pacific North")

    assert isinstance(network.network_id, UUID)


def test_rail_network_accepts_explicit_network_id():
    explicit_id = uuid4()

    network = RailNetwork(
        name="Pacific North",
        network_id=explicit_id,
    )

    assert network.network_id == explicit_id


def test_rail_network_rejects_blank_name():
    with pytest.raises(ValueError, match="RailNetwork name must not be blank."):
        RailNetwork(name="   ")


def test_add_track_registers_track():
    network = RailNetwork(name="Pacific North")
    track = make_track("Main 1")

    network.add_track(track)

    assert network.tracks[track.track_id] is track


def test_add_track_rejects_duplicate_track_id():
    shared_id = uuid4()

    track_a = Track(
        name="Main 1",
        track_type=TrackType.MAINLINE,
        length_ft=1000,
        track_id=shared_id,
    )
    track_b = Track(
        name="Main 1 Reloaded",
        track_type=TrackType.MAINLINE,
        length_ft=1000,
        track_id=shared_id,
    )

    network = RailNetwork(name="Pacific North")
    network.add_track(track_a)

    with pytest.raises(ValueError, match="already exists in network"):
        network.add_track(track_b)


def test_get_track_returns_registered_track():
    network = RailNetwork(name="Pacific North")
    track = make_track("Main 1")
    network.add_track(track)

    result = network.get_track(track.track_id)

    assert result is track


def test_get_track_raises_for_unknown_track_id():
    network = RailNetwork(name="Pacific North")

    with pytest.raises(ValueError, match="Track id .* not found in network"):
        network.get_track(uuid4())


def test_add_junction_registers_valid_junction():
    network = RailNetwork(name="Pacific North")
    track_a = make_track("Main 1")
    track_b = make_track("Main 2")

    network.add_track(track_a)
    network.add_track(track_b)

    junction = make_simple_junction(track_a, track_b)

    network.add_junction(junction)

    assert network.junctions[junction.junction_id] is junction


def test_add_junction_rejects_duplicate_junction_id():
    shared_id = uuid4()

    network = RailNetwork(name="Pacific North")
    track_a = make_track("Main 1")
    track_b = make_track("Main 2")
    track_c = make_track("Main 3")

    network.add_track(track_a)
    network.add_track(track_b)
    network.add_track(track_c)

    junction_a = make_simple_junction(track_a, track_b)
    junction_a.junction_id = shared_id

    endpoint_a = make_endpoint(track_b, TrackEnd.B)
    endpoint_b = make_endpoint(track_c, TrackEnd.A)
    route = JunctionRoute(from_endpoint=endpoint_a, to_endpoint=endpoint_b)
    junction_b = Junction(
        name="JCT-2",
        junction_type=JunctionType.CONNECTION,
        endpoints={endpoint_a, endpoint_b},
        routes={route},
        junction_id=shared_id,
    )

    network.add_junction(junction_a)

    with pytest.raises(ValueError, match="already exists in network"):
        network.add_junction(junction_b)


def test_add_junction_rejects_reference_to_unregistered_track():
    network = RailNetwork(name="Pacific North")
    track_a = make_track("Main 1")
    track_b = make_track("Main 2")

    network.add_track(track_a)

    junction = make_simple_junction(track_a, track_b)

    with pytest.raises(ValueError, match="is not registered in network"):
        network.add_junction(junction)


def test_get_junction_returns_registered_junction():
    network = RailNetwork(name="Pacific North")
    track_a = make_track("Main 1")
    track_b = make_track("Main 2")

    network.add_track(track_a)
    network.add_track(track_b)

    junction = make_simple_junction(track_a, track_b)
    network.add_junction(junction)

    result = network.get_junction(junction.junction_id)

    assert result is junction


def test_get_junction_raises_for_unknown_junction_id():
    network = RailNetwork(name="Pacific North")

    with pytest.raises(ValueError, match="Junction id .* not found in network"):
        network.get_junction(uuid4())


def test_add_boundary_connection_registers_valid_connection():
    network = RailNetwork(name="Pacific North")
    track = make_track("Main 1")
    network.add_track(track)

    endpoint = make_endpoint(track, TrackEnd.B)

    connection = BoundaryConnection(
        local_endpoint=endpoint,
        remote_network_id=uuid4(),
        remote_track_id=uuid4(),
        remote_end=TrackEnd.A,
    )

    network.add_boundary_connection(connection)

    assert network.boundary_connections[connection.connection_id] is connection


def test_add_boundary_connection_rejects_duplicate_connection_id():
    shared_id = uuid4()

    network = RailNetwork(name="Pacific North")
    track = make_track("Main 1")
    network.add_track(track)

    endpoint = make_endpoint(track, TrackEnd.B)

    connection_a = BoundaryConnection(
        local_endpoint=endpoint,
        remote_network_id=uuid4(),
        remote_track_id=uuid4(),
        remote_end=TrackEnd.A,
        connection_id=shared_id,
    )
    connection_b = BoundaryConnection(
        local_endpoint=endpoint,
        remote_network_id=uuid4(),
        remote_track_id=uuid4(),
        remote_end=TrackEnd.A,
        connection_id=shared_id,
    )

    network.add_boundary_connection(connection_a)

    with pytest.raises(ValueError, match="already exists"):
        network.add_boundary_connection(connection_b)


def test_add_boundary_connection_rejects_unregistered_local_track():
    network = RailNetwork(name="Pacific North")
    track = make_track("Main 1")
    endpoint = make_endpoint(track, TrackEnd.B)

    connection = BoundaryConnection(
        local_endpoint=endpoint,
        remote_network_id=uuid4(),
        remote_track_id=uuid4(),
        remote_end=TrackEnd.A,
    )

    with pytest.raises(ValueError, match="is not registered in network"):
        network.add_boundary_connection(connection)


def test_boundary_connections_for_track_returns_matching_connections():
    network = RailNetwork(name="Pacific North")
    track_a = make_track("Main 1")
    track_b = make_track("Main 2")

    network.add_track(track_a)
    network.add_track(track_b)

    endpoint_a = make_endpoint(track_a, TrackEnd.B)
    endpoint_b = make_endpoint(track_b, TrackEnd.A)

    connection_a = BoundaryConnection(
        local_endpoint=endpoint_a,
        remote_network_id=uuid4(),
        remote_track_id=uuid4(),
        remote_end=TrackEnd.A,
    )
    connection_b = BoundaryConnection(
        local_endpoint=endpoint_b,
        remote_network_id=uuid4(),
        remote_track_id=uuid4(),
        remote_end=TrackEnd.B,
    )

    network.add_boundary_connection(connection_a)
    network.add_boundary_connection(connection_b)

    results = network.boundary_connections_for_track(track_a.track_id)

    assert results == [connection_a]


def test_boundary_connections_for_endpoint_returns_matching_connections():
    network = RailNetwork(name="Pacific North")
    track = make_track("Main 1")
    network.add_track(track)

    endpoint_a = make_endpoint(track, TrackEnd.A)
    endpoint_b = make_endpoint(track, TrackEnd.B)

    connection_a = BoundaryConnection(
        local_endpoint=endpoint_a,
        remote_network_id=uuid4(),
        remote_track_id=uuid4(),
        remote_end=TrackEnd.A,
    )
    connection_b = BoundaryConnection(
        local_endpoint=endpoint_b,
        remote_network_id=uuid4(),
        remote_track_id=uuid4(),
        remote_end=TrackEnd.B,
    )

    network.add_boundary_connection(connection_a)
    network.add_boundary_connection(connection_b)

    results = network.boundary_connections_for_endpoint(endpoint_b)

    assert results == [connection_b]


def test_junctions_for_track_returns_matching_junctions():
    network = RailNetwork(name="Pacific North")

    track_a = make_track("Main 1")
    track_b = make_track("Main 2")
    track_c = make_track("Siding 1")

    network.add_track(track_a)
    network.add_track(track_b)
    network.add_track(track_c)

    junction_1 = make_simple_junction(track_a, track_b)

    endpoint_a = make_endpoint(track_a, TrackEnd.A)
    endpoint_c = make_endpoint(track_c, TrackEnd.A)
    route_2 = JunctionRoute(from_endpoint=endpoint_a, to_endpoint=endpoint_c)
    junction_2 = Junction(
        name="JCT-2",
        junction_type=JunctionType.CONNECTION,
        endpoints={endpoint_a, endpoint_c},
        routes={route_2},
    )

    network.add_junction(junction_1)
    network.add_junction(junction_2)

    results = network.junctions_for_track(track_a.track_id)

    assert len(results) == 2
    assert junction_1 in results
    assert junction_2 in results


def test_junctions_for_track_raises_for_unknown_track_id():
    network = RailNetwork(name="Pacific North")

    with pytest.raises(ValueError, match="Track id .* not found in network"):
        network.junctions_for_track(uuid4())


def test_junctions_for_endpoint_returns_matching_junction():
    network = RailNetwork(name="Pacific North")

    track_a = make_track("Main 1")
    track_b = make_track("Main 2")

    network.add_track(track_a)
    network.add_track(track_b)

    endpoint_a = make_endpoint(track_a, TrackEnd.B)
    endpoint_b = make_endpoint(track_b, TrackEnd.A)
    route = JunctionRoute(from_endpoint=endpoint_a, to_endpoint=endpoint_b)

    junction = Junction(
        name="JCT-1",
        junction_type=JunctionType.CONNECTION,
        endpoints={endpoint_a, endpoint_b},
        routes={route},
    )

    network.add_junction(junction)

    results = network.junctions_for_endpoint(endpoint_a)

    assert results == [junction]


def test_junctions_for_endpoint_raises_for_unregistered_track():
    network = RailNetwork(name="Pacific North")
    track = make_track("Main 1")
    endpoint = make_endpoint(track, TrackEnd.A)

    with pytest.raises(
        ValueError, match="Endpoint track .* is not registered in network"
    ):
        network.junctions_for_endpoint(endpoint)


def test_connected_tracks_returns_directly_connected_tracks():
    network = RailNetwork(name="Pacific North")

    track_a = make_track("Main 1")
    track_b = make_track("Main 2")
    track_c = make_track("Siding 1")

    network.add_track(track_a)
    network.add_track(track_b)
    network.add_track(track_c)

    junction_1 = make_simple_junction(track_a, track_b)

    endpoint_a = make_endpoint(track_a, TrackEnd.A)
    endpoint_c = make_endpoint(track_c, TrackEnd.A)
    route_2 = JunctionRoute(from_endpoint=endpoint_a, to_endpoint=endpoint_c)
    junction_2 = Junction(
        name="JCT-2",
        junction_type=JunctionType.CONNECTION,
        endpoints={endpoint_a, endpoint_c},
        routes={route_2},
    )

    network.add_junction(junction_1)
    network.add_junction(junction_2)

    results = network.connected_tracks(track_a.track_id)

    assert len(results) == 2
    assert track_b in results
    assert track_c in results


def test_connected_tracks_returns_unique_tracks():
    network = RailNetwork(name="Pacific North")

    track_a = make_track("Main 1")
    track_b = make_track("Main 2")

    network.add_track(track_a)
    network.add_track(track_b)

    endpoint_a1 = make_endpoint(track_a, TrackEnd.A)
    endpoint_b1 = make_endpoint(track_b, TrackEnd.A)
    route_1 = JunctionRoute(from_endpoint=endpoint_a1, to_endpoint=endpoint_b1)
    junction_1 = Junction(
        name="JCT-1",
        junction_type=JunctionType.CONNECTION,
        endpoints={endpoint_a1, endpoint_b1},
        routes={route_1},
    )

    endpoint_a2 = make_endpoint(track_a, TrackEnd.B)
    endpoint_b2 = make_endpoint(track_b, TrackEnd.B)
    route_2 = JunctionRoute(from_endpoint=endpoint_a2, to_endpoint=endpoint_b2)
    junction_2 = Junction(
        name="JCT-2",
        junction_type=JunctionType.CONNECTION,
        endpoints={endpoint_a2, endpoint_b2},
        routes={route_2},
    )

    network.add_junction(junction_1)
    network.add_junction(junction_2)

    results = network.connected_tracks(track_a.track_id)

    assert results == [track_b]


def test_connected_tracks_raises_for_unknown_track_id():
    network = RailNetwork(name="Pacific North")

    with pytest.raises(ValueError, match="Track id .* not found in network"):
        network.connected_tracks(uuid4())


def test_topology_summary_includes_expected_sections_and_connections():
    network = RailNetwork(name="Pacific North")

    track_a = make_track("Main 1")
    track_b = make_track("Main 2")

    network.add_track(track_a)
    network.add_track(track_b)

    junction = make_simple_junction(track_a, track_b)
    network.add_junction(junction)

    summary = network.topology_summary()

    assert "RailNetwork: Pacific North" in summary
    assert "Tracks" in summary
    assert "Junctions" in summary
    assert "Connectivity" in summary
    assert "Main 1 (A,B)" in summary
    assert "Main 2 (A,B)" in summary
    assert "JCT-1" in summary
    assert "Main 1:B  <->  Main 2:A" in summary
    assert "Main 1 -> Main 2" in summary
    assert "Main 2 -> Main 1" in summary


def test_debug_topology_summary_output():
    network = RailNetwork(name="Pacific North")

    track_a = make_track("Main 1")
    track_b = make_track("Main 2")

    network.add_track(track_a)
    network.add_track(track_b)

    junction = make_simple_junction(track_a, track_b)
    network.add_junction(junction)

    print()
    print(network.topology_summary())


def test_graph_edges_returns_bidirectional_junction_edges():
    network = RailNetwork(name="Pacific North")

    track_a = make_track("Main 1")
    track_b = make_track("Main 2")

    network.add_track(track_a)
    network.add_track(track_b)

    junction = make_simple_junction(track_a, track_b)
    network.add_junction(junction)

    edges = network.graph_edges()

    assert ("Main 1:B", "Main 2:A", "junction:JCT-1") in edges
    assert ("Main 2:A", "Main 1:B", "junction:JCT-1") in edges


def test_graph_edges_includes_boundary_edge():
    network = RailNetwork(name="Pacific North")

    track = make_track("Main 1")
    network.add_track(track)

    endpoint = make_endpoint(track, TrackEnd.B)
    remote_network_id = uuid4()
    remote_track_id = uuid4()

    connection = BoundaryConnection(
        local_endpoint=endpoint,
        remote_network_id=remote_network_id,
        remote_track_id=remote_track_id,
        remote_end=TrackEnd.A,
    )
    network.add_boundary_connection(connection)

    edges = network.graph_edges()

    assert (
        "Main 1:B",
        f"remote:{remote_network_id}/{remote_track_id}:A",
        "boundary",
    ) in edges


def test_graph_debugger_summary_includes_endpoint_and_edge_sections():
    network = RailNetwork(name="Pacific North")

    track_a = make_track("Main 1")
    track_b = make_track("Main 2")

    network.add_track(track_a)
    network.add_track(track_b)

    junction = make_simple_junction(track_a, track_b)
    network.add_junction(junction)

    summary = network.graph_debugger_summary()

    assert "RailNetwork Graph: Pacific North" in summary
    assert "Endpoints" in summary
    assert "Edges" in summary
    assert "Boundary Edges" in summary
    assert "Main 1:A" in summary
    assert "Main 1:B" in summary
    assert "Main 2:A" in summary
    assert "Main 2:B" in summary
    assert "Main 1:B -> Main 2:A [junction:JCT-1]" in summary


def test_graph_debugger_summary_shows_none_when_no_boundary_edges():
    network = RailNetwork(name="Pacific North")

    track_a = make_track("Main 1")
    track_b = make_track("Main 2")

    network.add_track(track_a)
    network.add_track(track_b)

    junction = make_simple_junction(track_a, track_b)
    network.add_junction(junction)

    summary = network.graph_debugger_summary()

    assert "Boundary Edges" in summary
    assert "(none)" in summary
