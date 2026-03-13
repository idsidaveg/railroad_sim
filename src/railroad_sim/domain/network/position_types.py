from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from uuid import UUID

from railroad_sim.domain.consist import Consist
from railroad_sim.domain.enums import TravelDirection


@dataclass(frozen=True, slots=True)
class NetworkPosition:
    """
    One precise position on one track.

    offset_ft is measured in the track's local coordinate frame:

        A ---------------------------------------------- B
        0 ft                                      track.length_ft
    """

    track_id: UUID
    offset_ft: float

    def __post_init__(self) -> None:
        if self.offset_ft < 0:
            raise ValueError("offset_ft must be >= 0")


@dataclass(frozen=True, slots=True)
class ConsistExtent:
    """
    Canonical network extent of one consist.

    The consist occupies the continuous network path between rear_position
    and front_position.
    """

    consist: Consist
    rear_position: NetworkPosition
    front_position: NetworkPosition
    travel_direction: TravelDirection = TravelDirection.STATIONARY

    def __post_init__(self) -> None:
        if self.rear_position == self.front_position:
            raise ValueError(
                "rear_position and front_position cannot be identical for a consist extent."
            )


@dataclass(frozen=True, slots=True)
class TrackOccupancySegment:
    """
    Derived occupied range for one consist on one track.
    """

    track_id: UUID
    rear_offset_ft: float
    front_offset_ft: float

    def __post_init__(self) -> None:
        if self.rear_offset_ft < 0:
            raise ValueError("rear_offset_ft must be >= 0")

        if self.front_offset_ft < 0:
            raise ValueError("front_offset_ft must be >= 0")

        if self.rear_offset_ft > self.front_offset_ft:
            raise ValueError("rear_offset_ft must be <= front_offset_ft")

    @property
    def length_ft(self) -> float:
        return self.front_offset_ft - self.rear_offset_ft


@dataclass(frozen=True, slots=True)
class ConsistFootprint:
    """
    Derived multi-track footprint of a consist across the network.
    """

    consist: Consist
    segments: tuple[TrackOccupancySegment, ...] = field(default_factory=tuple)

    @property
    def occupied_track_ids(self) -> tuple[UUID, ...]:
        return tuple(segment.track_id for segment in self.segments)

    @property
    def total_occupied_length_ft(self) -> float:
        return sum(segment.length_ft for segment in self.segments)

    @property
    def track_count(self) -> int:
        return len(self.segments)


class ExtentValidationReason(str, Enum):
    VALID = "valid"
    UNKNOWN_REAR_TRACK = "unknown_rear_track"
    UNKNOWN_FRONT_TRACK = "unknown_front_track"
    REAR_OFFSET_OUT_OF_RANGE = "rear_offset_out_of_range"
    FRONT_OFFSET_OUT_OF_RANGE = "front_offset_out_of_range"
    SAME_TRACK_OFFSETS_INVALID = "same_track_offsets_invalid"
    NO_PATH = "no_path"


@dataclass(frozen=True, slots=True)
class ExtentValidationResult:
    is_valid: bool
    reason: ExtentValidationReason
    path_track_ids: tuple[UUID, ...] = ()
