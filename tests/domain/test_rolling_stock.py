from datetime import date, datetime, timezone
from uuid import UUID, uuid4

import pytest

from railroad_sim.domain.enums import (
    CouplerPosition,
    MaintenanceStatus,
    RollingStockCondition,
    RollingStockEventType,
)
from railroad_sim.domain.rolling_stock import RollingStock


def make_car(
    reporting_mark: str = "UP",
    road_number: str = "1001",
) -> RollingStock:
    return RollingStock(reporting_mark=reporting_mark, road_number=road_number)


def test_rolling_stock_creates_with_uuid_and_couplers():
    car = make_car()

    assert isinstance(car.asset_id, UUID)
    assert car.reporting_mark == "UP"
    assert car.road_number == "1001"

    assert car.front_coupler.position is CouplerPosition.FRONT
    assert car.rear_coupler.position is CouplerPosition.REAR

    assert car.front_coupler.owner is car
    assert car.rear_coupler.owner is car

    assert car.front_coupler is not car.rear_coupler
    assert car.front_coupler.connected_to is None
    assert car.rear_coupler.connected_to is None


def test_rolling_stock_uses_explicit_created_at_for_created_event():
    created_at = datetime(2025, 1, 1, 10, 30, tzinfo=timezone.utc)

    car = RollingStock(
        reporting_mark="UP",
        road_number="1001",
        created_at_value=created_at,
    )

    event = car.event_history[0]
    assert event.event_type is RollingStockEventType.CREATED
    assert event.occurred_at == created_at


def test_event_sequence_increments_across_multiple_operations():
    car = make_car()

    car.rename_equipment("BNSF", "2002")
    car.mark_damaged(details="Side damage from debris.")
    car.release_to_service(details="Repairs completed.")

    assert [event.sequence for event in car.event_history] == [1, 2, 3, 4]
    assert [event.event_type for event in car.event_history] == [
        RollingStockEventType.CREATED,
        RollingStockEventType.RENAMED,
        RollingStockEventType.DAMAGED,
        RollingStockEventType.RELEASED_TO_SERVICE,
    ]


def test_mark_damaged_without_explicit_time_records_timezone_aware_timestamp():
    car = make_car()

    car.mark_damaged()

    event = car.event_history[-1]
    assert event.event_type is RollingStockEventType.DAMAGED
    assert event.occurred_at.tzinfo is not None


def test_rolling_stock_accepts_optional_owner():
    car = RollingStock(reporting_mark="UP", road_number="1001", owner="Union Pacific")

    assert car.owner == "Union Pacific"


def test_complete_maintenance_resets_overdue_status_to_none():
    car = make_car()
    car.maintenance_status = MaintenanceStatus.OVERDUE

    car.complete_maintenance()

    assert car.maintenance_status is MaintenanceStatus.NONE


def test_rolling_stock_accepts_explicit_asset_id():
    known_id = uuid4()

    car = RollingStock(
        reporting_mark="BNSF",
        road_number="778901",
        asset_id_value=known_id,
    )

    assert car.asset_id == known_id


def test_asset_id_is_read_only_after_creation():
    car = make_car()

    with pytest.raises(AttributeError):
        setattr(car, "asset_id", uuid4())


def test_equipment_id_returns_reporting_mark_and_road_number():
    car = RollingStock(reporting_mark="BNSF", road_number="778901")

    assert car.equipment_id == "BNSF 778901"


def test_reporting_mark_is_normalized_to_uppercase_and_trimmed():
    car = make_car()

    assert car.reporting_mark == "UP"


def test_road_number_is_trimmed():
    car = make_car()

    assert car.road_number == "1001"


def test_empty_reporting_mark_raises_error():
    with pytest.raises(ValueError):
        RollingStock(reporting_mark="   ", road_number="1001")


def test_empty_road_number_raises_error():
    with pytest.raises(ValueError):
        RollingStock(reporting_mark="UP", road_number="   ")


def test_rolling_stock_defaults_to_in_service_and_no_maintenance():
    car = make_car()

    assert car.condition is RollingStockCondition.IN_SERVICE
    assert car.maintenance_status is MaintenanceStatus.NONE
    assert car.inspection_due_miles is None
    assert car.inspection_due_date is None
    assert car.restricted_from_service is False


def test_rolling_stock_records_created_event_on_initialization():
    car = make_car()

    assert len(car.event_history) == 1

    event = car.event_history[0]
    assert event.sequence == 1
    assert event.event_type is RollingStockEventType.CREATED
    assert event.details == "Rolling stock created."
    assert event.location is None
    assert event.related_train_id is None
    assert event.occurred_at.tzinfo is not None


def test_event_history_is_read_only_tuple():
    car = make_car()

    assert isinstance(car.event_history, tuple)

    with pytest.raises(AttributeError):
        car.event_history.append("bad")  # type: ignore[attr-defined]


def test_rename_equipment_updates_visible_identifier_but_not_asset_id():
    car = make_car()
    original_asset_id = car.asset_id

    car.rename_equipment("BNSF", "2002")

    assert car.asset_id == original_asset_id
    assert car.reporting_mark == "BNSF"
    assert car.road_number == "2002"
    assert car.equipment_id == "BNSF 2002"


def test_rename_equipment_normalizes_values():
    car = make_car()

    car.rename_equipment("  csxt ", " 3003 ")

    assert car.reporting_mark == "CSXT"
    assert car.road_number == "3003"


def test_rename_equipment_records_event_when_identifier_changes():
    car = make_car()

    car.rename_equipment("BNSF", "2002")

    assert len(car.event_history) == 2

    event = car.event_history[-1]
    assert event.sequence == 2
    assert event.event_type is RollingStockEventType.RENAMED
    assert event.details == "Renamed from UP 1001 to BNSF 2002."
    assert event.location is None
    assert event.related_train_id is None


def test_rename_equipment_does_not_record_event_when_identifier_does_not_change():
    car = make_car()

    car.rename_equipment(" up ", " 1001 ")

    assert car.reporting_mark == "UP"
    assert car.road_number == "1001"
    assert len(car.event_history) == 1
    assert car.event_history[0].event_type is RollingStockEventType.CREATED


def test_rename_equipment_rejects_empty_reporting_mark():
    car = make_car()

    with pytest.raises(ValueError):
        car.rename_equipment("   ", "3003")


def test_rename_equipment_rejects_empty_road_number():
    car = make_car()

    with pytest.raises(ValueError):
        car.rename_equipment("BNSF", "   ")


def test_is_serviceable_true_when_in_service_and_unrestricted():
    car = make_car()

    assert car.is_serviceable is True


def test_is_serviceable_false_when_restricted_from_service():
    car = make_car()
    car.restricted_from_service = True

    assert car.is_serviceable is False


def test_is_serviceable_false_when_not_in_service_condition():
    car = make_car()
    car.condition = RollingStockCondition.DAMAGED

    assert car.is_serviceable is False


def test_is_serviceable_false_when_maintenance_is_overdue():
    car = make_car()
    car.maintenance_status = MaintenanceStatus.OVERDUE

    assert car.is_serviceable is False


def test_can_complete_trip_returns_true_when_serviceable_and_no_due_limit():
    car = make_car()

    assert car.can_complete_trip(200) is True


def test_can_complete_trip_returns_false_when_not_serviceable():
    car = make_car()
    car.restricted_from_service = True

    assert car.can_complete_trip(200) is False


def test_can_complete_trip_returns_false_when_inspection_due_before_trip_distance():
    car = make_car()
    car.inspection_due_miles = 50

    assert car.can_complete_trip(200) is False


def test_can_complete_trip_allows_trip_when_due_miles_equals_trip_distance():
    car = make_car()
    car.inspection_due_miles = 200

    assert car.can_complete_trip(200) is True


def test_can_complete_trip_rejects_negative_distance():
    car = make_car()

    with pytest.raises(ValueError):
        car.can_complete_trip(-1)


def test_mark_damaged_updates_state_and_records_event():
    car = make_car()
    occurred_at = datetime(2026, 3, 9, 12, 0, tzinfo=timezone.utc)

    car.mark_damaged(
        occurred_at=occurred_at,
        details="Rockslide impact to side panels.",
        location="MP 44.2",
        related_train_id="M-101",
    )

    assert car.condition is RollingStockCondition.DAMAGED
    assert car.restricted_from_service is True
    assert len(car.event_history) == 2

    event = car.event_history[-1]
    assert event.sequence == 2
    assert event.event_type is RollingStockEventType.DAMAGED
    assert event.occurred_at == occurred_at
    assert event.details == "Rockslide impact to side panels."
    assert event.location == "MP 44.2"
    assert event.related_train_id == "M-101"


def test_mark_bad_order_updates_state_and_records_event():
    car = make_car()
    occurred_at = datetime(2026, 3, 9, 12, 30, tzinfo=timezone.utc)

    car.mark_bad_order(
        occurred_at=occurred_at,
        details="Wheel defect found during inspection.",
        location="East Yard",
        related_train_id="M-102",
    )

    assert car.condition is RollingStockCondition.BAD_ORDER
    assert car.restricted_from_service is True
    assert len(car.event_history) == 2

    event = car.event_history[-1]
    assert event.sequence == 2
    assert event.event_type is RollingStockEventType.BAD_ORDERED
    assert event.occurred_at == occurred_at
    assert event.details == "Wheel defect found during inspection."
    assert event.location == "East Yard"
    assert event.related_train_id == "M-102"


def test_schedule_maintenance_updates_state_and_records_event():
    car = make_car()
    occurred_at = datetime(2026, 3, 9, 13, 0, tzinfo=timezone.utc)
    due_date = date(2026, 3, 15)

    car.schedule_maintenance(
        occurred_at=occurred_at,
        details="Scheduled brake inspection.",
        location="Boise Yard",
        due_miles=50,
        due_date=due_date,
    )

    assert car.maintenance_status is MaintenanceStatus.SCHEDULED
    assert car.inspection_due_miles == 50
    assert car.inspection_due_date == due_date
    assert len(car.event_history) == 2

    event = car.event_history[-1]
    assert event.sequence == 2
    assert event.event_type is RollingStockEventType.MAINTENANCE_SCHEDULED
    assert event.occurred_at == occurred_at
    assert event.details == "Scheduled brake inspection."
    assert event.location == "Boise Yard"
    assert event.related_train_id is None


def test_schedule_maintenance_rejects_negative_due_miles():
    car = make_car()

    with pytest.raises(ValueError):
        car.schedule_maintenance(due_miles=-10)


def test_complete_maintenance_clears_due_flags_by_default_and_records_event():
    car = make_car()
    car.schedule_maintenance(due_miles=50, due_date=date(2026, 3, 15))
    occurred_at = datetime(2026, 3, 10, 9, 0, tzinfo=timezone.utc)

    car.complete_maintenance(
        occurred_at=occurred_at,
        details="Brake inspection completed.",
        location="Boise Shop",
    )

    assert car.maintenance_status is MaintenanceStatus.NONE
    assert car.inspection_due_miles is None
    assert car.inspection_due_date is None

    event = car.event_history[-1]
    assert event.event_type is RollingStockEventType.MAINTENANCE_COMPLETED
    assert event.occurred_at == occurred_at
    assert event.details == "Brake inspection completed."
    assert event.location == "Boise Shop"


def test_complete_maintenance_can_preserve_due_flags_when_requested():
    car = make_car()
    due_date = date(2026, 3, 15)
    car.schedule_maintenance(due_miles=50, due_date=due_date)

    car.complete_maintenance(clear_due_flags=False)

    assert car.maintenance_status is MaintenanceStatus.NONE
    assert car.inspection_due_miles == 50
    assert car.inspection_due_date == due_date


def test_release_to_service_restores_in_service_and_clears_restriction():
    car = make_car()
    car.mark_damaged()

    car.release_to_service(
        details="Repairs completed and cleared for service.",
        location="Boise Shop",
    )

    assert car.condition is RollingStockCondition.IN_SERVICE
    assert car.restricted_from_service is False

    event = car.event_history[-1]
    assert event.event_type is RollingStockEventType.RELEASED_TO_SERVICE
    assert event.details == "Repairs completed and cleared for service."
    assert event.location == "Boise Shop"


def test_release_to_service_clears_overdue_maintenance_status():
    car = make_car()
    car.maintenance_status = MaintenanceStatus.OVERDUE

    car.release_to_service()

    assert car.maintenance_status is MaintenanceStatus.NONE


def test_assign_to_train_records_event():
    car = make_car()
    occurred_at = datetime(2026, 3, 9, 14, 0, tzinfo=timezone.utc)

    car.assign_to_train(
        "M-101",
        occurred_at=occurred_at,
        details="Assigned for westbound manifest service.",
        location="Nampa Yard",
    )

    event = car.event_history[-1]
    assert event.event_type is RollingStockEventType.ASSIGNED_TO_TRAIN
    assert event.occurred_at == occurred_at
    assert event.details == "Assigned for westbound manifest service."
    assert event.location == "Nampa Yard"
    assert event.related_train_id == "M-101"


def test_assign_to_train_rejects_empty_train_id():
    car = make_car()

    with pytest.raises(ValueError):
        car.assign_to_train("   ")


def test_remove_from_train_records_event():
    car = make_car()
    occurred_at = datetime(2026, 3, 9, 15, 0, tzinfo=timezone.utc)

    car.remove_from_train(
        "M-101",
        occurred_at=occurred_at,
        details="Removed for local delivery.",
        location="Caldwell Spur",
    )

    event = car.event_history[-1]
    assert event.event_type is RollingStockEventType.REMOVED_FROM_TRAIN
    assert event.occurred_at == occurred_at
    assert event.details == "Removed for local delivery."
    assert event.location == "Caldwell Spur"
    assert event.related_train_id == "M-101"


def test_remove_from_train_rejects_empty_train_id():
    car = make_car()

    with pytest.raises(ValueError):
        car.remove_from_train("   ")


def test_repr_uses_equipment_id():
    car = make_car()
    assert repr(car) == "RollingStock(UP 1001)"
