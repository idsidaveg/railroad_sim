from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar, Iterator
from uuid import UUID, uuid4

from railroad_sim.domain.couplers import Coupler
from railroad_sim.domain.enums import TraversalDirection
from railroad_sim.domain.exceptions import (
    ConsistOperationError,
    ConsistTopologyError,
)
from railroad_sim.domain.rolling_stock import RollingStock


@dataclass(slots=True)
class Consist:
    """
    Represents a physically connected chain of rolling stock.

    The consist does not store order explicitly. Instead, it derives
    order by traversing coupler connections starting from the anchor.

    Active consist membership is enforced globally so that a single
    RollingStock asset cannot belong to multiple active consists at once.
    """

    _consists_by_id: ClassVar[dict[UUID, "Consist"]] = {}
    _asset_to_consist_id: ClassVar[dict[UUID, UUID]] = {}

    anchor: RollingStock
    consist_id: UUID = field(init=False)

    def __post_init__(self) -> None:
        self.consist_id = uuid4()
        self._register()

    def _find_end(self, start: RollingStock) -> RollingStock:
        """
        Walk toward the head end until no more equipment exists.

        Raises:
            ConsistTopologyError: if a loop is detected.
        """
        current = start
        visited: set[UUID] = set()

        while True:
            if current.asset_id in visited:
                raise ConsistTopologyError("Consist loop detected while finding end.")

            visited.add(current.asset_id)

            next_car = self._next_car(
                current,
                direction=TraversalDirection.REVERSE,
            )

            if next_car is None:
                return current

            current = next_car

    def _next_car(
        self,
        current: RollingStock,
        direction: TraversalDirection,
    ) -> RollingStock | None:
        """
        Return the next car in the consist in the requested direction.

        Traversal is orientation-aware:
        - REVERSE follows the front coupler toward the head end
        - FORWARD follows the rear coupler toward the rear end
        """
        if direction is TraversalDirection.REVERSE:
            coupler = current.front_coupler
        else:
            coupler = current.rear_coupler

        if coupler.connected_to is None:
            return None

        return coupler.connected_to.owner

    def ordered_equipment(self) -> list[RollingStock]:
        """
        Return rolling stock in physical order from head to rear.

        Raises:
            ConsistTopologyError: if a loop is detected.
        """
        head = self._find_end(self.anchor)

        ordered: list[RollingStock] = []
        visited: set[UUID] = set()

        current = head

        while current is not None:
            if current.asset_id in visited:
                raise ConsistTopologyError("Consist loop detected during traversal.")

            ordered.append(current)
            visited.add(current.asset_id)

            current = self._next_car(
                current,
                direction=TraversalDirection.FORWARD,
            )

        return ordered

    def _register(self) -> None:
        """
        Register this consist and claim ownership of all of its assets.

        Raises:
            ConsistOperationError: if any asset is already claimed by
                another active consist.
        """
        equipment = self.ordered_equipment()

        for car in equipment:
            existing_consist_id = self._asset_to_consist_id.get(car.asset_id)
            if existing_consist_id is not None:
                raise ConsistOperationError(
                    f"Rolling stock {car.equipment_id} is already assigned to "
                    f"consist {existing_consist_id}."
                )

        self._consists_by_id[self.consist_id] = self

        for car in equipment:
            self._asset_to_consist_id[car.asset_id] = self.consist_id

    def _release_registry_claims(
        self,
        equipment: list[RollingStock] | None = None,
    ) -> None:
        """
        Release this consist's asset claims and remove it from the active registry.

        If equipment is provided, that exact membership list is used. This is
        important for split and merge operations, where the physical topology
        may change before replacement consists are created.
        """
        if equipment is None:
            equipment = self.ordered_equipment()

        for car in equipment:
            registered_consist_id = self._asset_to_consist_id.get(car.asset_id)
            if registered_consist_id == self.consist_id:
                del self._asset_to_consist_id[car.asset_id]

        self._consists_by_id.pop(self.consist_id, None)

    def _disconnect_adjacent_pair(
        self,
        left: RollingStock,
        right: RollingStock,
    ) -> None:
        """
        Disconnect the coupler pair joining two adjacent rolling stock units.

        Raises:
            ConsistOperationError: if the cars are not directly connected.
        """
        for coupler in (left.front_coupler, left.rear_coupler):
            if coupler.connected_to is None:
                continue

            if coupler.connected_to.owner is right:
                coupler.disconnect()
                return

        raise ConsistOperationError(
            f"Rolling stock {left.equipment_id} and {right.equipment_id} "
            "are not directly connected."
        )

    def _ensure_active(self) -> None:
        """
        Ensure this consist is still active in the global registry.
        """
        if self._consists_by_id.get(self.consist_id) is not self:
            raise ConsistOperationError(f"Consist {self.consist_id} is not active.")

    def _contains_car(self, car: RollingStock) -> bool:
        """
        Return True if the rolling stock is part of this consist.
        """
        return car in self.ordered_equipment()

    def _exposed_end_couplers(self) -> tuple[Coupler, Coupler]:
        """
        Return the two exposed outside-facing couplers for this consist.

        For a multi-car consist:
        - head_end.front_coupler
        - rear_end.rear_coupler

        For a single-car consist, those may both belong to the same car.
        """
        head = self.head_end
        rear = self.rear_end
        return head.front_coupler, rear.rear_coupler

    def _is_exposed_end_coupler(self, coupler: Coupler) -> bool:
        """
        Return True if the coupler is one of the consist's exposed end couplers.
        """
        exposed_left, exposed_right = self._exposed_end_couplers()
        return coupler is exposed_left or coupler is exposed_right

    def merge_with(
        self,
        other: "Consist",
        self_coupler: Coupler,
        other_coupler: Coupler,
    ) -> "Consist":
        """
        Merge this consist with another by coupling two exposed end couplers.

        The original consists are retired from the registry and replaced by a
        new consist representing the merged topology.

        Raises:
            ConsistOperationError: if either consist is inactive, if both
                references point to the same consist, if the provided couplers
                do not belong to the correct consists, if either coupler is not
                an exposed end coupler, or if either coupler is already connected.
        """
        if self is other:
            raise ConsistOperationError("Cannot merge a consist with itself.")

        self._ensure_active()
        other._ensure_active()

        if not self._contains_car(self_coupler.owner):
            raise ConsistOperationError(
                "The provided self_coupler does not belong to this consist."
            )

        if not other._contains_car(other_coupler.owner):
            raise ConsistOperationError(
                "The provided other_coupler does not belong to the other consist."
            )

        if not self._is_exposed_end_coupler(self_coupler):
            raise ConsistOperationError(
                "The provided self_coupler is not an exposed end coupler."
            )

        if not other._is_exposed_end_coupler(other_coupler):
            raise ConsistOperationError(
                "The provided other_coupler is not an exposed end coupler."
            )

        if self_coupler.connected_to is not None:
            raise ConsistOperationError(
                "The provided self_coupler is already connected."
            )

        if other_coupler.connected_to is not None:
            raise ConsistOperationError(
                "The provided other_coupler is already connected."
            )

        self_equipment = self.ordered_equipment()
        other_equipment = other.ordered_equipment()

        self._release_registry_claims(equipment=self_equipment)
        other._release_registry_claims(equipment=other_equipment)

        self_coupler.connect(other_coupler)

        return Consist(anchor=self.anchor)

    def split_after(self, car: RollingStock) -> tuple["Consist", "Consist"]:
        """
        Split the consist immediately after the specified car.

        Example:
            A - B - C - D
            split_after(B) -> (A - B), (C - D)

        Raises:
            ConsistOperationError: if the car is not in the consist or if the
                split would produce an empty side.
        """
        ordered = self.ordered_equipment()

        try:
            idx = ordered.index(car)
        except ValueError as exc:
            raise ConsistOperationError(
                f"Rolling stock {car.equipment_id} is not part of this consist."
            ) from exc

        if idx == len(ordered) - 1:
            raise ConsistOperationError(
                f"Cannot split after {car.equipment_id}; it is already the rear end."
            )

        left_car = ordered[idx]
        right_car = ordered[idx + 1]

        self._disconnect_adjacent_pair(left_car, right_car)
        self._release_registry_claims(equipment=ordered)

        return Consist(anchor=ordered[0]), Consist(anchor=right_car)

    def split_before(self, car: RollingStock) -> tuple["Consist", "Consist"]:
        """
        Split the consist immediately before the specified car.

        Example:
            A - B - C - D
            split_before(C) -> (A - B), (C - D)

        Raises:
            ConsistOperationError: if the car is not in the consist or if the
                split would produce an empty side.
        """
        ordered = self.ordered_equipment()

        try:
            idx = ordered.index(car)
        except ValueError as exc:
            raise ConsistOperationError(
                f"Rolling stock {car.equipment_id} is not part of this consist."
            ) from exc

        if idx == 0:
            raise ConsistOperationError(
                f"Cannot split before {car.equipment_id}; it is already the head end."
            )

        left_car = ordered[idx - 1]
        right_car = ordered[idx]

        self._disconnect_adjacent_pair(left_car, right_car)
        self._release_registry_claims(equipment=ordered)

        return Consist(anchor=ordered[0]), Consist(anchor=right_car)

    def diagram(self) -> str:
        """
        Return a simple text representation of the consist in head-to-rear order.

        Example:
            HEAD -> UP 1001 --- UP 1002 --- UP 1003 <- REAR
        """
        cars = self.ordered_equipment()
        body = " --- ".join(car.equipment_id for car in cars)
        return f"HEAD -> {body} <- REAR"

    def diagnostic_dump(self) -> str:
        """
        Return a multi-line diagnostic view of the consist.

        This is intended for debugging and test support only.
        It does not define consist topology; coupler connections remain
        the source of truth.
        """

        def coupler_label(coupler) -> str:
            if coupler.connected_to is None:
                return "None"

            other = coupler.connected_to
            return f"{other.owner.equipment_id} {other.position.name}"

        lines = [
            "Consist Diagnostic",
            f"Consist ID: {self.consist_id}",
            f"Anchor: {self.anchor.equipment_id}",
            "",
        ]

        for idx, car in enumerate(self.ordered_equipment(), start=1):
            anchor_suffix = "  [ANCHOR]" if car is self.anchor else ""
            lines.append(f"[{idx}] {car.equipment_id}{anchor_suffix}")
            lines.append(f"    Front: {coupler_label(car.front_coupler)}")
            lines.append(f"    Rear : {coupler_label(car.rear_coupler)}")
            lines.append("")

        return "\n".join(lines).rstrip()

    def show(self) -> None:
        """Print the one-line diagram view of the consist."""
        print(self.diagram())

    def show_diagnostic(self) -> None:
        """Print the multi-line diagnostic view of the consist."""
        print(self.diagnostic_dump())

    def __len__(self) -> int:
        return len(self.ordered_equipment())

    def __iter__(self) -> Iterator[RollingStock]:
        yield from self.ordered_equipment()

    @property
    def head_end(self) -> RollingStock:
        return self.ordered_equipment()[0]

    @property
    def rear_end(self) -> RollingStock:
        order = self.ordered_equipment()
        return order[-1]

    @classmethod
    def get_by_id(cls, consist_id: UUID) -> "Consist | None":
        """Return an active consist by ID, if present."""
        return cls._consists_by_id.get(consist_id)

    @classmethod
    def get_consist_for_asset(cls, asset_id: UUID) -> "Consist | None":
        """Return the active consist that owns the given asset, if any."""
        consist_id = cls._asset_to_consist_id.get(asset_id)
        if consist_id is None:
            return None
        return cls._consists_by_id.get(consist_id)

    @classmethod
    def active_consists(cls) -> list["Consist"]:
        """Return all currently active consists."""
        return list(cls._consists_by_id.values())

    @classmethod
    def _reset_registry_for_tests(cls) -> None:
        """Clear all active consist registry state. Test support only."""
        cls._consists_by_id.clear()
        cls._asset_to_consist_id.clear()
