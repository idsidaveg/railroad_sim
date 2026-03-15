from __future__ import annotations

import pytest

from railroad_sim.domain.enums import (
    BoxCarService,
    BoxCarThermalProtection,
    BoxCarType,
)
from railroad_sim.domain.equipment.boxcar import BoxCar
from tests.domain.equipment.helpers import assert_basic_rolling_stock_contract


def test_boxcar_creation_with_defaults():
    car = BoxCar(reporting_mark="UP", road_number="500001")

    assert_basic_rolling_stock_contract(car)

    assert car.boxcar_type == BoxCarType.STANDARD
    assert car.service_type == BoxCarService.GENERAL
    assert car.thermal_protection == BoxCarThermalProtection.NONE
    assert car.inside_length_ft == 50.0
    assert car.cubic_capacity_ft3 is None
    assert car.door_count == 1
    assert car.load_limit_lbs is None
    assert car.current_commodity is None
    assert car.last_commodity is None
    assert car.is_cleaned is True
    assert car.is_loaded is False


def test_boxcar_creation_with_explicit_values():
    car = BoxCar(
        reporting_mark="BNSF",
        road_number="600100",
        boxcar_type=BoxCarType.PLUG_DOOR,
        service_type=BoxCarService.PAPER,
        thermal_protection=BoxCarThermalProtection.INSULATED,
        inside_length_ft=60.0,
        cubic_capacity_ft3=7500.0,
        door_count=2,
        load_limit_lbs=140000.0,
    )

    assert_basic_rolling_stock_contract(car)

    assert car.boxcar_type == BoxCarType.PLUG_DOOR
    assert car.service_type == BoxCarService.PAPER
    assert car.thermal_protection == BoxCarThermalProtection.INSULATED
    assert car.inside_length_ft == 60.0
    assert car.cubic_capacity_ft3 == 7500.0
    assert car.door_count == 2
    assert car.load_limit_lbs == 140000.0


def test_boxcars_have_unique_asset_identity():
    car1 = BoxCar(reporting_mark="UP", road_number="500001")
    car2 = BoxCar(reporting_mark="UP", road_number="500002")

    assert car1.asset_id != car2.asset_id


def test_boxcar_inside_length_must_be_positive():
    with pytest.raises(ValueError, match="inside_length_ft must be positive"):
        BoxCar(
            reporting_mark="UP",
            road_number="500010",
            inside_length_ft=0,
        )

    with pytest.raises(ValueError, match="inside_length_ft must be positive"):
        BoxCar(
            reporting_mark="UP",
            road_number="500011",
            inside_length_ft=-10,
        )


def test_boxcar_cubic_capacity_must_be_positive_when_provided():
    with pytest.raises(ValueError, match="cubic_capacity_ft3 must be positive"):
        BoxCar(
            reporting_mark="UP",
            road_number="500020",
            cubic_capacity_ft3=0,
        )

    with pytest.raises(ValueError, match="cubic_capacity_ft3 must be positive"):
        BoxCar(
            reporting_mark="UP",
            road_number="500021",
            cubic_capacity_ft3=-1,
        )


def test_boxcar_door_count_must_be_positive():
    with pytest.raises(ValueError, match="door_count must be positive"):
        BoxCar(
            reporting_mark="UP",
            road_number="500030",
            door_count=0,
        )

    with pytest.raises(ValueError, match="door_count must be positive"):
        BoxCar(
            reporting_mark="UP",
            road_number="500031",
            door_count=-2,
        )


def test_boxcar_load_limit_must_be_positive_when_provided():
    with pytest.raises(ValueError, match="load_limit_lbs must be positive"):
        BoxCar(
            reporting_mark="UP",
            road_number="500040",
            load_limit_lbs=0,
        )

    with pytest.raises(ValueError, match="load_limit_lbs must be positive"):
        BoxCar(
            reporting_mark="UP",
            road_number="500041",
            load_limit_lbs=-100,
        )


def test_refrigerated_boxcar_requires_refrigerated_thermal_protection():
    with pytest.raises(
        ValueError,
        match="REFRIGERATED boxcars must use REFRIGERATED thermal protection.",
    ):
        BoxCar(
            reporting_mark="UP",
            road_number="500050",
            boxcar_type=BoxCarType.REFRIGERATED,
            thermal_protection=BoxCarThermalProtection.NONE,
        )


def test_insulated_boxcar_requires_thermal_protection():
    with pytest.raises(
        ValueError,
        match="INSULATED boxcars must use insulated or refrigerated thermal protection.",
    ):
        BoxCar(
            reporting_mark="UP",
            road_number="500051",
            boxcar_type=BoxCarType.INSULATED,
            thermal_protection=BoxCarThermalProtection.NONE,
        )


def test_can_load_food_grade_requires_food_grade_service_and_clean_state():
    car = BoxCar(
        reporting_mark="UP",
        road_number="500060",
        service_type=BoxCarService.FOOD_GRADE,
        thermal_protection=BoxCarThermalProtection.REFRIGERATED,
        boxcar_type=BoxCarType.REFRIGERATED,
        is_cleaned=True,
    )

    assert car.can_load_commodity("bagged_food", food_grade=True) is True

    car2 = BoxCar(
        reporting_mark="UP",
        road_number="500061",
        service_type=BoxCarService.GENERAL,
        is_cleaned=True,
    )

    assert car2.can_load_commodity("bagged_food", food_grade=True) is False


def test_load_commodity_marks_boxcar_loaded_and_not_clean():
    car = BoxCar(reporting_mark="UP", road_number="500070")

    car.load_commodity("paper_rolls")

    assert car.current_commodity == "paper_rolls"
    assert car.is_loaded is True
    assert car.is_cleaned is False


def test_cannot_load_when_already_loaded():
    car = BoxCar(reporting_mark="UP", road_number="500071")
    car.load_commodity("appliances")

    with pytest.raises(ValueError, match="Boxcar is already loaded."):
        car.load_commodity("paper")


def test_unload_commodity_moves_current_to_last():
    car = BoxCar(reporting_mark="UP", road_number="500072")
    car.load_commodity("paper_rolls")

    unloaded = car.unload_commodity()

    assert unloaded == "paper_rolls"
    assert car.current_commodity is None
    assert car.last_commodity == "paper_rolls"
    assert car.is_loaded is False
    assert car.is_cleaned is False


def test_unload_requires_loaded_boxcar():
    car = BoxCar(reporting_mark="UP", road_number="500073")

    with pytest.raises(ValueError, match="Boxcar is not currently loaded."):
        car.unload_commodity()


def test_clean_boxcar_marks_car_cleaned():
    car = BoxCar(
        reporting_mark="UP",
        road_number="500074",
        service_type=BoxCarService.FOOD_GRADE,
    )
    car.load_commodity("bagged_food", food_grade=True)
    car.unload_commodity()

    assert car.is_cleaned is False

    car.clean_boxcar()

    assert car.is_cleaned is True


def test_food_grade_load_requires_cleaned_boxcar():
    car = BoxCar(
        reporting_mark="UP",
        road_number="500075",
        service_type=BoxCarService.FOOD_GRADE,
    )
    car.load_commodity("bagged_food", food_grade=True)
    car.unload_commodity()

    with pytest.raises(
        ValueError,
        match="Food-grade commodities require a cleaned boxcar.",
    ):
        car.load_commodity("boxed_milk", food_grade=True)


def test_boxcar_string_representation_is_readable():
    car = BoxCar(
        reporting_mark="BNSF",
        road_number="600100",
        boxcar_type=BoxCarType.AUTO_PARTS,
        inside_length_ft=60.0,
    )

    text = str(car)

    assert "BNSF 600100" in text
    assert "auto_parts" in text
    assert "60" in text


def test_boxcar_repr_contains_debug_information():
    car = BoxCar(
        reporting_mark="UP",
        road_number="500001",
        boxcar_type=BoxCarType.INSULATED,
        service_type=BoxCarService.FOOD_GRADE,
        thermal_protection=BoxCarThermalProtection.INSULATED,
        inside_length_ft=50.0,
    )

    text = repr(car)

    assert "BoxCar(" in text
    assert "UP 500001" in text
    assert "insulated" in text
    assert "food_grade" in text
    assert "length_ft=50" in text


def test_standard_boxcar_equipment_class():
    car = BoxCar(reporting_mark="UP", road_number="500001")
    assert car.equipment_class == "BOX"


def test_reefer_boxcar_equipment_class():
    car = BoxCar(
        reporting_mark="UP",
        road_number="500002",
        boxcar_type=BoxCarType.REFRIGERATED,
        thermal_protection=BoxCarThermalProtection.REFRIGERATED,
    )
    assert car.equipment_class == "REEFER"


def test_insulated_boxcar_equipment_class():
    car = BoxCar(
        reporting_mark="UP",
        road_number="500003",
        boxcar_type=BoxCarType.INSULATED,
        thermal_protection=BoxCarThermalProtection.INSULATED,
    )
    assert car.equipment_class == "INSULATED_BOX"


def test_auto_parts_boxcar_equipment_class():
    car = BoxCar(
        reporting_mark="UP",
        road_number="500004",
        boxcar_type=BoxCarType.AUTO_PARTS,
    )
    assert car.equipment_class == "AUTO_PARTS_BOX"
