from uuid import UUID, uuid4

import pytest

from railroad_sim.domain.enums import JunctionType, TrackEnd, TrackType
from railroad_sim.domain.junction import Junction, JunctionRoute, TrackEndpoint
from railroad_sim.domain.track import Track
from tests.support.track_builders import make_track


def test_track_endpoint_creation():
    track = make_track("Main 1")

    endpoint = TrackEndpoint(track=track, end=TrackEnd.A)

    assert endpoint.track is track
    assert endpoint.end == TrackEnd.A


def test_junction_generates_junction_id_by_default():
    track_a = make_track("Main 1")
    track_b = make_track("Main 2")

    endpoint_a = TrackEndpoint(track=track_a, end=TrackEnd.B)
    endpoint_b = TrackEndpoint(track=track_b, end=TrackEnd.A)
    route = JunctionRoute(from_endpoint=endpoint_a, to_endpoint=endpoint_b)

    junction = Junction(
        name="JCT-1",
        junction_type=JunctionType.CONNECTION,
        endpoints={endpoint_a, endpoint_b},
        routes={route},
    )

    assert isinstance(junction.junction_id, UUID)


def test_junction_accepts_explicit_junction_id():
    explicit_id = uuid4()

    track_a = make_track("Main 1")
    track_b = make_track("Main 2")

    endpoint_a = TrackEndpoint(track=track_a, end=TrackEnd.B)
    endpoint_b = TrackEndpoint(track=track_b, end=TrackEnd.A)
    route = JunctionRoute(from_endpoint=endpoint_a, to_endpoint=endpoint_b)

    junction = Junction(
        name="JCT-1",
        junction_type=JunctionType.CONNECTION,
        endpoints={endpoint_a, endpoint_b},
        routes={route},
        junction_id=explicit_id,
    )

    assert junction.junction_id == explicit_id


def test_track_endpoint_equality_uses_track_id_not_object_identity():
    shared_track_id = uuid4()

    track_a1 = Track(
        name="Main 1",
        track_type=TrackType.MAINLINE,
        length_ft=1000,
        track_id=shared_track_id,
    )
    track_a2 = Track(
        name="Main 1 Reloaded",
        track_type=TrackType.MAINLINE,
        length_ft=1000,
        track_id=shared_track_id,
    )

    endpoint_1 = TrackEndpoint(track=track_a1, end=TrackEnd.A)
    endpoint_2 = TrackEndpoint(track=track_a2, end=TrackEnd.A)

    assert endpoint_1 == endpoint_2
    assert hash(endpoint_1) == hash(endpoint_2)


def test_track_endpoint_distinguishes_different_ends_on_same_track_id():
    shared_track_id = uuid4()

    track_a1 = Track(
        name="Main 1",
        track_type=TrackType.MAINLINE,
        length_ft=1000,
        track_id=shared_track_id,
    )
    track_a2 = Track(
        name="Main 1 Reloaded",
        track_type=TrackType.MAINLINE,
        length_ft=1000,
        track_id=shared_track_id,
    )

    endpoint_a = TrackEndpoint(track=track_a1, end=TrackEnd.A)
    endpoint_b = TrackEndpoint(track=track_a2, end=TrackEnd.B)

    assert endpoint_a != endpoint_b


def test_junction_route_creation():
    track_a = make_track("Main 1")
    track_b = make_track("Main 2")

    endpoint_a = TrackEndpoint(track=track_a, end=TrackEnd.B)
    endpoint_b = TrackEndpoint(track=track_b, end=TrackEnd.A)

    route = JunctionRoute(from_endpoint=endpoint_a, to_endpoint=endpoint_b)

    assert route.from_endpoint == endpoint_a
    assert route.to_endpoint == endpoint_b


def test_junction_route_rejects_same_endpoint_on_both_sides():
    track = make_track("Main 1")
    endpoint = TrackEndpoint(track=track, end=TrackEnd.A)

    with pytest.raises(ValueError, match="cannot connect an endpoint to itself"):
        JunctionRoute(from_endpoint=endpoint, to_endpoint=endpoint)


def test_junction_route_rejects_two_ends_of_same_track():
    track = make_track("Main 1")
    endpoint_a = TrackEndpoint(track=track, end=TrackEnd.A)
    endpoint_b = TrackEndpoint(track=track, end=TrackEnd.B)

    with pytest.raises(ValueError, match="must connect two different tracks"):
        JunctionRoute(from_endpoint=endpoint_a, to_endpoint=endpoint_b)


def test_junction_creation_with_valid_connection():
    track_a = make_track("Main 1")
    track_b = make_track("Main 2")

    endpoint_a = TrackEndpoint(track=track_a, end=TrackEnd.B)
    endpoint_b = TrackEndpoint(track=track_b, end=TrackEnd.A)
    route = JunctionRoute(from_endpoint=endpoint_a, to_endpoint=endpoint_b)

    junction = Junction(
        name="JCT-1",
        junction_type=JunctionType.CONNECTION,
        endpoints={endpoint_a, endpoint_b},
        routes={route},
    )

    assert junction.name == "JCT-1"
    assert junction.junction_type == JunctionType.CONNECTION
    assert junction.endpoints == {endpoint_a, endpoint_b}
    assert junction.routes == {route}
    assert junction.aligned_routes == set()


def test_junction_rejects_blank_name():
    track_a = make_track("Main 1")
    track_b = make_track("Main 2")

    endpoint_a = TrackEndpoint(track=track_a, end=TrackEnd.B)
    endpoint_b = TrackEndpoint(track=track_b, end=TrackEnd.A)
    route = JunctionRoute(from_endpoint=endpoint_a, to_endpoint=endpoint_b)

    with pytest.raises(ValueError, match="junction name must not be blank"):
        Junction(
            name="   ",
            junction_type=JunctionType.CONNECTION,
            endpoints={endpoint_a, endpoint_b},
            routes={route},
        )


def test_junction_rejects_fewer_than_two_endpoints():
    track = make_track("Main 1")
    endpoint = TrackEndpoint(track=track, end=TrackEnd.A)

    with pytest.raises(ValueError, match="must connect at least two track endpoints"):
        Junction(
            name="JCT-1",
            junction_type=JunctionType.CONNECTION,
            endpoints={endpoint},
            routes=set(),
        )


def test_junction_rejects_route_with_unknown_endpoint():
    track_a = make_track("Main 1")
    track_b = make_track("Main 2")
    track_c = make_track("Main 3")

    endpoint_a = TrackEndpoint(track=track_a, end=TrackEnd.B)
    endpoint_b = TrackEndpoint(track=track_b, end=TrackEnd.A)
    endpoint_c = TrackEndpoint(track=track_c, end=TrackEnd.A)

    route = JunctionRoute(from_endpoint=endpoint_a, to_endpoint=endpoint_c)

    with pytest.raises(ValueError, match="is not registered on junction"):
        Junction(
            name="JCT-1",
            junction_type=JunctionType.TURNOUT,
            endpoints={endpoint_a, endpoint_b},
            routes={route},
        )


def test_junction_connects_returns_true_for_member_endpoint():
    track_a = make_track("Main 1")
    track_b = make_track("Main 2")

    endpoint_a = TrackEndpoint(track=track_a, end=TrackEnd.B)
    endpoint_b = TrackEndpoint(track=track_b, end=TrackEnd.A)
    route = JunctionRoute(from_endpoint=endpoint_a, to_endpoint=endpoint_b)

    junction = Junction(
        name="JCT-1",
        junction_type=JunctionType.CONNECTION,
        endpoints={endpoint_a, endpoint_b},
        routes={route},
    )

    assert junction.connects(endpoint_a) is True
    assert junction.connects(endpoint_b) is True


def test_can_route_returns_true_for_defined_route():
    track_a = make_track("Main 1")
    track_b = make_track("Main 2")

    endpoint_a = TrackEndpoint(track=track_a, end=TrackEnd.B)
    endpoint_b = TrackEndpoint(track=track_b, end=TrackEnd.A)
    route = JunctionRoute(from_endpoint=endpoint_a, to_endpoint=endpoint_b)

    junction = Junction(
        name="JCT-1",
        junction_type=JunctionType.CONNECTION,
        endpoints={endpoint_a, endpoint_b},
        routes={route},
    )

    assert junction.can_route(endpoint_a, endpoint_b) is True
    assert junction.can_route(endpoint_b, endpoint_a) is True


def test_available_routes_from_returns_matching_routes():
    track_a = make_track("Main 1")
    track_b = make_track("Siding 1")
    track_c = make_track("Spur 1")

    endpoint_a = TrackEndpoint(track=track_a, end=TrackEnd.B)
    endpoint_b = TrackEndpoint(track=track_b, end=TrackEnd.A)
    endpoint_c = TrackEndpoint(track=track_c, end=TrackEnd.A)

    route_ab = JunctionRoute(from_endpoint=endpoint_a, to_endpoint=endpoint_b)
    route_ac = JunctionRoute(from_endpoint=endpoint_a, to_endpoint=endpoint_c)

    junction = Junction(
        name="JCT-TURNOUT",
        junction_type=JunctionType.TURNOUT,
        endpoints={endpoint_a, endpoint_b, endpoint_c},
        routes={route_ab, route_ac},
    )

    routes = junction.available_routes_from(endpoint_a)

    assert len(routes) == 2
    assert route_ab in routes
    assert route_ac in routes


def test_available_routes_from_raises_for_unknown_endpoint():
    track_a = make_track("Main 1")
    track_b = make_track("Main 2")
    track_c = make_track("Main 3")

    endpoint_a = TrackEndpoint(track=track_a, end=TrackEnd.B)
    endpoint_b = TrackEndpoint(track=track_b, end=TrackEnd.A)
    endpoint_c = TrackEndpoint(track=track_c, end=TrackEnd.A)

    route = JunctionRoute(from_endpoint=endpoint_a, to_endpoint=endpoint_b)

    junction = Junction(
        name="JCT-1",
        junction_type=JunctionType.CONNECTION,
        endpoints={endpoint_a, endpoint_b},
        routes={route},
    )

    with pytest.raises(ValueError, match="Endpoint is not part of junction"):
        junction.available_routes_from(endpoint_c)


def test_align_route_sets_exactly_one_aligned_route():
    track_a = make_track("Main 1")
    track_b = make_track("Siding 1")
    track_c = make_track("Spur 1")

    endpoint_a = TrackEndpoint(track=track_a, end=TrackEnd.B)
    endpoint_b = TrackEndpoint(track=track_b, end=TrackEnd.A)
    endpoint_c = TrackEndpoint(track=track_c, end=TrackEnd.A)

    route_ab = JunctionRoute(from_endpoint=endpoint_a, to_endpoint=endpoint_b)
    route_ac = JunctionRoute(from_endpoint=endpoint_a, to_endpoint=endpoint_c)

    junction = Junction(
        name="JCT-TURNOUT",
        junction_type=JunctionType.TURNOUT,
        endpoints={endpoint_a, endpoint_b, endpoint_c},
        routes={route_ab, route_ac},
    )

    junction.align_route(endpoint_a, endpoint_b)

    assert junction.aligned_routes == {route_ab}
    assert junction.is_route_aligned(endpoint_a, endpoint_b) is True
    assert junction.is_route_aligned(endpoint_a, endpoint_c) is False

    junction.align_route(endpoint_a, endpoint_c)

    assert junction.aligned_routes == {route_ac}
    assert junction.is_route_aligned(endpoint_a, endpoint_b) is False
    assert junction.is_route_aligned(endpoint_a, endpoint_c) is True


def test_align_route_raises_when_route_does_not_exist():
    track_a = make_track("Main 1")
    track_b = make_track("Siding 1")
    track_c = make_track("Spur 1")

    endpoint_a = TrackEndpoint(track=track_a, end=TrackEnd.B)
    endpoint_b = TrackEndpoint(track=track_b, end=TrackEnd.A)
    endpoint_c = TrackEndpoint(track=track_c, end=TrackEnd.A)

    route_ab = JunctionRoute(from_endpoint=endpoint_a, to_endpoint=endpoint_b)

    junction = Junction(
        name="JCT-TURNOUT",
        junction_type=JunctionType.TURNOUT,
        endpoints={endpoint_a, endpoint_b, endpoint_c},
        routes={route_ab},
    )

    with pytest.raises(
        ValueError, match="No route exists between the requested endpoints"
    ):
        junction.align_route(endpoint_a, endpoint_c)


def test_clear_alignment_removes_all_aligned_routes():
    track_a = make_track("Main 1")
    track_b = make_track("Main 2")

    endpoint_a = TrackEndpoint(track=track_a, end=TrackEnd.B)
    endpoint_b = TrackEndpoint(track=track_b, end=TrackEnd.A)
    route = JunctionRoute(from_endpoint=endpoint_a, to_endpoint=endpoint_b)

    junction = Junction(
        name="JCT-1",
        junction_type=JunctionType.CONNECTION,
        endpoints={endpoint_a, endpoint_b},
        routes={route},
        aligned_routes={route},
    )

    junction.clear_alignment()

    assert junction.aligned_routes == set()


def test_connected_endpoints_for_returns_reachable_endpoints():
    track_a = make_track("Main 1")
    track_b = make_track("Siding 1")
    track_c = make_track("Spur 1")

    endpoint_a = TrackEndpoint(track=track_a, end=TrackEnd.B)
    endpoint_b = TrackEndpoint(track=track_b, end=TrackEnd.A)
    endpoint_c = TrackEndpoint(track=track_c, end=TrackEnd.A)

    route_ab = JunctionRoute(from_endpoint=endpoint_a, to_endpoint=endpoint_b)
    route_ac = JunctionRoute(from_endpoint=endpoint_a, to_endpoint=endpoint_c)

    junction = Junction(
        name="JCT-TURNOUT",
        junction_type=JunctionType.TURNOUT,
        endpoints={endpoint_a, endpoint_b, endpoint_c},
        routes={route_ab, route_ac},
    )

    connected = junction.connected_endpoints_for(endpoint_a)

    assert len(connected) == 2
    assert endpoint_b in connected
    assert endpoint_c in connected
