from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from railroad_sim.domain.enums import (
    TankCarService,
    TankCarThermalProtection,
    TankCarType,
)
from railroad_sim.domain.rolling_stock import RollingStock


@dataclass(slots=True)
class TankCar(RollingStock):
    """
    Represents a tank car in the railroad simulator.

    Tank cars are used to transport liquid or gaseous commodities and may
    be configured for general, pressure, or cryogenic service.

    This model also tracks basic contamination-sensitive operating state:
    - current commodity
    - last commodity
    - cleaning state
    """

    tankcar_type: TankCarType = TankCarType.GENERAL_SERVICE
    service_type: TankCarService = TankCarService.GENERAL
    thermal_protection: TankCarThermalProtection = TankCarThermalProtection.NONE

    capacity_gallons: float = 30000.0
    commodity: str | None = None
    hazmat_class: str | None = None
    is_pressurized: bool = False
    load_limit_lbs: float | None = None
    tank_material: str | None = None

    current_commodity: str | None = None
    last_commodity: str | None = None
    is_cleaned: bool = True

    def __post_init__(
        self,
        asset_id_value: UUID | None,
        created_at_value: datetime | None,
    ) -> None:
        super(TankCar, self).__post_init__(asset_id_value, created_at_value)

        if self.capacity_gallons <= 0:
            raise ValueError("capacity_gallons must be positive.")

        if self.load_limit_lbs is not None and self.load_limit_lbs <= 0:
            raise ValueError("load_limit_lbs must be positive when provided.")

        if self.tankcar_type == TankCarType.PRESSURE and not self.is_pressurized:
            raise ValueError("PRESSURE tank cars must have is_pressurized=True.")

        if self.tankcar_type == TankCarType.CRYOGENIC and not self.is_pressurized:
            raise ValueError("CRYOGENIC tank cars must have is_pressurized=True.")

        if self.service_type == TankCarService.FOOD_GRADE:
            if (
                self.tank_material is not None
                and self.tank_material.lower() != "stainless_steel"
            ):
                raise ValueError(
                    "FOOD_GRADE tank cars must use stainless_steel when "
                    "tank_material is provided."
                )

        if self.current_commodity is not None and self.commodity is None:
            self.commodity = self.current_commodity

        if self.current_commodity is not None:
            self.is_cleaned = False

        if self.tare_weight_lb == 0.0:
            self.tare_weight_lb = 90_000.0

    @property
    def operational_length_ft(self) -> float:
        return 60.0

    @property
    def is_loaded(self) -> bool:
        """Return True if the tank car is currently loaded."""
        return self.current_commodity is not None

    @property
    def equipment_class(self) -> str:
        if self.tankcar_type == TankCarType.CRYOGENIC:
            return "CRYO_TANK"

        if self.tankcar_type == TankCarType.PRESSURE:
            return "PRESSURE_TANK"

        return "TANK"

    @property
    def equipment_short_name(self) -> str:
        if self.tankcar_type == TankCarType.CRYOGENIC:
            return "CRYO"

        if self.tankcar_type == TankCarType.PRESSURE:
            return "PTNK"

        return "TANK"

    def can_load_commodity(self, commodity: str, *, food_grade: bool = False) -> bool:
        """
        Return True if the provided commodity may be loaded based on the
        car's current compatibility and contamination state.
        """
        if not commodity or not commodity.strip():
            return False

        if self.is_loaded:
            return False

        if food_grade and self.service_type != TankCarService.FOOD_GRADE:
            return False

        if food_grade and not self.is_cleaned:
            return False

        if food_grade and self.last_commodity is not None and not self.is_cleaned:
            return False

        return True

    def load_commodity(self, commodity: str, *, food_grade: bool = False) -> None:
        """
        Load a commodity into the tank car.

        Rules enforced:
        - commodity must be non-empty
        - car must not already be loaded
        - food-grade loads require FOOD_GRADE service
        - food-grade loads require cleaned state
        """
        if not commodity or not commodity.strip():
            raise ValueError("commodity must be a non-empty string.")

        if self.is_loaded:
            raise ValueError("Tank car is already loaded.")

        if food_grade and self.service_type != TankCarService.FOOD_GRADE:
            raise ValueError("Food-grade commodities require a FOOD_GRADE tank car.")

        if food_grade and not self.is_cleaned:
            raise ValueError("Food-grade commodities require a cleaned tank car.")

        self.current_commodity = commodity
        self.commodity = commodity
        self.is_cleaned = False

    def unload_commodity(self) -> str:
        """
        Unload the current commodity.

        Returns:
            The commodity that was removed.

        Raises:
            ValueError: if the tank car is not currently loaded.
        """
        if self.current_commodity is None:
            raise ValueError("Tank car is not currently loaded.")

        unloaded = self.current_commodity
        self.last_commodity = unloaded
        self.current_commodity = None
        self.commodity = None
        self.is_cleaned = False
        return unloaded

    def clean_tank(self) -> None:
        """
        Mark the tank as cleaned and ready for a compatible future load.
        """
        self.is_cleaned = True

    def __str__(self) -> str:
        commodity_text = (
            self.current_commodity if self.current_commodity is not None else "empty"
        )
        return (
            f"{self.equipment_id} "
            f"({self.tankcar_type.value}, {self.capacity_gallons:g} gal, "
            f"{commodity_text})"
        )

    def __repr__(self) -> str:
        return (
            f"TankCar("
            f"{self.equipment_id}, "
            f"type={self.tankcar_type.value}, "
            f"service={self.service_type.value}, "
            f"capacity_gallons={self.capacity_gallons:g}, "
            f"loaded={self.is_loaded}"
            f")"
        )
