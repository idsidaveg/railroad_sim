from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from railroad_sim.domain.enums import IntermodalCarType
from railroad_sim.domain.rolling_stock import RollingStock


@dataclass(slots=True)
class IntermodalCar(RollingStock):
    """
    Represents an intermodal car in the railroad simulator.

    Intermodal cars carry externally defined cargo units such as
    containers or trailers rather than loose commodity loads.
    """

    intermodal_car_type: IntermodalCarType = IntermodalCarType.WELL_CAR
    well_count: int = 1
    max_load_units: int = 2
    articulated: bool = False
    load_limit_lbs: float | None = None

    current_units_loaded: int = 0

    def __post_init__(
        self,
        asset_id_value: UUID | None,
        created_at_value: datetime | None,
    ) -> None:
        super(IntermodalCar, self).__post_init__(asset_id_value, created_at_value)

        if self.well_count <= 0:
            raise ValueError("well_count must be positive.")

        if self.max_load_units <= 0:
            raise ValueError("max_load_units must be positive.")

        if self.load_limit_lbs is not None and self.load_limit_lbs <= 0:
            raise ValueError("load_limit_lbs must be positive when provided.")

        if self.current_units_loaded < 0:
            raise ValueError("current_units_loaded cannot be negative.")

        if self.current_units_loaded > self.max_load_units:
            raise ValueError("current_units_loaded cannot exceed max_load_units.")

    @property
    def is_loaded(self) -> bool:
        return self.current_units_loaded > 0

    @property
    def equipment_class(self) -> str:
        return "INTERMODAL"

    @property
    def equipment_short_name(self) -> str:
        return "IM"

    def load_units(self, unit_count: int) -> None:
        if unit_count <= 0:
            raise ValueError("unit_count must be positive.")

        if self.current_units_loaded + unit_count > self.max_load_units:
            raise ValueError("Loading would exceed max_load_units.")

        self.current_units_loaded += unit_count

    def unload_units(self, unit_count: int) -> None:
        if unit_count <= 0:
            raise ValueError("unit_count must be positive.")

        if unit_count > self.current_units_loaded:
            raise ValueError("Cannot unload more units than currently loaded.")

        self.current_units_loaded -= unit_count

    def __str__(self) -> str:
        return (
            f"{self.equipment_id} "
            f"({self.intermodal_car_type.value}, "
            f"{self.current_units_loaded}/{self.max_load_units} units)"
        )

    def __repr__(self) -> str:
        return (
            f"IntermodalCar("
            f"{self.equipment_id}, "
            f"type={self.intermodal_car_type.value}, "
            f"units={self.current_units_loaded}/{self.max_load_units}"
            f")"
        )
