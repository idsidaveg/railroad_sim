from datetime import datetime, timezone

from railroad_sim.domain.consist import Consist
from railroad_sim.domain.enums import (
    EventSeverity,
    RollingStockCondition,
    RollingStockEventType,
    TrainEventType,
    TrainStatus,
)
from railroad_sim.domain.incident_service import IncidentService
from railroad_sim.domain.train import Train
from tests.support.rolling_stock_builders import make_car


def make_consist() -> Consist:
    return Consist(anchor=make_car())


def make_train_with_consist() -> Train:
    return Train(
        train_id="train-001",
        symbol="M-101",
        current_consist=make_consist(),
    )


def test_derailment_records_asset_and_train_events_and_stops_train():
    service = IncidentService()
    train = make_train_with_consist()
    car = make_car("BNSF", "2002")
    occurred_at = datetime(2026, 3, 21, 10, 0, tzinfo=timezone.utc)

    outcome = service.report_asset_incident(
        train=train,
        asset=car,
        asset_event_type=RollingStockEventType.DERAILED,
        severity=EventSeverity.CRITICAL,
        occurred_at=occurred_at,
        details="Wheel climbed rail on curve.",
        location="MP 44.2",
    )

    assert outcome.train_stopped is True
    assert outcome.asset_restricted is True
    assert outcome.asset_event_type is RollingStockEventType.DERAILED
    assert outcome.train_event_type is TrainEventType.ROLLING_STOCK_DERAILED

    assert car.restricted_from_service is True
    assert car.condition is RollingStockCondition.BAD_ORDER

    asset_event = car.event_history[-1]
    assert asset_event.event_type is RollingStockEventType.DERAILED
    assert asset_event.severity is EventSeverity.CRITICAL
    assert asset_event.occurred_at == occurred_at
    assert asset_event.details == "Wheel climbed rail on curve."
    assert asset_event.location == "MP 44.2"
    assert asset_event.related_train_id == train.train_id

    assert train.status is TrainStatus.EMERGENCY_STOPPED
    assert len(train.event_history) == 4

    train_incident_event = train.event_history[-2]
    assert train_incident_event.event_type is TrainEventType.ROLLING_STOCK_DERAILED
    assert train_incident_event.severity is EventSeverity.CRITICAL
    assert train_incident_event.occurred_at == occurred_at
    assert train_incident_event.details == "Wheel climbed rail on curve."
    assert train_incident_event.location == "MP 44.2"
    assert train_incident_event.related_asset_id == str(car.asset_id)

    emergency_stop_event = train.event_history[-1]
    assert emergency_stop_event.event_type is TrainEventType.EMERGENCY_STOPPED
    assert emergency_stop_event.severity is EventSeverity.CRITICAL
    assert emergency_stop_event.occurred_at == occurred_at
    assert emergency_stop_event.location == "MP 44.2"
    assert (
        emergency_stop_event.details == f"Emergency stop: {car.equipment_id} derailed."
    )


def test_hazmat_leak_records_asset_and_train_events_and_stops_train():
    service = IncidentService()
    train = make_train_with_consist()
    car = make_car("GATX", "9001")
    occurred_at = datetime(2026, 3, 21, 11, 0, tzinfo=timezone.utc)

    outcome = service.report_asset_incident(
        train=train,
        asset=car,
        asset_event_type=RollingStockEventType.HAZMAT_LEAK,
        severity=EventSeverity.CRITICAL,
        occurred_at=occurred_at,
        details="Pressure valve leak detected.",
        location="East Siding",
    )

    assert outcome.train_stopped is True
    assert outcome.train_event_type is TrainEventType.HAZMAT_LEAK_REPORTED

    asset_event = car.event_history[-1]
    assert asset_event.event_type is RollingStockEventType.HAZMAT_LEAK
    assert asset_event.severity is EventSeverity.CRITICAL

    train_incident_event = train.event_history[-2]
    assert train_incident_event.event_type is TrainEventType.HAZMAT_LEAK_REPORTED
    assert train_incident_event.severity is EventSeverity.CRITICAL

    emergency_stop_event = train.event_history[-1]
    assert emergency_stop_event.event_type is TrainEventType.EMERGENCY_STOPPED
    assert (
        emergency_stop_event.details
        == f"Emergency stop: hazardous leak reported on {car.equipment_id}."
    )


def test_critical_mechanical_failure_stops_train_even_if_event_type_is_not_auto_stop():
    service = IncidentService()
    train = make_train_with_consist()
    car = make_car("UP", "3003")

    outcome = service.report_asset_incident(
        train=train,
        asset=car,
        asset_event_type=RollingStockEventType.MECHANICAL_FAILURE,
        severity=EventSeverity.CRITICAL,
        details="Bearing failure detected.",
        location="Boise Subdivision",
    )

    assert outcome.train_stopped is True
    assert outcome.train_event_type is TrainEventType.MECHANICAL_FAILURE_REPORTED
    assert train.status is TrainStatus.EMERGENCY_STOPPED

    assert (
        train.event_history[-2].event_type is TrainEventType.MECHANICAL_FAILURE_REPORTED
    )
    assert train.event_history[-1].event_type is TrainEventType.EMERGENCY_STOPPED


def test_non_critical_load_shift_records_incident_without_stopping_train():
    service = IncidentService()
    train = make_train_with_consist()
    car = make_car("CNW", "4004")

    outcome = service.report_asset_incident(
        train=train,
        asset=car,
        asset_event_type=RollingStockEventType.LOAD_SHIFT,
        severity=EventSeverity.MAJOR,
        details="Load shift observed during inspection.",
        location="Nampa Yard",
    )

    assert outcome.train_stopped is False
    assert outcome.train_event_type is TrainEventType.LOAD_SHIFT_REPORTED

    assert car.restricted_from_service is True
    assert car.condition is RollingStockCondition.DAMAGED

    assert train.status is TrainStatus.PLANNED
    assert train.event_history[-1].event_type is TrainEventType.LOAD_SHIFT_REPORTED
    assert train.event_history[-1].severity is EventSeverity.MAJOR


def test_explicit_stop_train_true_forces_emergency_stop():
    service = IncidentService()
    train = make_train_with_consist()
    car = make_car("UP", "5005")

    outcome = service.report_asset_incident(
        train=train,
        asset=car,
        asset_event_type=RollingStockEventType.DAMAGED,
        severity=EventSeverity.WARNING,
        details="Unexpected structural concern reported.",
        location="Caldwell",
        stop_train=True,
    )

    assert outcome.train_stopped is True
    assert train.status is TrainStatus.EMERGENCY_STOPPED
    assert train.event_history[-2].event_type is TrainEventType.INCIDENT_REPORTED
    assert train.event_history[-1].event_type is TrainEventType.EMERGENCY_STOPPED


def test_explicit_stop_train_false_prevents_auto_stop():
    service = IncidentService()
    train = make_train_with_consist()
    car = make_car("UP", "6006")

    outcome = service.report_asset_incident(
        train=train,
        asset=car,
        asset_event_type=RollingStockEventType.DERAILED,
        severity=EventSeverity.CRITICAL,
        details="Minor derailment during yard movement.",
        location="Yard Track 3",
        stop_train=False,
    )

    assert outcome.train_stopped is False
    assert train.status is TrainStatus.PLANNED
    assert train.event_history[-1].event_type is TrainEventType.ROLLING_STOCK_DERAILED


def test_restrict_asset_false_leaves_asset_unrestricted():
    service = IncidentService()
    train = make_train_with_consist()
    car = make_car("UP", "7007")

    outcome = service.report_asset_incident(
        train=train,
        asset=car,
        asset_event_type=RollingStockEventType.DAMAGED,
        severity=EventSeverity.WARNING,
        details="Cosmetic panel damage only.",
        location="Shop Track",
        restrict_asset=False,
    )

    assert outcome.asset_restricted is False
    assert car.restricted_from_service is False
    assert car.condition is RollingStockCondition.IN_SERVICE

    asset_event = car.event_history[-1]
    assert asset_event.event_type is RollingStockEventType.DAMAGED
    assert asset_event.severity is EventSeverity.WARNING


def test_unknown_asset_event_type_maps_to_generic_train_incident_reported():
    service = IncidentService()
    train = make_train_with_consist()
    car = make_car("UP", "8008")

    outcome = service.report_asset_incident(
        train=train,
        asset=car,
        asset_event_type=RollingStockEventType.INSPECTED,
        severity=EventSeverity.INFO,
        details="Follow-up inspection completed.",
        location="Boise Shop",
    )

    assert outcome.train_event_type is TrainEventType.INCIDENT_REPORTED
    assert outcome.train_stopped is False

    train_event = train.event_history[-1]
    assert train_event.event_type is TrainEventType.INCIDENT_REPORTED
    assert train_event.severity is EventSeverity.INFO
    assert train_event.details == "Follow-up inspection completed."


def test_incident_service_preserves_event_sequence_order():
    service = IncidentService()
    train = make_train_with_consist()
    car = make_car()

    service.report_asset_incident(
        train=train,
        asset=car,
        asset_event_type=RollingStockEventType.HAZMAT_LEAK,
        severity=EventSeverity.CRITICAL,
        details="Hazmat release reported.",
        location="MP 55.0",
    )

    assert [event.sequence for event in car.event_history] == [1, 2]
    assert [event.sequence for event in train.event_history] == [1, 2, 3, 4]

    assert [event.event_type for event in train.event_history] == [
        TrainEventType.CREATED,
        TrainEventType.CONSIST_ASSIGNED,
        TrainEventType.HAZMAT_LEAK_REPORTED,
        TrainEventType.EMERGENCY_STOPPED,
    ]
