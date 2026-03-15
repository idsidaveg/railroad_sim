from __future__ import annotations

import pytest

from railroad_sim.domain.enums import (
    TankCarService,
    TankCarThermalProtection,
    TankCarType,
)
from railroad_sim.domain.equipment.tankcar import TankCar
from tests.domain.equipment.helpers import assert_basic_rolling_stock_contract


def test_tank_car_creation_with_defaults():
    car = TankCar(reporting_mark="UTLX", road_number="100001")

    assert_basic_rolling_stock_contract(car)

    assert car.tankcar_type == TankCarType.GENERAL_SERVICE
    assert car.service_type == TankCarService.GENERAL
    assert car.thermal_protection == TankCarThermalProtection.NONE
    assert car.capacity_gallons == 30000.0
    assert car.commodity is None
    assert car.current_commodity is None
    assert car.last_commodity is None
    assert car.is_cleaned is True
    assert car.is_loaded is False


def test_tankcar_creation_with_explicit_values():
    car = TankCar(
        reporting_mark="UTLX",
        road_number="100002",
        tankcar_type=TankCarType.PRESSURE,
        service_type=TankCarService.CHEMICAL,
        thermal_protection=TankCarThermalProtection.INSULATED,
        capacity_gallons=33800.0,
        commodity=None,
        hazmat_class="2.2",
        is_pressurized=True,
        load_limit_lbs=180000.0,
        tank_material="carbon_steel",
    )

    assert_basic_rolling_stock_contract(car)

    assert car.tankcar_type == TankCarType.PRESSURE
    assert car.service_type == TankCarService.CHEMICAL
    assert car.thermal_protection == TankCarThermalProtection.INSULATED
    assert car.capacity_gallons == 33800.0
    assert car.hazmat_class == "2.2"
    assert car.is_pressurized is True
    assert car.load_limit_lbs == 180000.0
    assert car.tank_material == "carbon_steel"


def test_tank_cars_have_unique_asset_identity():
    car1 = TankCar(reporting_mark="UTLX", road_number="100001")
    car2 = TankCar(reporting_mark="UTLX", road_number="100002")

    assert car1.asset_id != car2.asset_id


def test_tank_car_capacity_must_be_positive():
    with pytest.raises(ValueError, match="capacity_gallons must be positive"):
        TankCar(
            reporting_mark="UTLX",
            road_number="100010",
            capacity_gallons=0,
        )

    with pytest.raises(ValueError, match="capacity_gallons must be positive"):
        TankCar(
            reporting_mark="UTLX",
            road_number="100011",
            capacity_gallons=-1,
        )


def test_tank_car_load_limit_must_be_positive_when_provided():
    with pytest.raises(ValueError, match="load_limit_lbs must be positive"):
        TankCar(
            reporting_mark="UTLX",
            road_number="100020",
            load_limit_lbs=0,
        )

    with pytest.raises(ValueError, match="load_limit_lbs must be positive"):
        TankCar(
            reporting_mark="UTLX",
            road_number="100021",
            load_limit_lbs=-100,
        )


def test_pressure_tankcar_must_be_pressurized():
    with pytest.raises(
        ValueError,
        match="PRESSURE tank cars must have is_pressurized=True.",
    ):
        TankCar(
            reporting_mark="UTLX",
            road_number="100030",
            tankcar_type=TankCarType.PRESSURE,
            is_pressurized=False,
        )


def test_cryogenic_tankcar_must_be_pressurized():
    with pytest.raises(
        ValueError,
        match="CRYOGENIC tank cars must have is_pressurized=True.",
    ):
        TankCar(
            reporting_mark="UTLX",
            road_number="100031",
            tankcar_type=TankCarType.CRYOGENIC,
            is_pressurized=False,
        )


def test_food_grade_tankcar_requires_stainless_steel_when_material_provided():
    with pytest.raises(
        ValueError,
        match="FOOD_GRADE tank cars must use stainless_steel",
    ):
        TankCar(
            reporting_mark="UTLX",
            road_number="100032",
            service_type=TankCarService.FOOD_GRADE,
            tank_material="carbon_steel",
        )


def test_food_grade_tankcar_allows_stainless_steel():
    car = TankCar(
        reporting_mark="UTLX",
        road_number="100033",
        service_type=TankCarService.FOOD_GRADE,
        tank_material="stainless_steel",
    )

    assert_basic_rolling_stock_contract(car)
    assert car.service_type == TankCarService.FOOD_GRADE
    assert car.tank_material == "stainless_steel"


def test_can_load_food_grade_requires_food_grade_service_and_clean_state():
    car = TankCar(
        reporting_mark="UTLX",
        road_number="100040",
        service_type=TankCarService.FOOD_GRADE,
        tank_material="stainless_steel",
        is_cleaned=True,
    )

    assert car.can_load_commodity("soy_oil", food_grade=True) is True

    car2 = TankCar(
        reporting_mark="UTLX",
        road_number="100041",
        service_type=TankCarService.CHEMICAL,
        is_cleaned=True,
    )

    assert car2.can_load_commodity("soy_oil", food_grade=True) is False


def test_load_commodity_marks_car_loaded_and_not_clean():
    car = TankCar(reporting_mark="UTLX", road_number="100050")

    car.load_commodity("diesel_fuel")

    assert car.current_commodity == "diesel_fuel"
    assert car.commodity == "diesel_fuel"
    assert car.is_loaded is True
    assert car.is_cleaned is False


def test_cannot_load_when_already_loaded():
    car = TankCar(reporting_mark="UTLX", road_number="100051")
    car.load_commodity("diesel_fuel")

    with pytest.raises(ValueError, match="Tank car is already loaded."):
        car.load_commodity("crude_oil")


def test_unload_commodity_moves_current_to_last():
    car = TankCar(reporting_mark="UTLX", road_number="100052")
    car.load_commodity("crude_oil")

    unloaded = car.unload_commodity()

    assert unloaded == "crude_oil"
    assert car.current_commodity is None
    assert car.commodity is None
    assert car.last_commodity == "crude_oil"
    assert car.is_loaded is False
    assert car.is_cleaned is False


def test_unload_requires_loaded_car():
    car = TankCar(reporting_mark="UTLX", road_number="100053")

    with pytest.raises(ValueError, match="Tank car is not currently loaded."):
        car.unload_commodity()


def test_clean_tank_marks_car_cleaned():
    car = TankCar(
        reporting_mark="UTLX",
        road_number="100054",
        service_type=TankCarService.FOOD_GRADE,
        tank_material="stainless_steel",
    )
    car.load_commodity("soy_oil")
    car.unload_commodity()

    assert car.is_cleaned is False

    car.clean_tank()

    assert car.is_cleaned is True


def test_food_grade_load_requires_cleaned_tank():
    car = TankCar(
        reporting_mark="UTLX",
        road_number="100055",
        service_type=TankCarService.FOOD_GRADE,
        tank_material="stainless_steel",
    )
    car.load_commodity("milk", food_grade=True)
    car.unload_commodity()

    with pytest.raises(
        ValueError,
        match="Food-grade commodities require a cleaned tank car.",
    ):
        car.load_commodity("soy_oil", food_grade=True)


def test_tankcar_string_representation_is_readable():
    car = TankCar(
        reporting_mark="UTLX",
        road_number="100060",
        tankcar_type=TankCarType.GENERAL_SERVICE,
        capacity_gallons=30000.0,
    )

    text = str(car)

    assert "UTLX 100060" in text
    assert "general_service" in text
    assert "30000" in text


def test_tankcar_repr_contains_debug_information():
    car = TankCar(
        reporting_mark="UTLX",
        road_number="100061",
        tankcar_type=TankCarType.PRESSURE,
        service_type=TankCarService.CHEMICAL,
        capacity_gallons=33800.0,
        is_pressurized=True,
    )

    text = repr(car)

    assert "TankCar(" in text
    assert "UTLX 100061" in text
    assert "pressure" in text
    assert "chemical" in text
    assert "capacity_gallons=33800" in text


def test_general_service_tankcar_equipment_class():
    car = TankCar(reporting_mark="UTLX", road_number="100001")
    assert car.equipment_class == "TANK"


def test_pressure_tankcar_equipment_class():
    car = TankCar(
        reporting_mark="UTLX",
        road_number="100002",
        tankcar_type=TankCarType.PRESSURE,
        is_pressurized=True,
    )
    assert car.equipment_class == "PRESSURE_TANK"


def test_cryogenic_tankcar_equipment_class():
    car = TankCar(
        reporting_mark="UTLX",
        road_number="100003",
        tankcar_type=TankCarType.CRYOGENIC,
        is_pressurized=True,
    )
    assert car.equipment_class == "CRYO_TANK"
