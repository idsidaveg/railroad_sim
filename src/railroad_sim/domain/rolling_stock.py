from __future__ import annotations

from dataclasses import InitVar, dataclass, field
from uuid import UUID, uuid4

from railroad_sim.domain.couplers import Coupler
from railroad_sim.domain.enums import CouplerPosition


@dataclass(slots=True)
class RollingStock:
    """
    Base domain object representing a single piece of railroad equipment.

    Each RollingStock instance owns two couplers:
        - front_coupler
        - rear_coupler

    Couplers define the physical connections that form a consist.

    Identity is anchored by immutable asset_id.
    reporting_mark and road_number may change over time.
    """

    reporting_mark: str
    road_number: str
    asset_id_value: InitVar[UUID | None] = None
    owner: str | None = None

    _asset_id: UUID = field(init=False, repr=False)
    front_coupler: Coupler = field(init=False)
    rear_coupler: Coupler = field(init=False)

    def __post_init__(self, asset_id_value: UUID | None) -> None:
        self._asset_id = asset_id_value if asset_id_value is not None else uuid4()

        self.reporting_mark = self.reporting_mark.strip().upper()
        self.road_number = self.road_number.strip()

        if not self.reporting_mark:
            raise ValueError("reporting_mark cannot be empty.")

        if not self.road_number:
            raise ValueError("road_number cannot be empty.")

        self.front_coupler = Coupler(
            owner=self,
            position=CouplerPosition.FRONT,
        )
        self.rear_coupler = Coupler(
            owner=self,
            position=CouplerPosition.REAR,
        )

    @property
    def asset_id(self) -> UUID:
        """Immutable unique identity for this equipment."""
        return self._asset_id

    @property
    def equipment_id(self) -> str:
        """Human-readable railroad identifier."""
        return f"{self.reporting_mark} {self.road_number}"

    def rename_equipment(self, reporting_mark: str, road_number: str) -> None:
        """
        Update the visible railroad identifier without changing asset identity.
        """
        reporting_mark = reporting_mark.strip().upper()
        road_number = road_number.strip()

        if not reporting_mark:
            raise ValueError("reporting_mark cannot be empty.")

        if not road_number:
            raise ValueError("road_number cannot be empty.")

        self.reporting_mark = reporting_mark
        self.road_number = road_number

    def __repr__(self) -> str:
        return f"RollingStock({self.equipment_id})"
