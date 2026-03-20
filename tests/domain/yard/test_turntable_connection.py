import pytest

from railroad_sim.domain.enums import TrackEnd, TrackType
from railroad_sim.domain.track import Track
from railroad_sim.domain.yard.turntable import Turntable
from railroad_sim.domain.yard.turntable_connection import TurntableConnection

# -------------------------
# Helpers
# -------------------------


def build_track(name: str) -> Track:
    return Track(name=name, track_type=TrackType.MAINLINE, length_ft=100.0)


# -------------------------
# Tests
# -------------------------


def test_no_alignment_returns_none() -> None:
    bridge = build_track("bridge")
    approach = build_track("approach")

    tt = Turntable(
        name="TT",
        bridge_length_ft=100,
        bridge_track_id=bridge.track_id,
        approach_track_id=approach.track_id,
    )

    conn = TurntableConnection(
        turntable=tt,
        bridge_track=bridge,
        connected_tracks_by_id={
            approach.track_id: approach,
        },
    )

    assert conn.build_active_junction() is None


def test_alignment_to_approach_creates_junction_with_bridge_end_a() -> None:
    bridge = build_track("bridge")
    approach = build_track("approach")

    tt = Turntable(
        name="TT",
        bridge_length_ft=100,
        bridge_track_id=bridge.track_id,
        approach_track_id=approach.track_id,
    )

    tt.align_to(approach.track_id)

    conn = TurntableConnection(
        turntable=tt,
        bridge_track=bridge,
        connected_tracks_by_id={
            approach.track_id: approach,
        },
    )

    junction = conn.build_active_junction()

    assert junction is not None
    assert len(junction.routes) == 1

    route = next(iter(junction.routes))

    # Bridge should use TrackEnd.A for approach
    assert route.from_endpoint.track == bridge
    assert route.from_endpoint.end == TrackEnd.A

    assert route.to_endpoint.track == approach
    assert route.to_endpoint.end == TrackEnd.A


def test_alignment_to_stall_creates_junction_with_bridge_end_b() -> None:
    bridge = build_track("bridge")
    approach = build_track("approach")
    stall = build_track("stall")

    tt = Turntable(
        name="TT",
        bridge_length_ft=100,
        bridge_track_id=bridge.track_id,
        approach_track_id=approach.track_id,
        stall_track_ids=(stall.track_id,),
    )

    tt.align_to(stall.track_id)

    conn = TurntableConnection(
        turntable=tt,
        bridge_track=bridge,
        connected_tracks_by_id={
            approach.track_id: approach,
            stall.track_id: stall,
        },
    )

    junction = conn.build_active_junction()

    assert junction is not None
    assert len(junction.routes) == 1

    route = next(iter(junction.routes))

    # Bridge should use TrackEnd.B for stall
    assert route.from_endpoint.track == bridge
    assert route.from_endpoint.end == TrackEnd.B

    assert route.to_endpoint.track == stall
    assert route.to_endpoint.end == TrackEnd.A


def test_missing_aligned_track_in_lookup_raises() -> None:
    bridge = build_track("bridge")
    approach = build_track("approach")

    tt = Turntable(
        name="TT",
        bridge_length_ft=100,
        bridge_track_id=bridge.track_id,
        approach_track_id=approach.track_id,
    )

    tt.align_to(approach.track_id)

    conn = TurntableConnection(
        turntable=tt,
        bridge_track=bridge,
        connected_tracks_by_id={},  # missing
    )

    with pytest.raises(ValueError, match="not provided"):
        conn.build_active_junction()


def test_invalid_bridge_track_raises() -> None:
    bridge = build_track("bridge")
    wrong_bridge = build_track("wrong_bridge")
    approach = build_track("approach")

    tt = Turntable(
        name="TT",
        bridge_length_ft=100,
        bridge_track_id=bridge.track_id,
        approach_track_id=approach.track_id,
    )

    tt.align_to(approach.track_id)

    conn = TurntableConnection(
        turntable=tt,
        bridge_track=wrong_bridge,  # mismatch
        connected_tracks_by_id={
            approach.track_id: approach,
        },
    )

    with pytest.raises(ValueError, match="does not match"):
        conn.build_active_junction()


def test_alignment_lookup_returning_wrong_track_raises() -> None:
    bridge = build_track("bridge")
    approach = build_track("approach")
    other = build_track("other")

    tt = Turntable(
        name="TT",
        bridge_length_ft=100,
        bridge_track_id=bridge.track_id,
        approach_track_id=approach.track_id,
    )

    tt.align_to(approach.track_id)

    conn = TurntableConnection(
        turntable=tt,
        bridge_track=bridge,
        connected_tracks_by_id={
            approach.track_id: other,
        },
    )

    with pytest.raises(ValueError, match="not a connected track"):
        conn.build_active_junction()
