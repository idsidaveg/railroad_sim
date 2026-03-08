from uuid import UUID, uuid4

import pytest

from railroad_sim.domain.enums import CouplerPosition
from railroad_sim.domain.rolling_stock import RollingStock


def test_rolling_stock_creates_with_uuid_and_couplers():
    car = RollingStock(reporting_mark="UP", road_number="1001")

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


def test_rolling_stock_accepts_explicit_asset_id():
    known_id = uuid4()

    car = RollingStock(
        reporting_mark="BNSF",
        road_number="778901",
        asset_id_value=known_id,
    )

    assert car.asset_id == known_id


def test_asset_id_is_read_only_after_creation():
    car = RollingStock(reporting_mark="UP", road_number="1001")

    with pytest.raises(AttributeError):
        setattr(car, "asset_id", uuid4())


def test_equipment_id_returns_reporting_mark_and_road_number():
    car = RollingStock(reporting_mark="BNSF", road_number="778901")

    assert car.equipment_id == "BNSF 778901"


def test_reporting_mark_is_normalized_to_uppercase_and_trimmed():
    car = RollingStock(reporting_mark="  up ", road_number="1001")

    assert car.reporting_mark == "UP"


def test_road_number_is_trimmed():
    car = RollingStock(reporting_mark="UP", road_number=" 1001 ")

    assert car.road_number == "1001"


def test_empty_reporting_mark_raises_error():
    with pytest.raises(ValueError):
        RollingStock(reporting_mark="   ", road_number="1001")


def test_empty_road_number_raises_error():
    with pytest.raises(ValueError):
        RollingStock(reporting_mark="UP", road_number="   ")


def test_rename_equipment_updates_visible_identifier_but_not_asset_id():
    car = RollingStock(reporting_mark="UP", road_number="1001")
    original_asset_id = car.asset_id

    car.rename_equipment("BNSF", "2002")

    assert car.asset_id == original_asset_id
    assert car.reporting_mark == "BNSF"
    assert car.road_number == "2002"
    assert car.equipment_id == "BNSF 2002"


def test_rename_equipment_normalizes_values():
    car = RollingStock(reporting_mark="UP", road_number="1001")

    car.rename_equipment("  csxt ", " 3003 ")

    assert car.reporting_mark == "CSXT"
    assert car.road_number == "3003"


def test_rename_equipment_rejects_empty_reporting_mark():
    car = RollingStock(reporting_mark="UP", road_number="1001")

    with pytest.raises(ValueError):
        car.rename_equipment("   ", "3003")


def test_rename_equipment_rejects_empty_road_number():
    car = RollingStock(reporting_mark="UP", road_number="1001")

    with pytest.raises(ValueError):
        car.rename_equipment("BNSF", "   ")


def test_repr_uses_equipment_id():
    car = RollingStock(reporting_mark="UP", road_number="1001")
    assert repr(car) == "RollingStock(UP 1001)"
