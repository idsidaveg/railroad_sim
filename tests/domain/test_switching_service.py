import pytest

from railroad_sim.domain.consist import Consist
from railroad_sim.domain.exceptions import ConsistOperationError
from railroad_sim.domain.rolling_stock import RollingStock
from railroad_sim.domain.switching_service import SwitchingService


def build_three_car_chain():
    a = RollingStock("UP", "1001")
    b = RollingStock("UP", "1002")
    c = RollingStock("UP", "1003")

    a.rear_coupler.connect(b.front_coupler)
    b.rear_coupler.connect(c.front_coupler)

    return a, b, c


def build_six_car_chain():
    a = RollingStock("UP", "1001")
    b = RollingStock("UP", "1002")
    c = RollingStock("UP", "1003")
    d = RollingStock("UP", "1004")
    e = RollingStock("UP", "1005")
    f = RollingStock("UP", "1006")

    a.rear_coupler.connect(b.front_coupler)
    b.rear_coupler.connect(c.front_coupler)
    c.rear_coupler.connect(d.front_coupler)
    d.rear_coupler.connect(e.front_coupler)
    e.rear_coupler.connect(f.front_coupler)

    return a, b, c, d, e, f


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


def test_cut_after_delegates_to_consist_split_after():
    a, b, c = build_three_car_chain()
    consist = Consist(anchor=b)

    left, right = SwitchingService.cut_after(consist, b)

    assert left.ordered_equipment() == [a, b]
    assert right.ordered_equipment() == [c]


def test_cut_before_delegates_to_consist_split_before():
    a, b, c = build_three_car_chain()
    consist = Consist(anchor=b)

    left, right = SwitchingService.cut_before(consist, b)

    assert left.ordered_equipment() == [a]
    assert right.ordered_equipment() == [b, c]


def test_couple_delegates_to_consist_merge_with():
    a, b, c, d, left, right = build_two_two_car_consists()

    merged = SwitchingService.couple(
        left,
        right,
        left_coupler=b.rear_coupler,
        right_coupler=c.front_coupler,
    )

    assert merged.ordered_equipment() == [a, b, c, d]


def test_setout_block_from_middle():
    a, b, c, d, e, f = build_six_car_chain()
    consist = Consist(anchor=c)

    remaining, setout = SwitchingService.setout_block(consist, c, d)

    assert remaining.ordered_equipment() == [a, b, e, f]
    assert setout.ordered_equipment() == [c, d]


def test_setout_block_from_head_end():
    a, b, c, d, e, f = build_six_car_chain()
    consist = Consist(anchor=c)

    remaining, setout = SwitchingService.setout_block(consist, a, b)

    assert remaining.ordered_equipment() == [c, d, e, f]
    assert setout.ordered_equipment() == [a, b]


def test_setout_block_from_rear_end():
    a, b, c, d, e, f = build_six_car_chain()
    consist = Consist(anchor=c)

    remaining, setout = SwitchingService.setout_block(consist, e, f)

    assert remaining.ordered_equipment() == [a, b, c, d]
    assert setout.ordered_equipment() == [e, f]


def test_setout_single_car_from_middle():
    a, b, c, d, e, f = build_six_car_chain()
    consist = Consist(anchor=c)

    remaining, setout = SwitchingService.setout_block(consist, d, d)

    assert remaining.ordered_equipment() == [a, b, c, e, f]
    assert setout.ordered_equipment() == [d]


def test_setout_block_raises_if_first_car_not_in_consist():
    a, b, c, d, e, f = build_six_car_chain()
    outsider = RollingStock("BNSF", "9999")
    consist = Consist(anchor=c)

    with pytest.raises(ConsistOperationError, match="is not part of this consist"):
        SwitchingService.setout_block(consist, outsider, d)


def test_setout_block_raises_if_last_car_not_in_consist():
    a, b, c, d, e, f = build_six_car_chain()
    outsider = RollingStock("BNSF", "9999")
    consist = Consist(anchor=c)

    with pytest.raises(ConsistOperationError, match="is not part of this consist"):
        SwitchingService.setout_block(consist, c, outsider)


def test_setout_block_raises_if_first_car_after_last_car():
    a, b, c, d, e, f = build_six_car_chain()
    consist = Consist(anchor=c)

    with pytest.raises(
        ConsistOperationError,
        match="first_car to appear before last_car",
    ):
        SwitchingService.setout_block(consist, e, c)


def test_setout_block_raises_if_entire_consist_selected():
    a, b, c, d, e, f = build_six_car_chain()
    consist = Consist(anchor=c)

    with pytest.raises(ConsistOperationError, match="entire consist"):
        SwitchingService.setout_block(consist, a, f)


def test_pickup_block_appends_block_to_rear_of_train():
    a = RollingStock("UP", "1001")
    b = RollingStock("UP", "1002")
    c = RollingStock("UP", "1003")
    d = RollingStock("UP", "1004")

    a.rear_coupler.connect(b.front_coupler)
    c.rear_coupler.connect(d.front_coupler)

    train_consist = Consist(anchor=a)
    block_consist = Consist(anchor=c)

    merged = SwitchingService.pickup_block(train_consist, block_consist)

    assert merged.ordered_equipment() == [a, b, c, d]


def test_append_consist_joins_two_consists_in_order():
    a = RollingStock("UP", "1001")
    b = RollingStock("UP", "1002")
    c = RollingStock("UP", "1003")
    d = RollingStock("UP", "1004")

    a.rear_coupler.connect(b.front_coupler)
    c.rear_coupler.connect(d.front_coupler)

    left = Consist(anchor=a)
    right = Consist(anchor=c)

    merged = SwitchingService.append_consist(left, right)

    assert merged.ordered_equipment() == [a, b, c, d]


def test_insert_block_inserts_block_after_specified_car():
    a = RollingStock("UP", "1001")
    b = RollingStock("UP", "1002")
    e = RollingStock("UP", "1005")
    f = RollingStock("UP", "1006")
    c = RollingStock("UP", "1003")
    d = RollingStock("UP", "1004")

    a.rear_coupler.connect(b.front_coupler)
    e.rear_coupler.connect(f.front_coupler)
    c.rear_coupler.connect(d.front_coupler)

    base = Consist(anchor=a)
    tail = Consist(anchor=e)
    block = Consist(anchor=c)

    base_with_tail = SwitchingService.append_consist(base, tail)
    merged = SwitchingService.insert_block(base_with_tail, b, block)

    assert merged.ordered_equipment() == [a, b, c, d, e, f]


def test_insert_single_car_block_after_middle_car():
    a = RollingStock("UP", "1001")
    b = RollingStock("UP", "1002")
    d = RollingStock("UP", "1004")
    x = RollingStock("UP", "1999")

    a.rear_coupler.connect(b.front_coupler)
    b.rear_coupler.connect(d.front_coupler)

    base = Consist(anchor=b)
    block = Consist(anchor=x)

    merged = SwitchingService.insert_block(base, b, block)

    assert merged.ordered_equipment() == [a, b, x, d]


def test_insert_block_after_rear_end_appends_block():
    a = RollingStock("UP", "1001")
    b = RollingStock("UP", "1002")
    c = RollingStock("UP", "1003")
    d = RollingStock("UP", "1004")

    a.rear_coupler.connect(b.front_coupler)
    c.rear_coupler.connect(d.front_coupler)

    base = Consist(anchor=a)
    block = Consist(anchor=c)

    merged = SwitchingService.insert_block(base, b, block)

    assert merged.ordered_equipment() == [a, b, c, d]


def test_insert_block_raises_if_after_car_not_in_consist():
    a, b, c = build_three_car_chain()
    outsider = RollingStock("BNSF", "9999")
    x = RollingStock("UP", "2000")

    base = Consist(anchor=b)
    block = Consist(anchor=x)

    with pytest.raises(ConsistOperationError, match="is not part of this consist"):
        SwitchingService.insert_block(base, outsider, block)


def test_pickup_block_retires_old_consists_and_registers_new_one():
    a = RollingStock("UP", "1001")
    b = RollingStock("UP", "1002")
    c = RollingStock("UP", "1003")
    d = RollingStock("UP", "1004")

    a.rear_coupler.connect(b.front_coupler)
    c.rear_coupler.connect(d.front_coupler)

    train_consist = Consist(anchor=a)
    block_consist = Consist(anchor=c)

    train_id = train_consist.consist_id
    block_id = block_consist.consist_id

    merged = SwitchingService.pickup_block(train_consist, block_consist)

    assert Consist.get_by_id(train_id) is None
    assert Consist.get_by_id(block_id) is None
    assert Consist.get_by_id(merged.consist_id) is merged

    assert Consist.get_consist_for_asset(a.asset_id) is merged
    assert Consist.get_consist_for_asset(b.asset_id) is merged
    assert Consist.get_consist_for_asset(c.asset_id) is merged
    assert Consist.get_consist_for_asset(d.asset_id) is merged
