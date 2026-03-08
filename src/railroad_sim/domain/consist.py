from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

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
    """

    anchor: RollingStock

    def _find_end(self, start: RollingStock) -> RollingStock:
        """
        Walk toward the head end until no more equipment exists.

        Raises:
            ConsistTopologyError: if a loop is detected.
        """
        current = start
        visited: set = set()

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
        visited: set = set()

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

    def split_after(self, car: RollingStock) -> tuple[Consist, Consist]:
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

        return Consist(anchor=ordered[0]), Consist(anchor=right_car)

    def split_before(self, car: RollingStock) -> tuple[Consist, Consist]:
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

    # Debugging helper routines
    def show(self) -> None:
        """Print the one-line diagram view of the consist."""
        print(self.diagram())

    def show_diagnostic(self) -> None:
        """Print the multi-line diagnostic view of the consist."""
        print(self.diagnostic_dump())

    # Utility methods to help with the Consist object
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
