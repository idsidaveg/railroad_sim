from unittest.mock import Mock
from uuid import uuid4

import pytest

from railroad_sim.domain.enums import TravelDirection
from railroad_sim.domain.network.position_types import ConsistExtent, NetworkPosition
from railroad_sim.domain.yard.turntable import Turntable


def test_turntable_creation_basic() -> None:
    bridge = uuid4()
    approach = uuid4()
    stall = uuid4()
    service = uuid4()

    tt = Turntable(
        name="Main Turntable",
        bridge_length_ft=100.0,
        bridge_track_id=bridge,
        approach_track_id=approach,
        stall_track_ids=(stall,),
        service_track_ids=(service,),
    )

    assert tt.name == "Main Turntable"
    assert tt.bridge_length_ft == 100.0
    assert tt.bridge_track_id == bridge
    assert tt.approach_track_id == approach
    assert stall in tt.stall_track_ids
    assert service in tt.service_track_ids
    assert tt.aligned_track_id is None


def test_turntable_rejects_blank_name() -> None:
    with pytest.raises(ValueError, match="turntable name must not be blank"):
        Turntable(
            name="   ",
            bridge_length_ft=100.0,
            bridge_track_id=uuid4(),
            approach_track_id=uuid4(),
        )


def test_turntable_rejects_invalid_bridge_length() -> None:
    with pytest.raises(ValueError, match="bridge_length_ft must be > 0"):
        Turntable(
            name="Bad Turntable",
            bridge_length_ft=0,
            bridge_track_id=uuid4(),
            approach_track_id=uuid4(),
        )


def test_turntable_connected_tracks_property() -> None:
    bridge = uuid4()
    approach = uuid4()
    stall = uuid4()
    service = uuid4()

    tt = Turntable(
        name="TT",
        bridge_length_ft=80,
        bridge_track_id=bridge,
        approach_track_id=approach,
        stall_track_ids=(stall,),
        service_track_ids=(service,),
    )

    connected = tt.connected_track_ids

    assert bridge not in connected
    assert approach in connected
    assert stall in connected
    assert service in connected
    assert len(connected) == 3


def test_turntable_all_track_ids_includes_bridge() -> None:
    bridge = uuid4()
    approach = uuid4()
    stall = uuid4()

    tt = Turntable(
        name="TT",
        bridge_length_ft=80,
        bridge_track_id=bridge,
        approach_track_id=approach,
        stall_track_ids=(stall,),
    )

    all_tracks = tt.all_track_ids

    assert bridge in all_tracks
    assert approach in all_tracks
    assert stall in all_tracks
    assert len(all_tracks) == 3


def test_turntable_can_align_to() -> None:
    bridge = uuid4()
    approach = uuid4()
    stall = uuid4()

    tt = Turntable(
        name="TT",
        bridge_length_ft=80,
        bridge_track_id=bridge,
        approach_track_id=approach,
        stall_track_ids=(stall,),
    )

    assert tt.can_align_to(approach) is True
    assert tt.can_align_to(stall) is True
    assert tt.can_align_to(bridge) is False
    assert tt.can_align_to(uuid4()) is False


def test_turntable_align_and_clear() -> None:
    bridge = uuid4()
    approach = uuid4()
    stall = uuid4()

    tt = Turntable(
        name="TT",
        bridge_length_ft=80,
        bridge_track_id=bridge,
        approach_track_id=approach,
        stall_track_ids=(stall,),
    )

    tt.align_to(stall)
    assert tt.aligned_track_id == stall
    assert tt.is_aligned_to(stall) is True

    tt.clear_alignment()
    assert tt.aligned_track_id is None


def test_turntable_align_to_allows_rotation_when_protected_extent_is_fully_on_bridge() -> (
    None
):
    bridge_id = uuid4()
    approach_id = uuid4()
    stall_id = uuid4()

    tt = Turntable(
        name="TT",
        bridge_length_ft=100.0,
        bridge_track_id=bridge_id,
        approach_track_id=approach_id,
        stall_track_ids=(stall_id,),
    )

    extent = ConsistExtent(
        consist=Mock(),
        rear_position=NetworkPosition(
            track_id=bridge_id,
            offset_ft=10.0,
        ),
        front_position=NetworkPosition(
            track_id=bridge_id,
            offset_ft=90.0,
        ),
        travel_direction=TravelDirection.TOWARD_B,
    )

    tt.align_to(stall_id, protected_extent=extent)

    assert tt.aligned_track_id == stall_id


def test_turntable_align_to_rejects_rotation_when_protected_extent_is_not_fully_on_bridge() -> (
    None
):
    bridge_id = uuid4()
    approach_id = uuid4()
    stall_id = uuid4()

    tt = Turntable(
        name="TT",
        bridge_length_ft=100.0,
        bridge_track_id=bridge_id,
        approach_track_id=approach_id,
        stall_track_ids=(stall_id,),
    )

    extent = ConsistExtent(
        consist=Mock(),
        rear_position=NetworkPosition(
            track_id=bridge_id,
            offset_ft=10.0,
        ),
        front_position=NetworkPosition(
            track_id=approach_id,
            offset_ft=90.0,
        ),
        travel_direction=TravelDirection.TOWARD_B,
    )

    with pytest.raises(ValueError, match="fully on the bridge"):
        tt.align_to(stall_id, protected_extent=extent)

    assert tt.aligned_track_id is None


def test_turntable_rejects_invalid_alignment() -> None:
    tt = Turntable(
        name="TT",
        bridge_length_ft=80,
        bridge_track_id=uuid4(),
        approach_track_id=uuid4(),
    )

    with pytest.raises(ValueError, match="not connected to turntable"):
        tt.align_to(uuid4())


def test_turntable_rejects_duplicate_track_ids() -> None:
    bridge = uuid4()
    approach = uuid4()
    shared = uuid4()

    with pytest.raises(ValueError, match="duplicate track ids"):
        Turntable(
            name="TT",
            bridge_length_ft=80,
            bridge_track_id=bridge,
            approach_track_id=approach,
            stall_track_ids=(shared, shared),
        )


def test_turntable_rejects_bridge_track_id_matching_approach() -> None:
    shared = uuid4()

    with pytest.raises(ValueError, match="bridge_track_id must be distinct"):
        Turntable(
            name="TT",
            bridge_length_ft=80,
            bridge_track_id=shared,
            approach_track_id=shared,
        )


def test_turntable_rejects_invalid_initial_alignment() -> None:
    bridge = uuid4()
    approach = uuid4()
    stall = uuid4()

    with pytest.raises(ValueError, match="aligned_track_id"):
        Turntable(
            name="TT",
            bridge_length_ft=80,
            bridge_track_id=bridge,
            approach_track_id=approach,
            stall_track_ids=(stall,),
            aligned_track_id=uuid4(),
        )
