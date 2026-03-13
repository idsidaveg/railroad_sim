from __future__ import annotations

from railroad_sim.domain.enums import (
    TrackCondition,
    TrackEnd,
    TrackTrafficRule,
    TrackType,
)
from railroad_sim.domain.junction import TrackEndpoint
from railroad_sim.domain.track import Track


def make_track(
    name: str = "Track A",
    *,
    length_ft: float = 1000.0,
    track_type: TrackType = TrackType.MAINLINE,
    condition: TrackCondition = TrackCondition.CLEAR,
    traffic_rule: TrackTrafficRule = TrackTrafficRule.BIDIRECTIONAL,
) -> Track:
    """
    Build a Track object with the same defaults used across existing tests.
    """
    return Track(
        name=name,
        track_type=track_type,
        length_ft=length_ft,
        condition=condition,
        traffic_rule=traffic_rule,
    )


def make_track_pair(
    left_name: str = "Track A",
    right_name: str = "Track B",
    *,
    length_ft: float = 1000.0,
    track_type: TrackType = TrackType.MAINLINE,
    condition: TrackCondition = TrackCondition.CLEAR,
    traffic_rule: TrackTrafficRule = TrackTrafficRule.BIDIRECTIONAL,
) -> tuple[Track, Track]:
    """
    Build two independent tracks.
    """
    left = make_track(
        name=left_name,
        length_ft=length_ft,
        track_type=track_type,
        condition=condition,
        traffic_rule=traffic_rule,
    )

    right = make_track(
        name=right_name,
        length_ft=length_ft,
        track_type=track_type,
        condition=condition,
        traffic_rule=traffic_rule,
    )

    return left, right


def endpoint_a(track: Track) -> TrackEndpoint:
    """
    Return the A-end endpoint for a track.
    """
    return TrackEndpoint(track=track, end=TrackEnd.A)


def endpoint_b(track: Track) -> TrackEndpoint:
    """
    Return the B-end endpoint for a track.
    """
    return TrackEndpoint(track=track, end=TrackEnd.B)


def make_linear_track_chain(*names: str) -> tuple[Track, ...]:
    """
    Build a sequence of independent tracks.

    Example:
        make_linear_track_chain("A", "B", "C")
    """
    return tuple(make_track(name=name) for name in names)
