from __future__ import annotations

from railroad_sim.domain.enums import JunctionType, TrackEnd
from railroad_sim.domain.junction import Junction, JunctionRoute
from railroad_sim.domain.track import Track
from tests.support.track_builders import endpoint_a, endpoint_b


def make_route(
    from_track: Track,
    from_end: TrackEnd,
    to_track: Track,
    to_end: TrackEnd,
) -> JunctionRoute:
    from_endpoint = (
        endpoint_a(from_track) if from_end is TrackEnd.A else endpoint_b(from_track)
    )
    to_endpoint = endpoint_a(to_track) if to_end is TrackEnd.A else endpoint_b(to_track)

    return JunctionRoute(
        from_endpoint=from_endpoint,
        to_endpoint=to_endpoint,
    )


def make_junction(
    name: str,
    *,
    junction_type: JunctionType = JunctionType.CONNECTION,
    routes: set[JunctionRoute] | None = None,
    aligned_routes: set[JunctionRoute] | None = None,
) -> Junction:
    routes = routes or set()
    aligned_routes = aligned_routes or set()

    endpoints = set()
    for route in routes:
        endpoints.add(route.from_endpoint)
        endpoints.add(route.to_endpoint)

    return Junction(
        name=name,
        junction_type=junction_type,
        endpoints=endpoints,
        routes=routes,
        aligned_routes=aligned_routes,
    )


def make_connection_junction(
    name: str,
    left_track: Track,
    left_end: TrackEnd,
    right_track: Track,
    right_end: TrackEnd,
    *,
    aligned: bool = True,
) -> tuple[Junction, JunctionRoute]:
    route = make_route(
        from_track=left_track,
        from_end=left_end,
        to_track=right_track,
        to_end=right_end,
    )

    junction = make_junction(
        name=name,
        junction_type=JunctionType.CONNECTION,
        routes={route},
        aligned_routes={route} if aligned else set(),
    )

    return junction, route


def make_turnout_junction(
    name: str,
    trunk_track: Track,
    trunk_end: TrackEnd,
    route1_track: Track,
    route1_end: TrackEnd,
    route2_track: Track,
    route2_end: TrackEnd,
    *,
    align_to: int = 1,
) -> tuple[Junction, JunctionRoute, JunctionRoute]:
    route_1 = make_route(
        from_track=trunk_track,
        from_end=trunk_end,
        to_track=route1_track,
        to_end=route1_end,
    )

    route_2 = make_route(
        from_track=trunk_track,
        from_end=trunk_end,
        to_track=route2_track,
        to_end=route2_end,
    )

    if align_to == 1:
        aligned_routes = {route_1}
    elif align_to == 2:
        aligned_routes = {route_2}
    else:
        aligned_routes = set()

    junction = make_junction(
        name=name,
        junction_type=JunctionType.TURNOUT,
        routes={route_1, route_2},
        aligned_routes=aligned_routes,
    )

    return junction, route_1, route_2


def build_linear_connection_pair(
    left_track: Track,
    middle_track: Track,
    right_track: Track,
    *,
    align_left: bool = True,
    align_right: bool = True,
) -> tuple[Junction, Junction, JunctionRoute, JunctionRoute]:
    left_junction, left_route = make_connection_junction(
        name="J_LEFT",
        left_track=left_track,
        left_end=TrackEnd.B,
        right_track=middle_track,
        right_end=TrackEnd.A,
        aligned=align_left,
    )

    right_junction, right_route = make_connection_junction(
        name="J_RIGHT",
        left_track=middle_track,
        left_end=TrackEnd.B,
        right_track=right_track,
        right_end=TrackEnd.A,
        aligned=align_right,
    )

    return left_junction, right_junction, left_route, right_route
