from __future__ import annotations

from datetime import datetime
from uuid import UUID

from railroad_sim.domain.rolling_stock import RollingStock


def make_rolling_stock(
    reporting_mark: str = "UP",
    road_number: str = "1001",
    *,
    owner: str | None = None,
    asset_id_value: UUID | None = None,
    created_at_value: datetime | None = None,
) -> RollingStock:
    return RollingStock(
        reporting_mark=reporting_mark,
        road_number=road_number,
        owner=owner,
        asset_id_value=asset_id_value,
        created_at_value=created_at_value,
    )


def make_car(
    reporting_mark: str = "UP",
    road_number: str = "1001",
    *,
    owner: str | None = None,
    asset_id_value: UUID | None = None,
    created_at_value: datetime | None = None,
) -> RollingStock:
    return make_rolling_stock(
        reporting_mark=reporting_mark,
        road_number=road_number,
        owner=owner,
        asset_id_value=asset_id_value,
        created_at_value=created_at_value,
    )


def make_locomotive(
    road_number: str = "1001",
    *,
    reporting_mark: str = "UP",
    owner: str | None = None,
    asset_id_value: UUID | None = None,
    created_at_value: datetime | None = None,
) -> RollingStock:
    return make_rolling_stock(
        reporting_mark=reporting_mark,
        road_number=road_number,
        owner=owner,
        asset_id_value=asset_id_value,
        created_at_value=created_at_value,
    )


def make_boxcar(
    road_number: str = "1001",
    *,
    reporting_mark: str = "UP",
    owner: str | None = None,
    asset_id_value: UUID | None = None,
    created_at_value: datetime | None = None,
) -> RollingStock:
    return make_rolling_stock(
        reporting_mark=reporting_mark,
        road_number=road_number,
        owner=owner,
        asset_id_value=asset_id_value,
        created_at_value=created_at_value,
    )


def make_tank_car(
    road_number: str = "1001",
    *,
    reporting_mark: str = "UTLX",
    owner: str | None = None,
    asset_id_value: UUID | None = None,
    created_at_value: datetime | None = None,
) -> RollingStock:
    return make_rolling_stock(
        reporting_mark=reporting_mark,
        road_number=road_number,
        owner=owner,
        asset_id_value=asset_id_value,
        created_at_value=created_at_value,
    )


def make_rolling_stock_pair(
    left_reporting_mark: str = "UP",
    left_road_number: str = "1001",
    right_reporting_mark: str = "BNSF",
    right_road_number: str = "2001",
) -> tuple[RollingStock, RollingStock]:
    left = make_rolling_stock(
        reporting_mark=left_reporting_mark,
        road_number=left_road_number,
    )
    right = make_rolling_stock(
        reporting_mark=right_reporting_mark,
        road_number=right_road_number,
    )
    return left, right


def make_rolling_stock_sequence(
    *road_numbers: str,
    reporting_mark: str = "UP",
) -> list[RollingStock]:
    if road_numbers:
        return [
            make_rolling_stock(
                reporting_mark=reporting_mark,
                road_number=road_number,
            )
            for road_number in road_numbers
        ]

    return [make_rolling_stock(reporting_mark=reporting_mark)]
