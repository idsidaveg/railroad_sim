import pytest

from railroad_sim.domain.exceptions import (
    CouplerConnectionError,
    CouplerStateError,
)
from railroad_sim.domain.rolling_stock import RollingStock


def test_couplers_connect_successfully():
    car_a = RollingStock(reporting_mark="UP", road_number="1001")
    car_b = RollingStock(reporting_mark="BNSF", road_number="2002")

    front = car_a.front_coupler
    rear = car_b.rear_coupler

    front.connect(rear)

    assert front.connected_to is rear
    assert rear.connected_to is front
    assert front.is_connected is True
    assert rear.is_connected is True


def test_coupler_cannot_connect_to_itself():
    car = RollingStock(reporting_mark="UP", road_number="1001")
    coupler = car.front_coupler

    with pytest.raises(CouplerConnectionError):
        coupler.connect(coupler)

    assert coupler.connected_to is None
    assert coupler.is_connected is False


def test_couplers_on_same_rolling_stock_cannot_connect():
    car = RollingStock(reporting_mark="UP", road_number="1001")

    with pytest.raises(CouplerConnectionError):
        car.front_coupler.connect(car.rear_coupler)

    assert car.front_coupler.connected_to is None
    assert car.rear_coupler.connected_to is None


def test_damaged_source_coupler_cannot_connect():
    car_a = RollingStock(reporting_mark="UP", road_number="1001")
    car_b = RollingStock(reporting_mark="BNSF", road_number="2002")

    damaged = car_a.front_coupler
    other = car_b.rear_coupler
    damaged.is_damaged = True

    with pytest.raises(CouplerStateError):
        damaged.connect(other)

    assert damaged.connected_to is None
    assert other.connected_to is None
    assert damaged.is_connected is False
    assert other.is_connected is False


def test_damaged_target_coupler_cannot_connect():
    car_a = RollingStock(reporting_mark="UP", road_number="1001")
    car_b = RollingStock(reporting_mark="BNSF", road_number="2002")

    source = car_a.front_coupler
    damaged = car_b.rear_coupler
    damaged.is_damaged = True

    with pytest.raises(CouplerStateError):
        source.connect(damaged)

    assert source.connected_to is None
    assert damaged.connected_to is None
    assert source.is_connected is False
    assert damaged.is_connected is False


def test_already_connected_coupler_cannot_connect_again():
    car_a = RollingStock(reporting_mark="UP", road_number="1001")
    car_b = RollingStock(reporting_mark="BNSF", road_number="2002")
    car_c = RollingStock(reporting_mark="CSXT", road_number="3003")

    a = car_a.front_coupler
    b = car_b.rear_coupler
    c = car_c.front_coupler

    a.connect(b)

    with pytest.raises(CouplerConnectionError):
        a.connect(c)

    assert a.connected_to is b
    assert b.connected_to is a
    assert c.connected_to is None
    assert a.is_connected is True
    assert b.is_connected is True
    assert c.is_connected is False


def test_target_already_connected_coupler_cannot_accept_new_connection():
    car_a = RollingStock(reporting_mark="UP", road_number="1001")
    car_b = RollingStock(reporting_mark="BNSF", road_number="2002")
    car_c = RollingStock(reporting_mark="CSXT", road_number="3003")

    a = car_a.front_coupler
    b = car_b.rear_coupler
    c = car_c.front_coupler

    a.connect(b)

    with pytest.raises(CouplerConnectionError):
        c.connect(b)

    assert a.connected_to is b
    assert b.connected_to is a
    assert c.connected_to is None
    assert a.is_connected is True
    assert b.is_connected is True
    assert c.is_connected is False


def test_disconnect_clears_both_sides():
    car_a = RollingStock(reporting_mark="UP", road_number="1001")
    car_b = RollingStock(reporting_mark="BNSF", road_number="2002")

    front = car_a.front_coupler
    rear = car_b.rear_coupler

    front.connect(rear)
    front.disconnect()

    assert front.connected_to is None
    assert rear.connected_to is None
    assert front.is_connected is False
    assert rear.is_connected is False


def test_disconnect_of_unconnected_coupler_raises_error():
    car = RollingStock(reporting_mark="UP", road_number="1001")
    coupler = car.front_coupler

    with pytest.raises(CouplerStateError):
        coupler.disconnect()

    assert coupler.connected_to is None
    assert coupler.is_connected is False


def test_disconnect_only_affects_connected_pair():
    car_a = RollingStock(reporting_mark="UP", road_number="1001")
    car_b = RollingStock(reporting_mark="BNSF", road_number="2002")
    car_c = RollingStock(reporting_mark="CSXT", road_number="3003")

    a_rear = car_a.rear_coupler
    b_front = car_b.front_coupler
    b_rear = car_b.rear_coupler
    c_front = car_c.front_coupler

    a_rear.connect(b_front)
    b_rear.connect(c_front)

    b_rear.disconnect()

    assert a_rear.connected_to is b_front
    assert b_front.connected_to is a_rear
    assert a_rear.is_connected is True
    assert b_front.is_connected is True

    assert b_rear.connected_to is None
    assert c_front.connected_to is None
    assert b_rear.is_connected is False
    assert c_front.is_connected is False


def test_disconnect_detects_inconsistent_connection_state():
    car_a = RollingStock(reporting_mark="UP", road_number="1001")
    car_b = RollingStock(reporting_mark="BNSF", road_number="2002")

    a = car_a.front_coupler
    b = car_b.rear_coupler

    a.connect(b)

    # Intentionally corrupt the internal state
    b.connected_to = None

    with pytest.raises(CouplerStateError):
        a.disconnect()
