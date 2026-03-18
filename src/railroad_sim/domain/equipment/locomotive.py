from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from railroad_sim.domain.enums import MotivePowerType
from railroad_sim.domain.rolling_stock import RollingStock


@dataclass(slots=True)
class Locomotive(RollingStock):
    """
    Represents a locomotive in the railroad simulator.
    """

    motive_power_type: MotivePowerType = MotivePowerType.DIESEL
    horsepower: int = 4400
    builder: str | None = None
    model: str | None = None
    axle_count: int | None = None
    energy_capacity: float | None = None

    def __post_init__(
        self,
        asset_id_value: UUID | None,
        created_at_value: datetime | None,
    ) -> None:
        super(Locomotive, self).__post_init__(asset_id_value, created_at_value)

        if self.horsepower <= 0:
            raise ValueError("horsepower must be positive.")

        if self.axle_count is not None and self.axle_count <= 0:
            raise ValueError("axle_count must be positive when provided.")

        if self.energy_capacity is not None and self.energy_capacity < 0:
            raise ValueError("energy_capacity cannot be negative.")

    @property
    def operational_length_ft(self) -> float:
        return 73.0

    @property
    def equipment_class(self) -> str:
        return "LOCO"

    @property
    def equipment_short_name(self) -> str:
        return "LOCO"

    def __str__(self) -> str:
        return (
            f"{self.equipment_id} "
            f"({self.motive_power_type.value}, {self.horsepower} hp)"
        )

    def __repr__(self) -> str:
        return (
            f"Locomotive("
            f"{self.equipment_id}, "
            f"type={self.motive_power_type.value}, "
            f"hp={self.horsepower}"
            f")"
        )
