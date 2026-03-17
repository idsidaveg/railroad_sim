from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from railroad_sim.domain.enums import GondolaService, GondolaType
from railroad_sim.domain.rolling_stock import RollingStock


@dataclass(slots=True)
class Gondola(RollingStock):
    """
    Represents a gondola in the railroad simulator.

    Gondolas are open-top cars used for bulk, scrap, steel, and other
    rugged commodity service.
    """

    gondola_type: GondolaType = GondolaType.GENERAL_SERVICE
    service_type: GondolaService = GondolaService.GENERAL
    inside_length_ft: float = 52.0
    cubic_capacity_ft3: float | None = None
    load_limit_lbs: float | None = None

    current_commodity: str | None = None
    last_commodity: str | None = None
    is_cleaned: bool = True

    def __post_init__(
        self,
        asset_id_value: UUID | None,
        created_at_value: datetime | None,
    ) -> None:
        super(Gondola, self).__post_init__(asset_id_value, created_at_value)

        if self.inside_length_ft <= 0:
            raise ValueError("inside_length_ft must be positive.")

        if self.cubic_capacity_ft3 is not None and self.cubic_capacity_ft3 <= 0:
            raise ValueError("cubic_capacity_ft3 must be positive when provided.")

        if self.load_limit_lbs is not None and self.load_limit_lbs <= 0:
            raise ValueError("load_limit_lbs must be positive when provided.")

        if self.current_commodity is not None:
            self.is_cleaned = False

    @property
    def is_loaded(self) -> bool:
        return self.current_commodity is not None

    @property
    def equipment_class(self) -> str:
        return "GONDOLA"

    @property
    def equipment_short_name(self) -> str:
        return "GON"

    def can_load_commodity(self, commodity: str) -> bool:
        if not commodity or not commodity.strip():
            return False

        if self.is_loaded:
            return False

        return True

    def load_commodity(self, commodity: str) -> None:
        if not commodity or not commodity.strip():
            raise ValueError("commodity must be a non-empty string.")

        if self.is_loaded:
            raise ValueError("Gondola is already loaded.")

        self.current_commodity = commodity
        self.is_cleaned = False

    def unload_commodity(self) -> str:
        if self.current_commodity is None:
            raise ValueError("Gondola is not currently loaded.")

        unloaded = self.current_commodity
        self.last_commodity = unloaded
        self.current_commodity = None
        self.is_cleaned = False
        return unloaded

    def clean_gondola(self) -> None:
        self.is_cleaned = True

    def __str__(self) -> str:
        commodity_text = self.current_commodity if self.current_commodity else "empty"
        return (
            f"{self.equipment_id} "
            f"({self.gondola_type.value}, {self.inside_length_ft:g} ft, "
            f"{commodity_text})"
        )

    def __repr__(self) -> str:
        return (
            f"Gondola("
            f"{self.equipment_id}, "
            f"type={self.gondola_type.value}, "
            f"service={self.service_type.value}, "
            f"loaded={self.is_loaded}"
            f")"
        )
