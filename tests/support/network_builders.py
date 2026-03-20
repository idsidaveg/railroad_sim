from railroad_sim.domain.enums import JunctionType, TrackEnd
from railroad_sim.domain.junction import Junction, JunctionRoute, TrackEndpoint
from railroad_sim.domain.track import Track


def build_simple_turnout(
    name: str,
    from_track: Track,
    from_end: TrackEnd,
    to_track: Track,
    to_end: TrackEnd,
) -> Junction:
    """
    Build a minimal valid turnout-style junction between two tracks.
    """

    from_ep = TrackEndpoint(track=from_track, end=from_end)
    to_ep = TrackEndpoint(track=to_track, end=to_end)

    route = JunctionRoute(from_endpoint=from_ep, to_endpoint=to_ep)

    return Junction(
        name=name,
        junction_type=JunctionType.TURNOUT,  # <-- we'll fix this in a second
        endpoints={from_ep, to_ep},
        routes={route},
        aligned_routes={route},
    )
