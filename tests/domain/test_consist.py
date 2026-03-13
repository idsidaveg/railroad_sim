import pytest

from railroad_sim.domain.consist import Consist
from railroad_sim.domain.exceptions import (
    ConsistOperationError,
    ConsistTopologyError,
)
from railroad_sim.domain.rolling_stock import RollingStock
from tests.support.consist_builders import build_three_car_chain


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

    c.rear_coupler.connect(a.front_coupler)

    with pytest.raises(ConsistTopologyError):
        Consist(anchor=b)


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


def test_rolling_stock_cannot_belong_to_multiple_consists():
    a, b, c = build_three_car_chain()

    Consist(anchor=b)

    with pytest.raises(ConsistOperationError):
        Consist(anchor=a)


# consist mergin
def build_two_two_car_consists():
    a = RollingStock("UP", "1001")
    b = RollingStock("UP", "1002")
    c = RollingStock("UP", "1003")
    d = RollingStock("UP", "1004")

    a.rear_coupler.connect(b.front_coupler)
    c.rear_coupler.connect(d.front_coupler)

    left = Consist(anchor=a)
    right = Consist(anchor=c)

    return a, b, c, d, left, right


def test_merge_two_two_car_consists():
    a, b, c, d, left, right = build_two_two_car_consists()

    merged = left.merge_with(
        right,
        self_coupler=b.rear_coupler,
        other_coupler=c.front_coupler,
    )

    assert merged.ordered_equipment() == [a, b, c, d]
    assert b.rear_coupler.connected_to is c.front_coupler
    assert c.front_coupler.connected_to is b.rear_coupler


def test_merge_two_single_car_consists():
    a = RollingStock("UP", "1001")
    b = RollingStock("UP", "1002")

    left = Consist(anchor=a)
    right = Consist(anchor=b)

    merged = left.merge_with(
        right,
        self_coupler=a.rear_coupler,
        other_coupler=b.front_coupler,
    )

    assert merged.ordered_equipment() == [a, b]


def test_merge_single_car_with_multi_car_consist():
    a = RollingStock("UP", "1001")
    b = RollingStock("UP", "1002")
    c = RollingStock("UP", "1003")

    b.rear_coupler.connect(c.front_coupler)

    single = Consist(anchor=a)
    multi = Consist(anchor=b)

    merged = single.merge_with(
        multi,
        self_coupler=a.rear_coupler,
        other_coupler=b.front_coupler,
    )

    assert merged.ordered_equipment() == [a, b, c]


def test_merge_retires_old_consists_and_registers_new_one():
    a, b, c, d, left, right = build_two_two_car_consists()

    left_id = left.consist_id
    right_id = right.consist_id

    merged = left.merge_with(
        right,
        self_coupler=b.rear_coupler,
        other_coupler=c.front_coupler,
    )

    assert Consist.get_by_id(left_id) is None
    assert Consist.get_by_id(right_id) is None
    assert Consist.get_by_id(merged.consist_id) is merged

    assert Consist.get_consist_for_asset(a.asset_id) is merged
    assert Consist.get_consist_for_asset(b.asset_id) is merged
    assert Consist.get_consist_for_asset(c.asset_id) is merged
    assert Consist.get_consist_for_asset(d.asset_id) is merged


def test_merge_with_self_raises_error():
    a, b, c, d, left, right = build_two_two_car_consists()

    with pytest.raises(
        ConsistOperationError, match="Cannot merge a consist with itself"
    ):
        left.merge_with(
            left,
            self_coupler=b.rear_coupler,
            other_coupler=a.front_coupler,
        )


def test_merge_with_inactive_consist_raises_error():
    a, b, c, d, left, right = build_two_two_car_consists()

    left._release_registry_claims(equipment=left.ordered_equipment())

    with pytest.raises(ConsistOperationError, match="is not active"):
        left.merge_with(
            right,
            self_coupler=b.rear_coupler,
            other_coupler=c.front_coupler,
        )


def test_merge_raises_if_self_coupler_does_not_belong_to_self():
    a, b, c, d, left, right = build_two_two_car_consists()

    with pytest.raises(
        ConsistOperationError,
        match="self_coupler does not belong to this consist",
    ):
        left.merge_with(
            right,
            self_coupler=c.front_coupler,
            other_coupler=d.rear_coupler,
        )


def test_merge_raises_if_other_coupler_does_not_belong_to_other():
    a, b, c, d, left, right = build_two_two_car_consists()

    with pytest.raises(
        ConsistOperationError,
        match="other_coupler does not belong to the other consist",
    ):
        left.merge_with(
            right,
            self_coupler=b.rear_coupler,
            other_coupler=a.front_coupler,
        )


def test_merge_raises_if_self_coupler_is_not_exposed_end():
    a, b, c, d, left, right = build_two_two_car_consists()

    with pytest.raises(
        ConsistOperationError,
        match="self_coupler is not an exposed end coupler",
    ):
        left.merge_with(
            right,
            self_coupler=a.rear_coupler,
            other_coupler=c.front_coupler,
        )


def test_merge_raises_if_other_coupler_is_not_exposed_end():
    a, b, c, d, left, right = build_two_two_car_consists()

    with pytest.raises(
        ConsistOperationError,
        match="other_coupler is not an exposed end coupler",
    ):
        left.merge_with(
            right,
            self_coupler=b.rear_coupler,
            other_coupler=d.front_coupler,
        )
