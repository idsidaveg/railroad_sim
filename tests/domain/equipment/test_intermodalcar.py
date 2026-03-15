from __future__ import annotations

import pytest

from railroad_sim.domain.enums import IntermodalCarType
from railroad_sim.domain.equipment.intermodalcar import IntermodalCar
from tests.domain.equipment.helpers import assert_basic_rolling_stock_contract


def test_intermodalcar_creation_with_defaults():
    car = IntermodalCar(reporting_mark="DTTX", road_number="100001")

    assert_basic_rolling_stock_contract(car)

    assert car.intermodal_car_type == IntermodalCarType.WELL_CAR
    assert car.well_count == 1
    assert car.max_load_units == 2
    assert car.articulated is False
    assert car.load_limit_lbs is None
    assert car.current_units_loaded == 0
    assert car.is_loaded is False
    assert car.equipment_class == "INTERMODAL"


def test_intermodalcar_creation_with_explicit_values():
    car = IntermodalCar(
        reporting_mark="DTTX",
        road_number="100002",
        intermodal_car_type=IntermodalCarType.SPINE_CAR,
        well_count=1,
        max_load_units=5,
        articulated=True,
        load_limit_lbs=180000.0,
        current_units_loaded=2,
    )

    assert_basic_rolling_stock_contract(car)

    assert car.intermodal_car_type == IntermodalCarType.SPINE_CAR
    assert car.max_load_units == 5
    assert car.articulated is True
    assert car.load_limit_lbs == 180000.0
    assert car.current_units_loaded == 2
    assert car.is_loaded is True


def test_intermodalcar_validates_positive_fields():
    with pytest.raises(ValueError, match="well_count must be positive"):
        IntermodalCar(reporting_mark="DTTX", road_number="1", well_count=0)

    with pytest.raises(ValueError, match="max_load_units must be positive"):
        IntermodalCar(reporting_mark="DTTX", road_number="2", max_load_units=0)

    with pytest.raises(ValueError, match="load_limit_lbs must be positive"):
        IntermodalCar(
            reporting_mark="DTTX",
            road_number="3",
            load_limit_lbs=0,
        )


def test_intermodalcar_rejects_current_units_loaded_out_of_range():
    with pytest.raises(ValueError, match="current_units_loaded cannot be negative"):
        IntermodalCar(
            reporting_mark="DTTX",
            road_number="4",
            current_units_loaded=-1,
        )

    with pytest.raises(
        ValueError,
        match="current_units_loaded cannot exceed max_load_units.",
    ):
        IntermodalCar(
            reporting_mark="DTTX",
            road_number="5",
            max_load_units=2,
            current_units_loaded=3,
        )


def test_intermodalcar_load_and_unload_units():
    car = IntermodalCar(reporting_mark="DTTX", road_number="6", max_load_units=3)

    car.load_units(2)
    assert car.current_units_loaded == 2
    assert car.is_loaded is True

    car.unload_units(1)
    assert car.current_units_loaded == 1

    car.unload_units(1)
    assert car.current_units_loaded == 0
    assert car.is_loaded is False


def test_intermodalcar_prevents_invalid_unit_operations():
    car = IntermodalCar(reporting_mark="DTTX", road_number="7", max_load_units=2)

    with pytest.raises(ValueError, match="unit_count must be positive"):
        car.load_units(0)

    with pytest.raises(ValueError, match="Loading would exceed max_load_units."):
        car.load_units(3)

    car.load_units(2)

    with pytest.raises(
        ValueError,
        match="Cannot unload more units than currently loaded.",
    ):
        car.unload_units(3)


def test_intermodalcar_string_and_repr_are_readable():
    car = IntermodalCar(
        reporting_mark="DTTX",
        road_number="8",
        intermodal_car_type=IntermodalCarType.WELL_CAR,
        current_units_loaded=1,
        max_load_units=2,
    )

    assert "DTTX 8" in str(car)
    assert "well_car" in str(car)

    text = repr(car)
    assert "IntermodalCar(" in text
    assert "DTTX 8" in text
    assert "units=1/2" in text


def test_intermodalcar_equipment_class():
    car = IntermodalCar(reporting_mark="DTTX", road_number="100001")
    assert car.equipment_class == "INTERMODAL"
