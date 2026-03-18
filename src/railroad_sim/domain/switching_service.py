from __future__ import annotations

from railroad_sim.domain.consist import Consist
from railroad_sim.domain.couplers import Coupler
from railroad_sim.domain.exceptions import ConsistOperationError
from railroad_sim.domain.rolling_stock import RollingStock

"""
SwitchingService
================

Domain service that implements railroad-style switching operations.

This layer provides operational commands used by yard crews and
dispatchers when manipulating cuts of cars. It wraps lower-level
Consist topology operations into higher-level switching moves.

The service is intentionally stateless. It delegates all physical
topology changes and consist lifecycle management to the Consist
domain object.

Implemented Switching Operations
--------------------------------

CUTTING
~~~~~~~

cut_after(consist, car)
    Cut a consist immediately after the specified car.

    Example:
        Initial consist:
            A-B-C-D

        Operation:
            cut_after(B)

        Result:
            A-B     C-D

    Diagram:
        A-B-C-D  ->  A-B | C-D


cut_before(consist, car)
    Cut a consist immediately before the specified car.

    Example:
        Initial consist:
            A-B-C-D

        Operation:
            cut_before(C)

        Result:
            A-B     C-D

    Diagram:
        A-B-C-D  ->  A-B | C-D


COUPLING / BUILDING
~~~~~~~~~~~~~~~~~~~

couple(left_consist, right_consist, left_coupler, right_coupler)
    Couple two consists together using exposed end couplers.

    Example:
        Initial:
            A-B     C-D

        Operation:
            couple(B.rear, C.front)

        Result:
            A-B-C-D

    Diagram:
        A-B | C-D  ->  A-B-C-D


append_consist(left_consist, right_consist)
    Append one consist to the rear of another.

    This is a general-purpose coupling operation commonly used during
    yard switching and train assembly.

    Example:
        Initial:
            A-B     C-D

        Operation:
            append_consist(left, right)

        Result:
            A-B-C-D

    Diagram:
        A-B | C-D  ->  A-B-C-D


insert_block(consist, after_car, block_consist)
    Insert a block of cars into a consist immediately after a given car.

    Example:
        Initial consist:
            A-B-E-F

        Block to insert:
            C-D

        Operation:
            insert_block(after=B)

        Result:
            A-B-C-D-E-F

    Diagram:
        A-B-E-F  +  C-D  ->  A-B-C-D-E-F

    Special cases handled:
        • Inserting in the middle of a consist
        • Inserting after the rear car (append)
        • Inserting a single-car block

    Additional examples:
        Insert single car:
            A-B-D  +  X  ->  A-B-X-D

        Insert at rear:
            A-B  +  C-D  ->  A-B-C-D


pickup_block(train_consist, block_consist, after_car=None)
    Pick up a block of cars and add it to a train consist.

    If after_car is omitted, the block is appended to the rear of the train.
    If after_car is provided, the block is inserted immediately after that
    car in the train consist.

    Examples:

        Rear pickup:
            A-B | C-D  ->  A-B-C-D

        Middle pickup:
            A-B-E-F + C-D, after B  ->  A-B-C-D-E-F


REMOVAL / SETOUT
~~~~~~~~~~~~~~~~

setout_block(consist, first_car, last_car)
    Remove a contiguous block of cars from a consist.

    Example:
        Initial consist:
            A-B-C-D-E-F

        Operation:
            setout_block(C, D)

        Result:
            Remaining train:
                A-B-E-F

            Setout block:
                C-D

    Diagram:
        A-B-C-D-E-F  ->  A-B-E-F  +  C-D

    Special cases handled:
        • Block at head end
        • Block at rear end
        • Block in the middle of the consist
        • Single-car setouts

    Additional examples:
        Head-end setout:
            A-B-C-D-E-F  ->  C-D-E-F  +  A-B

        Rear-end setout:
            A-B-C-D-E-F  ->  A-B-C-D  +  E-F

        Single-car middle setout:
            A-B-C-D-E-F  ->  A-B-C-E-F  +  D


Quick Switching Diagram Reference
---------------------------------

    cut_after       A-B-C-D          -> A-B | C-D
    cut_before      A-B-C-D          -> A-B | C-D
    couple          A-B | C-D        -> A-B-C-D
    setout_block    A-B-C-D-E-F      -> A-B-E-F + C-D
    pickup_block    A-B | C-D        -> A-B-C-D
    pickup_block    A-B-E-F + C-D    -> A-B-C-D-E-F   (after B)
    append_consist  A-B | C-D        -> A-B-C-D
    insert_block    A-B-E-F + C-D    -> A-B-C-D-E-F


Operational Model
-----------------

These operations mirror the switching moves performed by real railroad
yard crews. Complex switching sequences are constructed by combining
these basic primitives.

Example switching sequence:

    Initial train:
        A-B-C-D-E-F

    Set out C-D:
        remaining, industry = setout_block(train, C, D)

    Later pick them up:
        train = pickup_block(remaining, industry)

    Final result:
        A-B-C-D-E-F


Layer Responsibilities
----------------------

RollingStock
    Individual railroad equipment with identity and history.

Coupler
    Physical connection points between rolling stock.

Consist
    Represents a connected chain of equipment determined by coupler
    topology. Handles splitting, merging, and registry management.

SwitchingService
    Implements railroad switching operations by orchestrating
    consist-level operations.

This separation keeps switching logic readable while preserving
strict topology integrity within the Consist domain model.
"""


class SwitchingService:
    """
    Domain service for railroad switching moves.

    This service wraps low-level consist split/merge mechanics in
    railroad-oriented operations such as cuts, coupling, setouts,
    pickups, appends, and block insertion.
    """

    # ==========================================================
    # Validation Helpers
    # ==========================================================

    @staticmethod
    def _validate_not_same_consist(left: Consist, right: Consist) -> None:
        """
        Ensure two consist arguments are distinct objects.
        """
        if left is right:
            raise ConsistOperationError("Operation requires two distinct consists.")

    @staticmethod
    def _validate_consist_not_empty(consist: Consist) -> None:
        """
        Ensure the consist contains at least one car.
        """
        if not consist.ordered_equipment():
            raise ConsistOperationError("Consist is empty.")

    @staticmethod
    def _validate_block_not_empty(block: Consist) -> None:
        """
        Ensure the block consist contains at least one car.
        """
        if not block.ordered_equipment():
            raise ConsistOperationError("Block consist is empty.")

    @staticmethod
    def _validate_car_in_consist(consist: Consist, car: RollingStock) -> None:
        """
        Ensure the specified car is part of the consist.
        """
        if car not in consist.ordered_equipment():
            raise ConsistOperationError(
                f"Rolling stock {car.equipment_id} is not part of this consist."
            )

    @staticmethod
    def _validate_exposed_coupler(coupler: Coupler, label: str) -> None:
        """
        Ensure the coupler is exposed and available for coupling.
        """
        if coupler.connected_to is not None:
            raise ConsistOperationError(f"{label} must be an exposed coupler.")

    # ==========================================================
    # Utility
    # ==========================================================

    @staticmethod
    def standard_coupling_pair(
        left: Consist,
        right: Consist,
    ) -> tuple[Coupler, Coupler]:
        """
        Return the default exposed-end coupler pair for appending the
        right consist to the rear of the left consist.

        Diagram:
            A-B | C-D  ->  use B.rear and C.front
        """
        return left.rear_end.rear_coupler, right.head_end.front_coupler

    # ==========================================================
    # Cutting Operations
    # ==========================================================

    @staticmethod
    def cut_after(consist: Consist, car: RollingStock) -> tuple[Consist, Consist]:
        """
        Cut a consist immediately after the specified car.

        Example:
            A-B-C-D
            cut_after(B) -> (A-B), (C-D)
        """
        SwitchingService._validate_consist_not_empty(consist)
        SwitchingService._validate_car_in_consist(consist, car)
        return consist.split_after(car)

    @staticmethod
    def cut_before(consist: Consist, car: RollingStock) -> tuple[Consist, Consist]:
        """
        Cut a consist immediately before the specified car.

        Example:
            A-B-C-D
            cut_before(C) -> (A-B), (C-D)
        """
        SwitchingService._validate_consist_not_empty(consist)
        SwitchingService._validate_car_in_consist(consist, car)
        return consist.split_before(car)

    # ==========================================================
    # Coupling Operations
    # ==========================================================

    @staticmethod
    def couple(
        left: Consist,
        right: Consist,
        left_coupler: Coupler,
        right_coupler: Coupler,
    ) -> Consist:
        """
        Couple two consists together using exposed end couplers.

        Raises:
            ConsistOperationError:
                - if the consists are the same object
                - if either consist is empty
                - if either supplied coupler is not exposed
        """
        SwitchingService._validate_not_same_consist(left, right)
        SwitchingService._validate_consist_not_empty(left)
        SwitchingService._validate_consist_not_empty(right)
        SwitchingService._validate_exposed_coupler(left_coupler, "left_coupler")
        SwitchingService._validate_exposed_coupler(right_coupler, "right_coupler")

        return left.merge_with(
            right,
            self_coupler=left_coupler,
            other_coupler=right_coupler,
        )

    @staticmethod
    def append_consist(
        left: Consist,
        right: Consist,
    ) -> Consist:
        """
        Append one consist to the rear of another.

        Raises:
            ConsistOperationError:
                - if the consists are the same object
                - if either consist is empty
                - if the exposed end couplers are not actually exposed
        """
        SwitchingService._validate_not_same_consist(left, right)
        SwitchingService._validate_consist_not_empty(left)
        SwitchingService._validate_block_not_empty(right)

        left_coupler, right_coupler = SwitchingService.standard_coupling_pair(
            left, right
        )
        SwitchingService._validate_exposed_coupler(left_coupler, "left rear coupler")
        SwitchingService._validate_exposed_coupler(right_coupler, "right head coupler")

        return left.merge_with(
            right,
            self_coupler=left_coupler,
            other_coupler=right_coupler,
        )

    @staticmethod
    def insert_block(
        consist: Consist,
        after_car: RollingStock,
        block: Consist,
    ) -> Consist:
        """
        Insert a block of cars into a consist immediately after a given car.

        Example:
            A-B-E-F
            insert C-D after B

            result -> A-B-C-D-E-F

        Raises:
            ConsistOperationError:
                - if after_car is not part of the consist
                - if block is empty
                - if consist and block are the same object
        """
        SwitchingService._validate_consist_not_empty(consist)
        SwitchingService._validate_block_not_empty(block)
        SwitchingService._validate_not_same_consist(consist, block)
        SwitchingService._validate_car_in_consist(consist, after_car)

        if after_car is consist.rear_end:
            return SwitchingService.append_consist(consist, block)

        left, right = consist.split_after(after_car)

        merged = left.merge_with(
            block,
            self_coupler=left.rear_end.rear_coupler,
            other_coupler=block.head_end.front_coupler,
        )

        return merged.merge_with(
            right,
            self_coupler=merged.rear_end.rear_coupler,
            other_coupler=right.head_end.front_coupler,
        )

    @staticmethod
    def pickup_block(
        train_consist: Consist,
        block_consist: Consist,
        after_car: RollingStock | None = None,
    ) -> Consist:
        """
        Pick up a block of cars and add it to a train consist.

        Behavior:
            - If after_car is None, append the block to the rear of the train.
            - If after_car is provided, insert the block immediately after
              that car in the train consist.

        Examples:
            Append to rear:
                Train: A-B
                Block: C-D

                pickup_block(train, block) -> A-B-C-D

            Insert in middle:
                Train: A-B-E-F
                Block: C-D

                pickup_block(train, block, after_car=B) -> A-B-C-D-E-F

        Raises:
            ConsistOperationError:
                - if train_consist and block_consist are the same consist
                - if either consist is empty
                - if after_car is provided but is not part of train_consist
        """
        SwitchingService._validate_not_same_consist(train_consist, block_consist)
        SwitchingService._validate_consist_not_empty(train_consist)
        SwitchingService._validate_block_not_empty(block_consist)

        if after_car is None:
            return SwitchingService.append_consist(train_consist, block_consist)

        SwitchingService._validate_car_in_consist(train_consist, after_car)
        return SwitchingService.insert_block(train_consist, after_car, block_consist)

    # ==========================================================
    # Removal / Setout Operations
    # ==========================================================

    @staticmethod
    def setout_block(
        consist: Consist,
        first_car: RollingStock,
        last_car: RollingStock,
    ) -> tuple[Consist, Consist]:
        """
        Set out a contiguous block of cars from a consist.

        The removed block must be contiguous in the consist and ordered
        from head-to-rear as first_car ... last_car.

        Example:
            A-B-C-D-E-F
            setout_block(C, D) -> remaining: A-B-E-F, setout: C-D

        Returns:
            (remaining_consist, setout_consist)

        Raises:
            ConsistOperationError:
                - if either car is not in the consist
                - if the cars are not ordered head-to-rear
                - if the setout would remove the entire consist
        """
        SwitchingService._validate_consist_not_empty(consist)
        SwitchingService._validate_car_in_consist(consist, first_car)
        SwitchingService._validate_car_in_consist(consist, last_car)

        ordered = consist.ordered_equipment()
        first_idx = ordered.index(first_car)
        last_idx = ordered.index(last_car)

        if first_idx > last_idx:
            raise ConsistOperationError(
                "setout_block requires first_car to appear before last_car "
                "in head-to-rear order."
            )

        if first_idx == 0 and last_idx == len(ordered) - 1:
            raise ConsistOperationError("Cannot set out the entire consist.")

        # Case 1: setout block starts at head
        if first_idx == 0:
            setout, remaining = consist.split_after(last_car)
            return remaining, setout

        # Case 2: setout block ends at rear
        if last_idx == len(ordered) - 1:
            remaining, setout = consist.split_before(first_car)
            return remaining, setout

        # Case 3: setout block is in the middle
        left_part, right_part = consist.split_before(first_car)
        setout, trailing_part = right_part.split_after(last_car)

        merged_remaining = left_part.merge_with(
            trailing_part,
            self_coupler=left_part.rear_end.rear_coupler,
            other_coupler=trailing_part.head_end.front_coupler,
        )

        return merged_remaining, setout
