from __future__ import annotations

from railroad_sim.domain.consist import Consist
from railroad_sim.domain.rolling_stock import RollingStock
from tests.support.rolling_stock_builders import make_car


def connect_cars_in_order(*cars: RollingStock) -> tuple[RollingStock, ...]:
    """
    Connect cars head-to-rear in the order provided.

    Example:
        A, B, C -> A.rear <-> B.front, B.rear <-> C.front
    """
    for left, right in zip(cars, cars[1:]):
        left.rear_coupler.connect(right.front_coupler)
    return cars


def build_car_chain(
    *road_numbers: str, reporting_mark: str = "UP"
) -> tuple[RollingStock, ...]:
    """
    Build and connect a chain of cars in the requested order.

    Example:
        build_car_chain("1001", "1002", "1003")
    """
    cars = tuple(
        make_car(reporting_mark=reporting_mark, road_number=road_number)
        for road_number in road_numbers
    )
    connect_cars_in_order(*cars)
    return cars


def make_single_car_consist(
    reporting_mark: str = "UP",
    road_number: str = "1001",
) -> Consist:
    car = make_car(reporting_mark=reporting_mark, road_number=road_number)
    return Consist(anchor=car)


def make_consist(*road_numbers: str, reporting_mark: str = "UP") -> Consist:
    """
    Build a consist from one or more road numbers.

    If one road number is provided, returns a single-car consist.
    If multiple are provided, cars are connected in the same order.

    Anchor is the first car.
    """
    if not road_numbers:
        road_numbers = ("1001",)

    cars = build_car_chain(*road_numbers, reporting_mark=reporting_mark)
    return Consist(anchor=cars[0])


def build_three_car_chain() -> tuple[RollingStock, RollingStock, RollingStock]:
    a, b, c = build_car_chain("1001", "1002", "1003")
    return a, b, c


def build_six_car_chain() -> tuple[
    RollingStock,
    RollingStock,
    RollingStock,
    RollingStock,
    RollingStock,
    RollingStock,
]:
    a, b, c, d, e, f = build_car_chain("1001", "1002", "1003", "1004", "1005", "1006")
    return a, b, c, d, e, f


def build_two_two_car_consists() -> tuple[
    RollingStock,
    RollingStock,
    RollingStock,
    RollingStock,
    Consist,
    Consist,
]:
    a, b = build_car_chain("1001", "1002")
    c, d = build_car_chain("1003", "1004")

    left = Consist(anchor=a)
    right = Consist(anchor=c)

    return a, b, c, d, left, right
