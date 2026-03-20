from uuid import uuid4

import pytest
from railroad_sim.domain.yard.roundhouse import Roundhouse

from railroad_sim.domain.yard.facility_types import FacilityType


def test_roundhouse_creation_basic() -> None:
    turntable_id = uuid4()
    stall_1 = uuid4()
    stall_2 = uuid4()

    roundhouse = Roundhouse(
        name="Boise Roundhouse",
        facility_type=FacilityType.ROUNDHOUSE,
        turntable_id=turntable_id,
        stall_track_ids=(stall_1, stall_2),
        served_track_ids=(stall_1, stall_2),
        description="Primary locomotive storage and service facility",
    )

    assert roundhouse.name == "Boise Roundhouse"
    assert roundhouse.facility_type == FacilityType.ROUNDHOUSE
    assert roundhouse.turntable_id == turntable_id
    assert roundhouse.stall_track_ids == (stall_1, stall_2)
    assert roundhouse.served_track_ids == (stall_1, stall_2)
    assert roundhouse.description == "Primary locomotive storage and service facility"
    assert roundhouse.facility_id is not None


def test_roundhouse_rejects_blank_name() -> None:
    with pytest.raises(ValueError, match="facility name must not be blank"):
        Roundhouse(
            name="   ",
            facility_type=FacilityType.ROUNDHOUSE,
            turntable_id=uuid4(),
        )


def test_roundhouse_requires_roundhouse_facility_type() -> None:
    with pytest.raises(
        ValueError,
        match="must have facility_type=ROUNDHOUSE",
    ):
        Roundhouse(
            name="Not Really A Roundhouse",
            facility_type=FacilityType.REPAIR_SHOP,
            turntable_id=uuid4(),
        )


def test_roundhouse_has_stalls() -> None:
    stall = uuid4()

    roundhouse_with_stalls = Roundhouse(
        name="Roundhouse With Stalls",
        facility_type=FacilityType.ROUNDHOUSE,
        turntable_id=uuid4(),
        stall_track_ids=(stall,),
    )

    roundhouse_without_stalls = Roundhouse(
        name="Empty Roundhouse",
        facility_type=FacilityType.ROUNDHOUSE,
        turntable_id=uuid4(),
    )

    assert roundhouse_with_stalls.has_stalls() is True
    assert roundhouse_without_stalls.has_stalls() is False


def test_roundhouse_stall_count() -> None:
    stall_1 = uuid4()
    stall_2 = uuid4()
    stall_3 = uuid4()

    roundhouse = Roundhouse(
        name="Three Stall Roundhouse",
        facility_type=FacilityType.ROUNDHOUSE,
        turntable_id=uuid4(),
        stall_track_ids=(stall_1, stall_2, stall_3),
    )

    assert roundhouse.stall_count() == 3


def test_roundhouse_has_stall() -> None:
    stall_1 = uuid4()
    stall_2 = uuid4()

    roundhouse = Roundhouse(
        name="Test Roundhouse",
        facility_type=FacilityType.ROUNDHOUSE,
        turntable_id=uuid4(),
        stall_track_ids=(stall_1,),
    )

    assert roundhouse.has_stall(stall_1) is True
    assert roundhouse.has_stall(stall_2) is False


def test_roundhouse_rejects_duplicate_stall_track_ids() -> None:
    stall = uuid4()

    with pytest.raises(ValueError, match="duplicate stall_track_ids"):
        Roundhouse(
            name="Duplicate Stall Roundhouse",
            facility_type=FacilityType.ROUNDHOUSE,
            turntable_id=uuid4(),
            stall_track_ids=(stall, stall),
        )


def test_roundhouse_inherits_facility_served_track_behavior() -> None:
    served_track = uuid4()
    other_track = uuid4()

    roundhouse = Roundhouse(
        name="Served Track Roundhouse",
        facility_type=FacilityType.ROUNDHOUSE,
        turntable_id=uuid4(),
        stall_track_ids=(served_track,),
        served_track_ids=(served_track,),
    )

    assert roundhouse.has_served_tracks() is True
    assert roundhouse.serves_track(served_track) is True
    assert roundhouse.serves_track(other_track) is False
