from uuid import uuid4

import pytest

from railroad_sim.domain.yard.facility import Facility
from railroad_sim.domain.yard.facility_types import FacilityType


def test_facility_creation_basic() -> None:
    track_id = uuid4()

    facility = Facility(
        name="Freight House",
        facility_type=FacilityType.FREIGHT_HOUSE,
        served_track_ids=(track_id,),
        description="Primary freight handling building",
    )

    assert facility.name == "Freight House"
    assert facility.facility_type == FacilityType.FREIGHT_HOUSE
    assert facility.served_track_ids == (track_id,)
    assert facility.description == "Primary freight handling building"
    assert facility.facility_id is not None


def test_facility_rejects_blank_name() -> None:
    with pytest.raises(ValueError, match="facility name must not be blank"):
        Facility(
            name="   ",
            facility_type=FacilityType.OFFICE,
        )


def test_facility_serves_track() -> None:
    track_id = uuid4()

    facility = Facility(
        name="Depot",
        facility_type=FacilityType.DEPOT,
        served_track_ids=(track_id,),
    )

    assert facility.serves_track(track_id) is True
    assert facility.serves_track(uuid4()) is False


def test_facility_has_served_tracks() -> None:
    facility_with_tracks = Facility(
        name="Warehouse",
        facility_type=FacilityType.WAREHOUSE,
        served_track_ids=(uuid4(),),
    )

    facility_without_tracks = Facility(
        name="Office",
        facility_type=FacilityType.OFFICE,
    )

    assert facility_with_tracks.has_served_tracks() is True
    assert facility_without_tracks.has_served_tracks() is False


def test_facility_rejects_duplicate_track_ids() -> None:
    track_id = uuid4()

    with pytest.raises(ValueError, match="duplicate served_track_ids"):
        Facility(
            name="Duplicate Tracks",
            facility_type=FacilityType.INDUSTRY,
            served_track_ids=(track_id, track_id),
        )
