from datetime import datetime, timezone

import pytest

from railroad_sim.domain.consist import Consist
from railroad_sim.domain.enums import TrainEventType, TrainStatus
from railroad_sim.domain.rolling_stock import RollingStock
from railroad_sim.domain.train import Train


def make_car(
    reporting_mark: str = "UP",
    road_number: str = "1001",
) -> RollingStock:
    return RollingStock(reporting_mark=reporting_mark, road_number=road_number)


def make_consist() -> Consist:
    return Consist(anchor=make_car())


def make_train(
    train_id: str = "train-001",
    symbol: str = "m-101",
    current_consist: Consist | None = None,
) -> Train:
    return Train(
        train_id=train_id,
        symbol=symbol,
        current_consist=current_consist,
    )


def test_train_creates_with_normalized_symbol_and_created_event():
    train = make_train(symbol=" m-101 ")

    assert train.train_id == "train-001"
    assert train.symbol == "M-101"
    assert train.status is TrainStatus.PLANNED
    assert train.current_consist is None
    assert train.has_consist is False

    assert len(train.event_history) == 1
    event = train.event_history[0]
    assert event.sequence == 1
    assert event.event_type is TrainEventType.CREATED
    assert event.details == "Train created."
    assert event.location is None
    assert event.related_consist_id is None
    assert event.related_asset_id is None
    assert event.occurred_at.tzinfo is not None


def test_train_uses_explicit_created_at_for_created_event():
    created_at = datetime(2025, 1, 1, 10, 30, tzinfo=timezone.utc)

    train = Train(
        train_id="train-001",
        symbol="M-101",
        created_at_value=created_at,
    )

    event = train.event_history[0]
    assert event.event_type is TrainEventType.CREATED
    assert event.occurred_at == created_at


def test_train_with_initial_consist_records_created_and_consist_assigned_events():
    consist = make_consist()

    train = Train(
        train_id="train-001",
        symbol="M-101",
        current_consist=consist,
    )

    assert train.current_consist is consist
    assert train.has_consist is True
    assert len(train.event_history) == 2

    assert train.event_history[0].sequence == 1
    assert train.event_history[0].event_type is TrainEventType.CREATED

    assert train.event_history[1].sequence == 2
    assert train.event_history[1].event_type is TrainEventType.CONSIST_ASSIGNED
    assert (
        train.event_history[1].details == "Initial consist assigned at train creation."
    )


def test_train_id_is_trimmed():
    train = Train(train_id="  train-001  ", symbol="M-101")

    assert train.train_id == "train-001"


def test_empty_train_id_raises_error():
    with pytest.raises(ValueError):
        Train(train_id="   ", symbol="M-101")


def test_empty_symbol_raises_error():
    with pytest.raises(ValueError):
        Train(train_id="train-001", symbol="   ")


def test_event_history_is_read_only_tuple():
    train = make_train()

    assert isinstance(train.event_history, tuple)

    with pytest.raises(AttributeError):
        train.event_history.append("bad")  # type: ignore[attr-defined]


def test_assign_consist_to_train_without_existing_consist_records_assigned_event():
    train = make_train()
    consist = make_consist()
    occurred_at = datetime(2026, 3, 9, 12, 0, tzinfo=timezone.utc)

    train.assign_consist(
        consist,
        occurred_at=occurred_at,
        details="Assigned at Nampa Yard.",
        location="Nampa Yard",
    )

    assert train.current_consist is consist
    assert train.has_consist is True
    assert len(train.event_history) == 2

    event = train.event_history[-1]
    assert event.sequence == 2
    assert event.event_type is TrainEventType.CONSIST_ASSIGNED
    assert event.occurred_at == occurred_at
    assert event.details == "Assigned at Nampa Yard."
    assert event.location == "Nampa Yard"


def test_assign_consist_to_train_with_existing_consist_records_changed_event():
    first_consist = make_consist()
    second_consist = Consist(anchor=make_car("BNSF", "2002"))
    train = make_train(current_consist=first_consist)
    occurred_at = datetime(2026, 3, 9, 13, 0, tzinfo=timezone.utc)

    train.assign_consist(
        second_consist,
        occurred_at=occurred_at,
        details="Power and consist swap.",
        location="Boise Yard",
    )

    assert train.current_consist is second_consist
    assert len(train.event_history) == 3

    event = train.event_history[-1]
    assert event.sequence == 3
    assert event.event_type is TrainEventType.CONSIST_CHANGED
    assert event.occurred_at == occurred_at
    assert event.details == "Power and consist swap."
    assert event.location == "Boise Yard"


def test_assign_same_consist_object_does_nothing():
    consist = make_consist()
    train = make_train(current_consist=consist)

    original_history = train.event_history

    train.assign_consist(consist)

    assert train.current_consist is consist
    assert train.event_history == original_history


def test_release_consist_records_event_and_clears_current_consist():
    consist = make_consist()
    train = make_train(current_consist=consist)
    occurred_at = datetime(2026, 3, 9, 14, 0, tzinfo=timezone.utc)

    train.release_consist(
        occurred_at=occurred_at,
        details="Released at terminal.",
        location="Boise Terminal",
    )

    assert train.current_consist is None
    assert train.has_consist is False
    assert len(train.event_history) == 3

    event = train.event_history[-1]
    assert event.sequence == 3
    assert event.event_type is TrainEventType.CONSIST_RELEASED
    assert event.occurred_at == occurred_at
    assert event.details == "Released at terminal."
    assert event.location == "Boise Terminal"


def test_release_consist_when_none_does_nothing():
    train = make_train()

    original_history = train.event_history

    train.release_consist()

    assert train.current_consist is None
    assert train.event_history == original_history


def test_depart_sets_status_active_and_records_event():
    train = make_train()
    occurred_at = datetime(2026, 3, 9, 15, 0, tzinfo=timezone.utc)

    train.depart(
        occurred_at=occurred_at,
        details="Departed on signal indication.",
        location="Nampa Yard",
    )

    assert train.status is TrainStatus.ACTIVE

    event = train.event_history[-1]
    assert event.event_type is TrainEventType.DEPARTED
    assert event.occurred_at == occurred_at
    assert event.details == "Departed on signal indication."
    assert event.location == "Nampa Yard"


def test_arrive_records_event():
    train = make_train()
    occurred_at = datetime(2026, 3, 9, 16, 0, tzinfo=timezone.utc)

    train.arrive(
        occurred_at=occurred_at,
        details="Arrived at destination terminal.",
        location="Boise Yard",
    )

    event = train.event_history[-1]
    assert event.event_type is TrainEventType.ARRIVED
    assert event.occurred_at == occurred_at
    assert event.details == "Arrived at destination terminal."
    assert event.location == "Boise Yard"


def test_hold_sets_status_held_and_records_event():
    train = make_train()
    occurred_at = datetime(2026, 3, 9, 17, 0, tzinfo=timezone.utc)

    train.hold(
        occurred_at=occurred_at,
        details="Held for meet.",
        location="Caldwell",
    )

    assert train.status is TrainStatus.HELD

    event = train.event_history[-1]
    assert event.event_type is TrainEventType.HELD
    assert event.occurred_at == occurred_at
    assert event.details == "Held for meet."
    assert event.location == "Caldwell"


def test_complete_sets_status_completed_and_records_event():
    train = make_train()
    occurred_at = datetime(2026, 3, 9, 18, 0, tzinfo=timezone.utc)

    train.complete(
        occurred_at=occurred_at,
        details="Completed scheduled run.",
        location="Boise Yard",
    )

    assert train.status is TrainStatus.COMPLETED

    event = train.event_history[-1]
    assert event.event_type is TrainEventType.COMPLETED
    assert event.occurred_at == occurred_at
    assert event.details == "Completed scheduled run."
    assert event.location == "Boise Yard"


def test_cancel_sets_status_canceled_and_records_event():
    train = make_train()
    occurred_at = datetime(2026, 3, 9, 19, 0, tzinfo=timezone.utc)

    train.cancel(
        occurred_at=occurred_at,
        details="Canceled before departure.",
        location="Nampa Yard",
    )

    assert train.status is TrainStatus.CANCELED

    event = train.event_history[-1]
    assert event.event_type is TrainEventType.CANCELED
    assert event.occurred_at == occurred_at
    assert event.details == "Canceled before departure."
    assert event.location == "Nampa Yard"


def test_record_asset_event_records_related_asset_id():
    train = make_train()
    occurred_at = datetime(2026, 3, 9, 20, 0, tzinfo=timezone.utc)

    train.record_asset_event(
        TrainEventType.CAR_REMOVED,
        related_asset_id="UP-1001-ASSET",
        occurred_at=occurred_at,
        details="Car removed for local delivery.",
        location="Caldwell Spur",
    )

    event = train.event_history[-1]
    assert event.event_type is TrainEventType.CAR_REMOVED
    assert event.occurred_at == occurred_at
    assert event.details == "Car removed for local delivery."
    assert event.location == "Caldwell Spur"
    assert event.related_asset_id == "UP-1001-ASSET"


def test_record_asset_event_rejects_empty_asset_id():
    train = make_train()

    with pytest.raises(ValueError):
        train.record_asset_event(
            TrainEventType.CAR_REMOVED,
            related_asset_id="   ",
        )


def test_to_snapshot_returns_serializable_dict_shape():
    train = make_train()
    train.depart(
        occurred_at=datetime(2026, 3, 9, 15, 0, tzinfo=timezone.utc),
        details="Departed westbound.",
        location="Nampa Yard",
    )

    snapshot = train.to_snapshot()

    assert snapshot["train_id"] == "train-001"
    assert snapshot["symbol"] == "M-101"
    assert snapshot["origin"] is None
    assert snapshot["destination"] is None
    assert snapshot["status"] == TrainStatus.ACTIVE.value
    assert "current_consist_id" in snapshot
    assert "event_history" in snapshot
    assert len(snapshot["event_history"]) == 2

    created_event = snapshot["event_history"][0]
    departed_event = snapshot["event_history"][1]

    assert created_event["event_type"] == TrainEventType.CREATED.value
    assert departed_event["event_type"] == TrainEventType.DEPARTED.value
    assert departed_event["details"] == "Departed westbound."
    assert departed_event["location"] == "Nampa Yard"


def test_from_snapshot_restores_train_without_creating_fake_created_event():
    original = make_train()
    original.depart(
        occurred_at=datetime(2026, 3, 9, 15, 0, tzinfo=timezone.utc),
        details="Departed westbound.",
        location="Nampa Yard",
    )
    original.hold(
        occurred_at=datetime(2026, 3, 9, 16, 0, tzinfo=timezone.utc),
        details="Held for traffic.",
        location="Caldwell",
    )

    snapshot = original.to_snapshot()

    restored = Train.from_snapshot(snapshot)

    assert restored.train_id == original.train_id
    assert restored.symbol == original.symbol
    assert restored.status is TrainStatus.HELD
    assert restored.current_consist is None

    assert len(restored.event_history) == 3
    assert [event.sequence for event in restored.event_history] == [1, 2, 3]
    assert [event.event_type for event in restored.event_history] == [
        TrainEventType.CREATED,
        TrainEventType.DEPARTED,
        TrainEventType.HELD,
    ]


def test_from_snapshot_restores_current_consist_reference_when_provided():
    consist = make_consist()
    original = make_train(current_consist=consist)
    snapshot = original.to_snapshot()

    restored = Train.from_snapshot(snapshot, current_consist=consist)

    assert restored.current_consist is consist
    assert restored.has_consist is True


def test_train_event_sequence_increments_across_multiple_operations():
    train = make_train()

    train.depart(details="Departed.")
    train.hold(details="Held.")
    train.complete(details="Completed.")

    assert [event.sequence for event in train.event_history] == [1, 2, 3, 4]
    assert [event.event_type for event in train.event_history] == [
        TrainEventType.CREATED,
        TrainEventType.DEPARTED,
        TrainEventType.HELD,
        TrainEventType.COMPLETED,
    ]


def test_repr_uses_symbol():
    train = make_train(symbol="M-101")

    assert repr(train) == "Train(M-101)"
