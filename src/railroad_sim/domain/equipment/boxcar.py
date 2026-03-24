from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from railroad_sim.domain.enums import (
    BoxCarService,
    BoxCarThermalProtection,
    BoxCarType,
)
from railroad_sim.domain.rolling_stock import RollingStock


@dataclass(slots=True)
class BoxCar(RollingStock):
    """
    Represents a boxcar in the railroad simulator.

    Boxcars are enclosed freight cars used for general merchandise,
    paper products, appliances, food products, and similar loads.

    This model tracks basic contamination-sensitive operating state:
    - current commodity
    - last commodity
    - cleaning state
    """

    boxcar_type: BoxCarType = BoxCarType.STANDARD
    service_type: BoxCarService = BoxCarService.GENERAL
    thermal_protection: BoxCarThermalProtection = BoxCarThermalProtection.NONE

    inside_length_ft: float = 50.0
    cubic_capacity_ft3: float | None = None
    door_count: int = 1
    load_limit_lbs: float | None = None

    current_commodity: str | None = None
    last_commodity: str | None = None
    is_cleaned: bool = True

    def __post_init__(
        self,
        asset_id_value: UUID | None,
        created_at_value: datetime | None,
    ) -> None:
        super(BoxCar, self).__post_init__(asset_id_value, created_at_value)

        if self.inside_length_ft <= 0:
            raise ValueError("inside_length_ft must be positive.")

        if self.cubic_capacity_ft3 is not None and self.cubic_capacity_ft3 <= 0:
            raise ValueError("cubic_capacity_ft3 must be positive when provided.")

        if self.door_count <= 0:
            raise ValueError("door_count must be positive.")

        if self.load_limit_lbs is not None and self.load_limit_lbs <= 0:
            raise ValueError("load_limit_lbs must be positive when provided.")

        if (
            self.boxcar_type == BoxCarType.REFRIGERATED
            and self.thermal_protection != BoxCarThermalProtection.REFRIGERATED
        ):
            raise ValueError(
                "REFRIGERATED boxcars must use REFRIGERATED thermal protection."
            )

        if (
            self.boxcar_type == BoxCarType.INSULATED
            and self.thermal_protection == BoxCarThermalProtection.NONE
        ):
            raise ValueError(
                "INSULATED boxcars must use insulated or refrigerated thermal protection."
            )

        if self.current_commodity is not None:
            self.is_cleaned = False

        if self.tare_weight_lb == 0.0:
            if self.boxcar_type == BoxCarType.REFRIGERATED:
                self.tare_weight_lb = 102_000.0
            else:
                self.tare_weight_lb = 73_000.0

    @property
    def operational_length_ft(self) -> float:
        return 55.0

    @property
    def is_loaded(self) -> bool:
        """Return True if the boxcar is currently loaded."""
        return self.current_commodity is not None

    @property
    def equipment_class(self) -> str:
        if self.boxcar_type == BoxCarType.REFRIGERATED:
            return "REEFER"

        if self.boxcar_type == BoxCarType.INSULATED:
            return "INSULATED_BOX"

        if self.boxcar_type == BoxCarType.AUTO_PARTS:
            return "AUTO_PARTS_BOX"

        return "BOX"

    @property
    def equipment_short_name(self) -> str:
        if self.boxcar_type == BoxCarType.REFRIGERATED:
            return "RFR"

        if self.boxcar_type == BoxCarType.INSULATED:
            return "IBOX"

        if self.boxcar_type == BoxCarType.AUTO_PARTS:
            return "APBX"

        return "BOX"

    def can_load_commodity(self, commodity: str, *, food_grade: bool = False) -> bool:
        """
        Return True if the provided commodity may be loaded based on the
        car's current compatibility and cleanliness state.
        """
        if not commodity or not commodity.strip():
            return False

        if self.is_loaded:
            return False

        if food_grade and self.service_type != BoxCarService.FOOD_GRADE:
            return False

        if food_grade and not self.is_cleaned:
            return False

        return True

    def load_commodity(self, commodity: str, *, food_grade: bool = False) -> None:
        """
        Load a commodity into the boxcar.

        Rules enforced:
        - commodity must be non-empty
        - car must not already be loaded
        - food-grade loads require FOOD_GRADE service
        - food-grade loads require cleaned state
        """
        if not commodity or not commodity.strip():
            raise ValueError("commodity must be a non-empty string.")

        if self.is_loaded:
            raise ValueError("Boxcar is already loaded.")

        if food_grade and self.service_type != BoxCarService.FOOD_GRADE:
            raise ValueError("Food-grade commodities require a FOOD_GRADE boxcar.")

        if food_grade and not self.is_cleaned:
            raise ValueError("Food-grade commodities require a cleaned boxcar.")

        self.current_commodity = commodity
        self.is_cleaned = False

    def unload_commodity(self) -> str:
        """
        Unload the current commodity.

        Returns:
            The commodity that was removed.

        Raises:
            ValueError: if the boxcar is not currently loaded.
        """
        if self.current_commodity is None:
            raise ValueError("Boxcar is not currently loaded.")

        unloaded = self.current_commodity
        self.last_commodity = unloaded
        self.current_commodity = None
        self.is_cleaned = False
        return unloaded

    def clean_boxcar(self) -> None:
        """Mark the boxcar as cleaned and ready for a compatible future load."""
        self.is_cleaned = True

    def __str__(self) -> str:
        commodity_text = (
            self.current_commodity if self.current_commodity is not None else "empty"
        )
        return (
            f"{self.equipment_id} "
            f"({self.boxcar_type.value}, {self.inside_length_ft:g} ft, "
            f"{commodity_text})"
        )

    def __repr__(self) -> str:
        return (
            f"BoxCar("
            f"{self.equipment_id}, "
            f"type={self.boxcar_type.value}, "
            f"service={self.service_type.value}, "
            f"length_ft={self.inside_length_ft:g}, "
            f"loaded={self.is_loaded}"
            f")"
        )
