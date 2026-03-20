from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4

from railroad_sim.domain.yard.facility import Facility
from railroad_sim.domain.yard.facility_types import FacilityType


@dataclass(slots=True)
class Roundhouse(Facility):
    """
    Represents a roundhouse facility connected to a turntable.

    Design rules:
    - does NOT manage track movement
    - does NOT create or modify topology
    - references existing track IDs
    - references a turntable by ID
    """

    turntable_id: UUID = field(default_factory=uuid4)
    stall_track_ids: tuple[UUID, ...] = ()

    def __post_init__(self) -> None:
        Facility.__post_init__(self)

        if self.facility_type != FacilityType.ROUNDHOUSE:
            raise ValueError(
                f"Roundhouse '{self.name}' must have facility_type=ROUNDHOUSE."
            )

        self._validate_stall_tracks()

    def has_stalls(self) -> bool:
        return bool(self.stall_track_ids)

    def stall_count(self) -> int:
        return len(self.stall_track_ids)

    def has_stall(self, track_id: UUID) -> bool:
        return track_id in self.stall_track_ids

    def _validate_stall_tracks(self) -> None:
        if len(set(self.stall_track_ids)) != len(self.stall_track_ids):
            raise ValueError(f"Roundhouse '{self.name}' has duplicate stall_track_ids.")
