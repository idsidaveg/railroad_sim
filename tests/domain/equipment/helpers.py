from __future__ import annotations

from railroad_sim.domain.couplers import Coupler
from railroad_sim.domain.enums import CouplerPosition


def assert_basic_rolling_stock_contract(car) -> None:
    """
    Assert the common RollingStock behaviors that every equipment subtype
    should inherit correctly.
    """
    assert car.asset_id is not None

    assert car.reporting_mark
    assert car.road_number
    assert car.equipment_id == f"{car.reporting_mark} {car.road_number}"

    assert isinstance(car.front_coupler, Coupler)
    assert isinstance(car.rear_coupler, Coupler)

    assert car.front_coupler.owner is car
    assert car.rear_coupler.owner is car

    assert car.front_coupler.position == CouplerPosition.FRONT
    assert car.rear_coupler.position == CouplerPosition.REAR

    assert car.front_coupler is not car.rear_coupler

    assert car.front_coupler.coupler_id != car.rear_coupler.coupler_id

    assert car.front_coupler.connected_to is None
    assert car.rear_coupler.connected_to is None
