from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from railroad_sim.domain.enums import CouplerPosition
from railroad_sim.domain.exceptions import (
    CouplerConnectionError,
    CouplerStateError,
)

if TYPE_CHECKING:
    from railroad_sim.domain.rolling_stock import RollingStock


@dataclass(slots=True)
class Coupler:
    """
    Represents a single coupler on a piece of rolling stock.

    A coupler may connect to at most one other coupler.
    Front and rear couplers are independent.
    """

    owner: RollingStock
    position: CouplerPosition
    is_damaged: bool = False
    connected_to: Coupler | None = field(default=None, init=False, repr=False)

    @property
    def is_connected(self) -> bool:
        """Return True if this coupler is currently connected."""
        return self.connected_to is not None

    def connect(self, other: Coupler) -> None:
        """
        Connect this coupler to another coupler.

        Raises:
            CouplerConnectionError: if either coupler is already connected,
                or if attempting to connect a coupler to itself.
            CouplerStateError: if either coupler is damaged.
        """
        if other is self:
            raise CouplerConnectionError("A coupler cannot connect to itself.")

        if self.owner is other.owner:
            raise CouplerConnectionError(
                "Cannot connect two couplers on the same rolling stock."
            )

        if self.is_damaged:
            raise CouplerStateError(
                f"Cannot connect {self.position.name} coupler because it is damaged."
            )

        if other.is_damaged:
            raise CouplerStateError(
                f"Cannot connect to {other.position.name} coupler because it is damaged."
            )

        if self.connected_to is not None:
            raise CouplerConnectionError(
                f"{self.position.name} coupler is already connected."
            )

        if other.connected_to is not None:
            raise CouplerConnectionError(
                f"Target {other.position.name} coupler is already connected."
            )

        self.connected_to = other
        other.connected_to = self

    def disconnect(self) -> None:
        """
        Disconnect this coupler from its connected mate.

        Raises:
            CouplerStateError: if this coupler is not connected, or if the
                connection state is inconsistent.
        """
        if self.connected_to is None:
            raise CouplerStateError(
                f"{self.position.name} coupler is not currently connected."
            )

        other = self.connected_to

        if other.connected_to is not self:
            raise CouplerStateError(
                "Inconsistent coupler state detected during disconnect."
            )

        self.connected_to = None
        other.connected_to = None
