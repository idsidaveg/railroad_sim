from uuid import UUID, uuid4

import pytest

from railroad_sim.domain.consist import Consist
from railroad_sim.domain.enums import (
    MovementState,
    TrackCondition,
    TrackTrafficRule,
    TrackType,
    TravelDirection,
)
from railroad_sim.domain.rolling_stock import RollingStock
from railroad_sim.domain.track import Track, TrackOccupancy


def make_car(road_number: str) -> RollingStock:
    return RollingStock(reporting_mark="UP", road_number=road_number)


def make_consist(*road_numbers: str) -> Consist:
    cars = [make_car(number) for number in road_numbers]

    for left, right in zip(cars, cars[1:]):
        left.rear_coupler.connect(right.front_coupler)

    return Consist(anchor=cars[0])


def test_track_generates_track_id_by_default():
    track = Track(
        name="Yard 1",
        track_type=TrackType.YARD,
        length_ft=1000,
    )

    assert isinstance(track.track_id, UUID)


def test_track_accepts_explicit_track_id():
    explicit_id = uuid4()

    track = Track(
        name="Yard 1",
        track_type=TrackType.YARD,
        length_ft=1000,
        track_id=explicit_id,
    )

    assert track.track_id == explicit_id


def test_track_creation_with_required_fields():
    track = Track(
        name="Yard 1",
        track_type=TrackType.YARD,
        length_ft=1000,
    )

    assert track.name == "Yard 1"
    assert track.track_type == TrackType.YARD
    assert track.length_ft == 1000
    assert track.condition == TrackCondition.CLEAR
    assert track.traffic_rule == TrackTrafficRule.BIDIRECTIONAL
    assert track.occupancies == []


def test_track_creation_rejects_blank_name():
    with pytest.raises(ValueError, match="track name must not be blank"):
        Track(
            name="   ",
            track_type=TrackType.YARD,
            length_ft=1000,
        )


def test_track_creation_rejects_non_positive_length():
    with pytest.raises(ValueError, match="length_ft must be > 0"):
        Track(
            name="Yard 1",
            track_type=TrackType.YARD,
            length_ft=0,
        )


def test_track_is_not_occupied_when_empty():
    track = Track(
        name="Main 1",
        track_type=TrackType.MAINLINE,
        length_ft=5000,
    )

    assert track.is_occupied() is False
    assert track.active_consists() == []


def test_track_is_occupied_when_occupancy_present():
    consist = make_consist("1001", "1002")
    occupancy = TrackOccupancy(
        consist=consist,
        rear_offset_ft=100,
        front_offset_ft=220,
    )
    track = Track(
        name="Main 1",
        track_type=TrackType.MAINLINE,
        length_ft=5000,
        occupancies=[occupancy],
    )

    assert track.is_occupied() is True
    assert track.active_consists() == [consist]


def test_track_is_available_when_not_out_of_service():
    track = Track(
        name="Siding A",
        track_type=TrackType.SIDING,
        length_ft=1500,
        condition=TrackCondition.DAMAGED,
    )

    assert track.is_available() is True


def test_track_is_not_available_when_out_of_service():
    track = Track(
        name="Siding A",
        track_type=TrackType.SIDING,
        length_ft=1500,
        condition=TrackCondition.OUT_OF_SERVICE,
    )

    assert track.is_available() is False


def test_track_occupancy_creation_accepts_stationary_occupancy():
    consist = make_consist("1001")
    occupancy = TrackOccupancy(
        consist=consist,
        rear_offset_ft=0,
        front_offset_ft=60,
        travel_direction=TravelDirection.STATIONARY,
        speed_mph=0,
        movement_state=MovementState.STATIONARY,
    )

    assert occupancy.length_ft == 60


def test_track_occupancy_rejects_negative_rear_offset():
    consist = make_consist("1001")

    with pytest.raises(ValueError, match="rear_offset_ft must be >= 0"):
        TrackOccupancy(
            consist=consist,
            rear_offset_ft=-1,
            front_offset_ft=60,
        )


def test_track_occupancy_rejects_front_less_than_rear():
    consist = make_consist("1001")

    with pytest.raises(ValueError, match="rear_offset_ft must be <= front_offset_ft"):
        TrackOccupancy(
            consist=consist,
            rear_offset_ft=100,
            front_offset_ft=50,
        )


def test_track_occupancy_rejects_negative_speed():
    consist = make_consist("1001")

    with pytest.raises(ValueError, match="speed_mph must be >= 0"):
        TrackOccupancy(
            consist=consist,
            rear_offset_ft=0,
            front_offset_ft=60,
            travel_direction=TravelDirection.TOWARD_B,
            speed_mph=-5,
            movement_state=MovementState.MOVING,
        )


def test_track_occupancy_rejects_stationary_movement_with_nonzero_speed():
    consist = make_consist("1001")

    with pytest.raises(
        ValueError, match="stationary occupancy must have speed_mph == 0"
    ):
        TrackOccupancy(
            consist=consist,
            rear_offset_ft=0,
            front_offset_ft=60,
            travel_direction=TravelDirection.STATIONARY,
            speed_mph=5,
            movement_state=MovementState.STATIONARY,
        )


def test_add_occupancy_adds_record_and_can_be_found():
    consist = make_consist("1001", "1002")
    occupancy = TrackOccupancy(
        consist=consist,
        rear_offset_ft=200,
        front_offset_ft=320,
    )
    track = Track(
        name="Yard 2",
        track_type=TrackType.YARD,
        length_ft=1000,
    )

    track.add_occupancy(occupancy)

    assert track.is_occupied() is True
    assert track.occupancy_for(consist) is occupancy
    assert track.active_consists() == [consist]


def test_add_occupancy_rejects_duplicate_consist():
    consist = make_consist("1001", "1002")
    first = TrackOccupancy(
        consist=consist,
        rear_offset_ft=0,
        front_offset_ft=120,
    )
    second = TrackOccupancy(
        consist=consist,
        rear_offset_ft=200,
        front_offset_ft=320,
    )
    track = Track(
        name="Yard 2",
        track_type=TrackType.YARD,
        length_ft=1000,
    )

    track.add_occupancy(first)

    with pytest.raises(ValueError, match="Consist already has an occupancy"):
        track.add_occupancy(second)


def test_add_occupancy_rejects_range_beyond_track_length():
    consist = make_consist("1001")
    occupancy = TrackOccupancy(
        consist=consist,
        rear_offset_ft=900,
        front_offset_ft=1100,
    )
    track = Track(
        name="Yard 3",
        track_type=TrackType.YARD,
        length_ft=1000,
    )

    with pytest.raises(
        ValueError, match="front_offset_ft 1100 exceeds track length 1000"
    ):
        track.add_occupancy(occupancy)


def test_remove_occupancy_removes_record():
    consist = make_consist("1001", "1002")
    occupancy = TrackOccupancy(
        consist=consist,
        rear_offset_ft=100,
        front_offset_ft=220,
    )
    track = Track(
        name="Yard 4",
        track_type=TrackType.YARD,
        length_ft=1000,
        occupancies=[occupancy],
    )

    track.remove_occupancy(consist)

    assert track.is_occupied() is False
    assert track.occupancy_for(consist) is None
    assert track.active_consists() == []


def test_remove_occupancy_raises_for_missing_consist():
    consist_on_track = make_consist("1001")
    other_consist = make_consist("2001")

    occupancy = TrackOccupancy(
        consist=consist_on_track,
        rear_offset_ft=100,
        front_offset_ft=160,
    )
    track = Track(
        name="Yard 4",
        track_type=TrackType.YARD,
        length_ft=1000,
        occupancies=[occupancy],
    )

    with pytest.raises(ValueError, match="Consist not found on track"):
        track.remove_occupancy(other_consist)


def test_has_overlapping_occupancies_detects_overlap():
    consist_a = make_consist("1001")
    consist_b = make_consist("1002")

    occupancy_a = TrackOccupancy(
        consist=consist_a,
        rear_offset_ft=100,
        front_offset_ft=200,
    )
    occupancy_b = TrackOccupancy(
        consist=consist_b,
        rear_offset_ft=150,
        front_offset_ft=250,
    )
    track = Track(
        name="Main 2",
        track_type=TrackType.MAINLINE,
        length_ft=5000,
        occupancies=[occupancy_a, occupancy_b],
    )

    assert track.has_overlapping_occupancies() is True


def test_has_overlapping_occupancies_returns_false_when_ranges_only_touch():
    consist_a = make_consist("1001")
    consist_b = make_consist("1002")

    occupancy_a = TrackOccupancy(
        consist=consist_a,
        rear_offset_ft=100,
        front_offset_ft=200,
    )
    occupancy_b = TrackOccupancy(
        consist=consist_b,
        rear_offset_ft=200,
        front_offset_ft=300,
    )
    track = Track(
        name="Main 2",
        track_type=TrackType.MAINLINE,
        length_ft=5000,
        occupancies=[occupancy_a, occupancy_b],
    )

    assert track.has_overlapping_occupancies() is False


def test_has_opposing_movements_detects_conflict():
    consist_a = make_consist("1001")
    consist_b = make_consist("1002")

    occupancy_a = TrackOccupancy(
        consist=consist_a,
        rear_offset_ft=100,
        front_offset_ft=200,
        travel_direction=TravelDirection.TOWARD_A,
        speed_mph=10,
        movement_state=MovementState.MOVING,
    )
    occupancy_b = TrackOccupancy(
        consist=consist_b,
        rear_offset_ft=300,
        front_offset_ft=400,
        travel_direction=TravelDirection.TOWARD_B,
        speed_mph=12,
        movement_state=MovementState.MOVING,
    )
    track = Track(
        name="Main 3",
        track_type=TrackType.MAINLINE,
        length_ft=5000,
        occupancies=[occupancy_a, occupancy_b],
    )

    assert track.has_opposing_movements() is True


def test_has_opposing_movements_returns_false_for_same_direction():
    consist_a = make_consist("1001")
    consist_b = make_consist("1002")

    occupancy_a = TrackOccupancy(
        consist=consist_a,
        rear_offset_ft=100,
        front_offset_ft=200,
        travel_direction=TravelDirection.TOWARD_B,
        speed_mph=10,
        movement_state=MovementState.MOVING,
    )
    occupancy_b = TrackOccupancy(
        consist=consist_b,
        rear_offset_ft=300,
        front_offset_ft=400,
        travel_direction=TravelDirection.TOWARD_B,
        speed_mph=12,
        movement_state=MovementState.MOVING,
    )
    track = Track(
        name="Main 3",
        track_type=TrackType.MAINLINE,
        length_ft=5000,
        occupancies=[occupancy_a, occupancy_b],
    )

    assert track.has_opposing_movements() is False


def test_supports_direction_respects_traffic_rule():
    track = Track(
        name="Main East",
        track_type=TrackType.MAINLINE,
        length_ft=5000,
        traffic_rule=TrackTrafficRule.A_TO_B_ONLY,
    )

    assert track.supports_direction(TravelDirection.TOWARD_B) is True
    assert track.supports_direction(TravelDirection.TOWARD_A) is False
    assert track.supports_direction(TravelDirection.STATIONARY) is True
