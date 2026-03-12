from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from railroad_sim.domain.enums import (
    MovementState,
    TrackCondition,
    TrackTrafficRule,
    TrackType,
    TravelDirection,
)

if TYPE_CHECKING:
    from railroad_sim.domain.consist import Consist


@dataclass(slots=True)
class TrackOccupancy:
    """One consist's current presence on one track segment.

    Offsets are measured in feet on the track's coordinate frame:

        A ---------------------------------------------- B
        0 ft                                      track.length_ft
    """

    consist: Consist
    rear_offset_ft: float
    front_offset_ft: float
    travel_direction: TravelDirection = TravelDirection.STATIONARY
    speed_mph: float = 0.0
    movement_state: MovementState = MovementState.STATIONARY

    def __post_init__(self) -> None:
        if self.rear_offset_ft < 0:
            raise ValueError("rear_offset_ft must be >= 0")

        if self.front_offset_ft < 0:
            raise ValueError("front_offset_ft must be >= 0")

        if self.rear_offset_ft > self.front_offset_ft:
            raise ValueError("rear_offset_ft must be <= front_offset_ft")

        if self.speed_mph < 0:
            raise ValueError("speed_mph must be >= 0")

        if self.movement_state == MovementState.STATIONARY and self.speed_mph != 0:
            raise ValueError("stationary occupancy must have speed_mph == 0")

        if self.travel_direction == TravelDirection.STATIONARY and self.speed_mph != 0:
            raise ValueError("stationary travel direction must have speed_mph == 0")

        if self.speed_mph > 0 and self.movement_state == MovementState.STATIONARY:
            raise ValueError("moving occupancy cannot have MovementState.STATIONARY")

        if self.speed_mph > 0 and self.travel_direction == TravelDirection.STATIONARY:
            raise ValueError("moving occupancy cannot have TravelDirection.STATIONARY")

    @property
    def length_ft(self) -> float:
        """Return the occupied length on this track segment."""
        return self.front_offset_ft - self.rear_offset_ft

    def overlaps(self, other: "TrackOccupancy") -> bool:
        """Return True if this occupancy overlaps another occupancy range.

        Touching at a single boundary point is not treated as overlap.
        Example:
            [0, 100] and [100, 200] -> False
        """
        return not (
            self.front_offset_ft <= other.rear_offset_ft
            or other.front_offset_ft <= self.rear_offset_ft
        )


@dataclass(slots=True)
class Track:
    """A two-ended physical section of railroad.

    Track models infrastructure and active occupancy state. It does not model
    switch topology, turnout alignment, wye routing, or interlocking logic.
    """

    name: str
    track_type: TrackType
    length_ft: float
    condition: TrackCondition = TrackCondition.CLEAR
    traffic_rule: TrackTrafficRule = TrackTrafficRule.BIDIRECTIONAL
    occupancies: list[TrackOccupancy] = field(default_factory=list)
    track_id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("track name must not be blank")

        if self.length_ft <= 0:
            raise ValueError("length_ft must be > 0")

        for occupancy in self.occupancies:
            self._validate_occupancy_range(occupancy)

        self._validate_no_duplicate_consists()

    def is_occupied(self) -> bool:
        """Return True if one or more occupancies are present."""
        return bool(self.occupancies)

    def active_consists(self) -> list["Consist"]:
        """Return the consists currently occupying the track."""
        return [occupancy.consist for occupancy in self.occupancies]

    def is_available(self) -> bool:
        """Return True if the track is operationally usable.

        First-version rule:
        - OUT_OF_SERVICE means unavailable
        - all other conditions are considered available
        """
        return self.condition is not TrackCondition.OUT_OF_SERVICE

    def add_occupancy(self, occupancy: TrackOccupancy) -> None:
        """Add an occupancy record to the track.

        This validates range and duplicate consist presence, but does not
        attempt to block dangerous or invalid railroad operating states such
        as collisions or opposing movements.
        """
        self._validate_occupancy_range(occupancy)

        if self.occupancy_for(occupancy.consist) is not None:
            raise ValueError(
                f"Consist already has an occupancy on track '{self.name}'."
            )

        self.occupancies.append(occupancy)

    def remove_occupancy(self, consist: "Consist") -> None:
        """Remove the occupancy record for the given consist."""
        for index, occupancy in enumerate(self.occupancies):
            if occupancy.consist is consist:
                del self.occupancies[index]
                return

        raise ValueError(f"Consist not found on track '{self.name}'.")

    def occupancy_for(self, consist: "Consist") -> TrackOccupancy | None:
        """Return the occupancy record for the given consist, if present."""
        for occupancy in self.occupancies:
            if occupancy.consist is consist:
                return occupancy
        return None

    def occupied_ranges(self) -> list[tuple[float, float]]:
        """Return occupied coordinate ranges on the track."""
        return [
            (occupancy.rear_offset_ft, occupancy.front_offset_ft)
            for occupancy in self.occupancies
        ]

    def has_overlapping_occupancies(self) -> bool:
        """Return True if any occupancy ranges overlap."""
        for i, left in enumerate(self.occupancies):
            for right in self.occupancies[i + 1 :]:
                if left.overlaps(right):
                    return True
        return False

    def has_opposing_movements(self) -> bool:
        """Return True if two moving occupancies oppose each other."""
        moving = [
            occupancy
            for occupancy in self.occupancies
            if occupancy.movement_state == MovementState.MOVING
        ]

        for i, left in enumerate(moving):
            for right in moving[i + 1 :]:
                directions = {left.travel_direction, right.travel_direction}
                if directions == {
                    TravelDirection.TOWARD_A,
                    TravelDirection.TOWARD_B,
                }:
                    return True
        return False

    def supports_direction(self, direction: TravelDirection) -> bool:
        """Return True if the track's traffic rule allows this direction.

        STATIONARY is always allowed because it does not represent movement.
        """
        if direction is TravelDirection.STATIONARY:
            return True

        if self.traffic_rule is TrackTrafficRule.BIDIRECTIONAL:
            return True

        if (
            self.traffic_rule is TrackTrafficRule.A_TO_B_ONLY
            and direction is TravelDirection.TOWARD_B
        ):
            return True

        if (
            self.traffic_rule is TrackTrafficRule.B_TO_A_ONLY
            and direction is TravelDirection.TOWARD_A
        ):
            return True

        return False

    def _validate_occupancy_range(self, occupancy: TrackOccupancy) -> None:
        """Validate that occupancy offsets lie within the track."""
        if occupancy.rear_offset_ft > self.length_ft:
            raise ValueError(
                f"rear_offset_ft {occupancy.rear_offset_ft} exceeds "
                f"track length {self.length_ft} on '{self.name}'."
            )

        if occupancy.front_offset_ft > self.length_ft:
            raise ValueError(
                f"front_offset_ft {occupancy.front_offset_ft} exceeds "
                f"track length {self.length_ft} on '{self.name}'."
            )

    def _validate_no_duplicate_consists(self) -> None:
        """Ensure a consist does not appear twice on the same track."""
        seen_ids: set[int] = set()

        for occupancy in self.occupancies:
            consist_id = id(occupancy.consist)
            if consist_id in seen_ids:
                raise ValueError(
                    f"Duplicate occupancy for same consist on track '{self.name}'."
                )
            seen_ids.add(consist_id)
