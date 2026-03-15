from __future__ import annotations

import pytest

from railroad_sim.domain.enums import CabooseType
from railroad_sim.domain.equipment.caboose import Caboose
from tests.domain.equipment.helpers import assert_basic_rolling_stock_contract


def test_caboose_creation_with_defaults():
    car = Caboose(reporting_mark="UP", road_number="900001")

    assert_basic_rolling_stock_contract(car)

    assert car.caboose_type == CabooseType.STANDARD
    assert car.crew_capacity == 4
    assert car.occupied is False
    assert car.has_stove is True
    assert car.has_cupola is False
    assert car.has_bay_window is False
    assert car.equipment_class == "CABOOSE"


def test_caboose_creation_with_explicit_values():
    car = Caboose(
        reporting_mark="UP",
        road_number="900002",
        caboose_type=CabooseType.CUPOLA,
        crew_capacity=5,
        occupied=True,
        has_stove=True,
        has_cupola=True,
    )

    assert_basic_rolling_stock_contract(car)

    assert car.caboose_type == CabooseType.CUPOLA
    assert car.crew_capacity == 5
    assert car.occupied is True
    assert car.has_cupola is True


def test_caboose_validates_crew_capacity():
    with pytest.raises(ValueError, match="crew_capacity must be positive."):
        Caboose(reporting_mark="UP", road_number="1", crew_capacity=0)


def test_cupola_and_bay_window_validation():
    with pytest.raises(ValueError, match="CUPOLA cabooses must have has_cupola=True."):
        Caboose(
            reporting_mark="UP",
            road_number="2",
            caboose_type=CabooseType.CUPOLA,
            has_cupola=False,
        )

    with pytest.raises(
        ValueError,
        match="BAY_WINDOW cabooses must have has_bay_window=True.",
    ):
        Caboose(
            reporting_mark="UP",
            road_number="3",
            caboose_type=CabooseType.BAY_WINDOW,
            has_bay_window=False,
        )


def test_caboose_occupy_and_vacate():
    car = Caboose(reporting_mark="UP", road_number="4")

    car.occupy()
    assert car.occupied is True

    car.vacate()
    assert car.occupied is False


def test_caboose_string_and_repr_are_readable():
    car = Caboose(
        reporting_mark="UP",
        road_number="5",
        caboose_type=CabooseType.TRANSFER,
    )

    assert "UP 5" in str(car)
    assert "transfer" in str(car)

    text = repr(car)
    assert "Caboose(" in text
    assert "UP 5" in text
    assert "occupied=False" in text


def test_caboose_equipment_class():
    car = Caboose(reporting_mark="UP", road_number="900001")
    assert car.equipment_class == "CABOOSE"
