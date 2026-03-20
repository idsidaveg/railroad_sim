from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4

from railroad_sim.domain.yard.facility_types import FacilityType


@dataclass(slots=True)
class Facility:
    """
    Describes a passive railroad facility or structure.

    This object does not define topology or movement behavior. It represents
    a named place or structure that may be associated with one or more tracks.

    Examples:
    - freight house
    - engine house
    - repair shop
    - office
    - depot
    - industry building
    """

    name: str
    facility_type: FacilityType

    served_track_ids: tuple[UUID, ...] = ()
    description: str | None = None

    facility_id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("facility name must not be blank")

        self._validate_unique_served_tracks()

    def serves_track(self, track_id: UUID) -> bool:
        """Return True if the facility is associated with the given track."""
        return track_id in self.served_track_ids

    def has_served_tracks(self) -> bool:
        """Return True if one or more served tracks are associated."""
        return bool(self.served_track_ids)

    def _validate_unique_served_tracks(self) -> None:
        if len(set(self.served_track_ids)) != len(self.served_track_ids):
            raise ValueError(f"Facility '{self.name}' has duplicate served_track_ids.")
