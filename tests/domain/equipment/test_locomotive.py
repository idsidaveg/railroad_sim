from __future__ import annotations

import pytest

from railroad_sim.domain.enums import MotivePowerType
from railroad_sim.domain.equipment.locomotive import Locomotive
from tests.domain.equipment.helpers import assert_basic_rolling_stock_contract


def test_locomotive_creation_with_defaults():
    loco = Locomotive(reporting_mark="BNSF", road_number="4721")

    assert_basic_rolling_stock_contract(loco)

    assert loco.motive_power_type == MotivePowerType.DIESEL
    assert loco.horsepower == 4400
    assert loco.builder is None
    assert loco.model is None
    assert loco.axle_count is None
    assert loco.energy_capacity is None


def test_locomotive_creation_with_explicit_values():
    loco = Locomotive(
        reporting_mark="UP",
        road_number="844",
        motive_power_type=MotivePowerType.STEAM,
        horsepower=4500,
        builder="ALCO",
        model="FEF-3",
        axle_count=8,
        energy_capacity=0.0,
    )

    assert_basic_rolling_stock_contract(loco)

    assert loco.motive_power_type == MotivePowerType.STEAM
    assert loco.horsepower == 4500
    assert loco.builder == "ALCO"
    assert loco.model == "FEF-3"
    assert loco.axle_count == 8
    assert loco.energy_capacity == 0.0


def test_locomotives_have_unique_asset_identity():
    loco1 = Locomotive(reporting_mark="BNSF", road_number="1001")
    loco2 = Locomotive(reporting_mark="BNSF", road_number="1002")

    assert loco1.asset_id != loco2.asset_id


def test_locomotive_horsepower_must_be_positive():
    with pytest.raises(ValueError, match="horsepower must be positive"):
        Locomotive(
            reporting_mark="BNSF",
            road_number="9999",
            horsepower=0,
        )

    with pytest.raises(ValueError, match="horsepower must be positive"):
        Locomotive(
            reporting_mark="BNSF",
            road_number="9998",
            horsepower=-100,
        )


def test_locomotive_axle_count_must_be_positive_when_provided():
    with pytest.raises(ValueError, match="axle_count must be positive"):
        Locomotive(
            reporting_mark="BNSF",
            road_number="9997",
            axle_count=0,
        )

    with pytest.raises(ValueError, match="axle_count must be positive"):
        Locomotive(
            reporting_mark="BNSF",
            road_number="9996",
            axle_count=-2,
        )


def test_locomotive_energy_capacity_cannot_be_negative():
    with pytest.raises(ValueError, match="energy_capacity cannot be negative"):
        Locomotive(
            reporting_mark="FUTX",
            road_number="2001",
            motive_power_type=MotivePowerType.HYDROGEN,
            energy_capacity=-1.0,
        )


def test_locomotive_string_representation_is_readable():
    loco = Locomotive(
        reporting_mark="BNSF",
        road_number="4721",
        motive_power_type=MotivePowerType.DIESEL,
        horsepower=4400,
    )

    text = str(loco)

    assert "BNSF 4721" in text
    assert "diesel" in text
    assert "4400 hp" in text


def test_locomotive_repr_contains_debug_information():
    loco = Locomotive(
        reporting_mark="UP",
        road_number="844",
        motive_power_type=MotivePowerType.STEAM,
        horsepower=4500,
    )

    text = repr(loco)

    assert "Locomotive(" in text
    assert "UP 844" in text
    assert "steam" in text
    assert "hp=4500" in text


def test_locomotive_equipment_class():
    loco = Locomotive(reporting_mark="BNSF", road_number="4721")
    assert loco.equipment_class == "LOCO"
