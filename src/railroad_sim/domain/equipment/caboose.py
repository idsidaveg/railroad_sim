from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from railroad_sim.domain.enums import CabooseType
from railroad_sim.domain.rolling_stock import RollingStock


@dataclass(slots=True)
class Caboose(RollingStock):
    """
    Represents a caboose in the railroad simulator.
    """

    caboose_type: CabooseType = CabooseType.STANDARD
    crew_capacity: int = 4
    occupied: bool = False
    has_stove: bool = True
    has_cupola: bool = False
    has_bay_window: bool = False

    def __post_init__(
        self,
        asset_id_value: UUID | None,
        created_at_value: datetime | None,
    ) -> None:
        super(Caboose, self).__post_init__(asset_id_value, created_at_value)

        if self.crew_capacity <= 0:
            raise ValueError("crew_capacity must be positive.")

        if self.caboose_type == CabooseType.CUPOLA and not self.has_cupola:
            raise ValueError("CUPOLA cabooses must have has_cupola=True.")

        if self.caboose_type == CabooseType.BAY_WINDOW and not self.has_bay_window:
            raise ValueError("BAY_WINDOW cabooses must have has_bay_window=True.")

        if self.tare_weight_lb == 0.00:
            self.tare_weight_lb = 44_000.0

    @property
    def operational_length_ft(self) -> float:
        return 40.0

    @property
    def equipment_class(self) -> str:
        return "CABOOSE"

    @property
    def equipment_short_name(self) -> str:
        return "CAB"

    def occupy(self) -> None:
        self.occupied = True

    def vacate(self) -> None:
        self.occupied = False

    def __str__(self) -> str:
        return (
            f"{self.equipment_id} ({self.caboose_type.value}, occupied={self.occupied})"
        )

    def __repr__(self) -> str:
        return (
            f"Caboose("
            f"{self.equipment_id}, "
            f"type={self.caboose_type.value}, "
            f"occupied={self.occupied}"
            f")"
        )
