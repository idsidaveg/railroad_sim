import pytest

from railroad_sim.domain.consist import Consist
from railroad_sim.domain.exceptions import (
    ConsistOperationError,
    ConsistTopologyError,
)
from railroad_sim.domain.rolling_stock import RollingStock


def build_three_car_chain():
    a = RollingStock("UP", "1001")
    b = RollingStock("UP", "1002")
    c = RollingStock("UP", "1003")

    a.rear_coupler.connect(b.front_coupler)
    b.rear_coupler.connect(c.front_coupler)

    return a, b, c


def test_consist_order_three_cars():
    a, b, c = build_three_car_chain()

    consist = Consist(anchor=b)

    ordered = consist.ordered_equipment()

    assert ordered == [a, b, c]


def test_consist_length():
    a, b, c = build_three_car_chain()

    consist = Consist(anchor=b)

    assert len(consist) == 3


def test_head_and_rear_detection():
    a, b, c = build_three_car_chain()

    consist = Consist(anchor=b)

    assert consist.head_end is a
    assert consist.rear_end is c


def test_single_car_consist():
    car = RollingStock("UP", "1001")

    consist = Consist(anchor=car)

    ordered = consist.ordered_equipment()

    assert ordered == [car]


def test_iterating_consist():
    a, b, c = build_three_car_chain()

    consist = Consist(anchor=b)

    result = list(consist)

    assert result == [a, b, c]


def test_consist_detects_circular_topology():
    a, b, c = build_three_car_chain()

    # create an invalid loop:
    # A.rear -> B.front
    # B.rear -> C.front
    # C.rear -> A.front
    c.rear_coupler.connect(a.front_coupler)

    consist = Consist(anchor=b)
    with pytest.raises(ConsistTopologyError):
        consist.ordered_equipment()


# Tests that handle splitting our consist into two pieces
def test_split_after_middle_car():
    a, b, c = build_three_car_chain()

    consist = Consist(anchor=b)

    left, right = consist.split_after(b)

    assert left.ordered_equipment() == [a, b]
    assert right.ordered_equipment() == [c]

    assert b.rear_coupler.connected_to is None
    assert c.front_coupler.connected_to is None


def test_split_before_middle_car():
    a, b, c = build_three_car_chain()

    consist = Consist(anchor=b)

    left, right = consist.split_before(b)

    assert left.ordered_equipment() == [a]
    assert right.ordered_equipment() == [b, c]

    assert a.rear_coupler.connected_to is None
    assert b.front_coupler.connected_to is None


def test_split_after_rear_end_raises_error():
    a, b, c = build_three_car_chain()

    consist = Consist(anchor=b)

    with pytest.raises(ConsistOperationError):
        consist.split_after(c)


def test_split_before_head_end_raises_error():
    a, b, c = build_three_car_chain()

    consist = Consist(anchor=b)

    with pytest.raises(ConsistOperationError):
        consist.split_before(a)


def test_split_after_car_not_in_consist_raises_error():
    a, b, c = build_three_car_chain()
    outsider = RollingStock("BNSF", "9999")

    consist = Consist(anchor=b)

    with pytest.raises(ConsistOperationError):
        consist.split_after(outsider)


def test_split_before_car_not_in_consist_raises_error():
    a, b, c = build_three_car_chain()
    outsider = RollingStock("BNSF", "9999")

    consist = Consist(anchor=b)

    with pytest.raises(ConsistOperationError):
        consist.split_before(outsider)


# Diagnostic tests
def test_consist_diagram_three_cars():
    _, b, _ = build_three_car_chain()

    consist = Consist(anchor=b)

    assert consist.diagram() == "HEAD -> UP 1001 --- UP 1002 --- UP 1003 <- REAR"


def test_consist_diagnostic_dump_contains_anchor():
    _, b, _ = build_three_car_chain()

    consist = Consist(anchor=b)
    dump = consist.diagnostic_dump()

    assert "Anchor: UP 1002" in dump
    assert "[2] UP 1002  [ANCHOR]" in dump


def test_rolling_stock_cannot_exist_in_two_consists():
    a, b, c = build_three_car_chain()

    consist1 = Consist(anchor=b)
    consist2 = Consist(anchor=a)

    ids1 = {car.asset_id for car in consist1.ordered_equipment()}
    ids2 = {car.asset_id for car in consist2.ordered_equipment()}

    assert ids1 == ids2


def test_rolling_stock_cannot_belong_to_multiple_consists():
    a, b, c = build_three_car_chain()

    Consist(anchor=b)

    with pytest.raises(ConsistOperationError):
        Consist(anchor=a)
