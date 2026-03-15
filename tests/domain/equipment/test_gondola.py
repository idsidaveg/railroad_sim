from __future__ import annotations

import pytest

from railroad_sim.domain.enums import GondolaService, GondolaType
from railroad_sim.domain.equipment.gondola import Gondola
from tests.domain.equipment.helpers import assert_basic_rolling_stock_contract


def test_gondola_creation_with_defaults():
    car = Gondola(reporting_mark="UP", road_number="700001")

    assert_basic_rolling_stock_contract(car)

    assert car.gondola_type == GondolaType.GENERAL_SERVICE
    assert car.service_type == GondolaService.GENERAL
    assert car.inside_length_ft == 52.0
    assert car.cubic_capacity_ft3 is None
    assert car.load_limit_lbs is None
    assert car.current_commodity is None
    assert car.last_commodity is None
    assert car.is_cleaned is True
    assert car.is_loaded is False
    assert car.equipment_class == "GONDOLA"


def test_gondola_creation_with_explicit_values():
    car = Gondola(
        reporting_mark="UP",
        road_number="700002",
        gondola_type=GondolaType.MILL_GONDOLA,
        service_type=GondolaService.STEEL,
        inside_length_ft=65.0,
        cubic_capacity_ft3=5000.0,
        load_limit_lbs=180000.0,
    )

    assert_basic_rolling_stock_contract(car)

    assert car.gondola_type == GondolaType.MILL_GONDOLA
    assert car.service_type == GondolaService.STEEL
    assert car.inside_length_ft == 65.0
    assert car.cubic_capacity_ft3 == 5000.0
    assert car.load_limit_lbs == 180000.0


def test_gondola_validates_positive_fields():
    with pytest.raises(ValueError, match="inside_length_ft must be positive"):
        Gondola(reporting_mark="UP", road_number="1", inside_length_ft=0)

    with pytest.raises(ValueError, match="cubic_capacity_ft3 must be positive"):
        Gondola(reporting_mark="UP", road_number="2", cubic_capacity_ft3=0)

    with pytest.raises(ValueError, match="load_limit_lbs must be positive"):
        Gondola(reporting_mark="UP", road_number="3", load_limit_lbs=0)


def test_gondola_load_unload_and_clean():
    car = Gondola(reporting_mark="UP", road_number="4")

    assert car.can_load_commodity("scrap") is True

    car.load_commodity("scrap")
    assert car.current_commodity == "scrap"
    assert car.is_loaded is True
    assert car.is_cleaned is False

    unloaded = car.unload_commodity()
    assert unloaded == "scrap"
    assert car.current_commodity is None
    assert car.last_commodity == "scrap"
    assert car.is_loaded is False

    car.clean_gondola()
    assert car.is_cleaned is True


def test_gondola_prevents_invalid_loading_states():
    car = Gondola(reporting_mark="UP", road_number="5")

    with pytest.raises(ValueError, match="commodity must be a non-empty string."):
        car.load_commodity("")

    car.load_commodity("aggregate")

    with pytest.raises(ValueError, match="Gondola is already loaded."):
        car.load_commodity("scrap")

    car.unload_commodity()

    with pytest.raises(ValueError, match="Gondola is not currently loaded."):
        car.unload_commodity()


def test_gondola_string_and_repr_are_readable():
    car = Gondola(
        reporting_mark="UP",
        road_number="6",
        gondola_type=GondolaType.HIGH_SIDE,
        service_type=GondolaService.SCRAP,
    )

    assert "UP 6" in str(car)
    assert "high_side" in str(car)

    text = repr(car)
    assert "Gondola(" in text
    assert "UP 6" in text
    assert "scrap" in text


def test_gondola_equipment_class():
    car = Gondola(reporting_mark="UP", road_number="700001")
    assert car.equipment_class == "GONDOLA"
