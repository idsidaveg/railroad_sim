from __future__ import annotations

from dataclasses import InitVar, dataclass, field
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from railroad_sim.domain.enums import CouplerPosition, DamageRating
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

    Persistence notes:
    - Each coupler has its own immutable UUID.
    - A coupler UUID may be restored using ``coupler_id_value``.
    - ``connected_to`` remains a runtime object reference and should be
      serialized by identity elsewhere in the persistence layer.
    """

    owner: RollingStock
    position: CouplerPosition
    is_damaged: bool = False
    damage_rating: DamageRating | None = field(default=None, init=False)
    coupler_id_value: InitVar[UUID | None] = None

    connected_to: Coupler | None = field(default=None, init=False, repr=False)
    _coupler_id: UUID = field(init=False, repr=False)

    def __post_init__(self, coupler_id_value: UUID | None) -> None:
        """Assign an immutable UUID, or restore one if provided."""
        self._coupler_id = coupler_id_value if coupler_id_value is not None else uuid4()

    @property
    def coupler_id(self) -> UUID:
        """Return the immutable UUID for this coupler."""
        return self._coupler_id

    @property
    def is_connected(self) -> bool:
        """Return True if this coupler is currently connected."""
        return self.connected_to is not None

    def mark_damaged(self, *, damage_rating: DamageRating) -> None:
        """
        Mark this coupler as damaged with a severity rating.
        Allowed ratings:
        - MODERATE
        - SEVERE
        """

        self.is_damaged = True
        self.damage_rating = damage_rating

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

    def __str__(self) -> str:
        """Human-readable debugging representation."""
        owner_id = getattr(self.owner, "equipment_id", "Unknown")

        if self.connected_to is None:
            connection_text = "None"
        else:
            other_owner_id = getattr(self.connected_to.owner, "equipment_id", "Unknown")
            connection_text = f"{other_owner_id}:{self.connected_to.position.name}"

        return (
            f"{owner_id}:{self.position.name} [{self.coupler_id}] -> {connection_text}"
        )

    def __repr__(self) -> str:
        """Debugger-friendly representation."""
        return f"Coupler({self})"

    def debug_summary(self) -> str:
        """Return a multi-line summary of the coupler and its connection state."""
        owner_id = getattr(self.owner, "equipment_id", "Unknown")

        lines = [
            "Coupler",
            f"  owner         : {owner_id}",
            f"  position      : {self.position.name}",
            f"  coupler_id    : {self.coupler_id}",
            f"  damaged       : {self.is_damaged}",
            f"  damage_rating : {self.damage_rating}",
        ]

        if self.connected_to is None:
            lines.append("  connected   : None")
        else:
            other_owner_id = getattr(self.connected_to.owner, "equipment_id", "Unknown")
            lines.extend(
                [
                    "  connected   :",
                    f"    owner     : {other_owner_id}",
                    f"    position  : {self.connected_to.position.name}",
                    f"    coupler_id: {self.connected_to.coupler_id}",
                ]
            )

        return "\n".join(lines)
