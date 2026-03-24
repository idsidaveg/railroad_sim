from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4

from railroad_sim.domain.network.position_types import ConsistExtent


@dataclass(slots=True)
class Turntable:
    """
    Represents a railroad turntable as a yard-domain object.

    V1 scope:
    - the turntable is NOT modeled as a Junction
    - it tracks which connected track is currently aligned to the bridge
    - it has exactly one bridge track
    - it supports one approach track
    - it supports zero or more stall tracks
    - it supports zero or more additional service tracks

    Design intent:
    - movement remains track-based
    - the bridge is a real track in the layout
    - the turntable controls which external track is currently connected
    """

    name: str
    bridge_length_ft: float

    bridge_track_id: UUID
    approach_track_id: UUID
    max_gross_weight_lb: float = 600_000.0
    stall_track_ids: tuple[UUID, ...] = ()
    service_track_ids: tuple[UUID, ...] = ()

    aligned_track_id: UUID | None = None

    turntable_id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("turntable name must not be blank")

        if self.bridge_length_ft <= 0:
            raise ValueError("bridge_length_ft must be > 0")

        if self.max_gross_weight_lb <= 0:
            raise ValueError("max_gross_weight_lb must be > 0")

        self._validate_track_membership()
        self._validate_alignment()

    @property
    def connected_track_ids(self) -> tuple[UUID, ...]:
        """
        Return all non-bridge tracks that can be aligned to the bridge.

        The approach track is always first, followed by stall tracks and then
        service tracks.
        """
        return (
            self.approach_track_id,
            *self.stall_track_ids,
            *self.service_track_ids,
        )

    @property
    def all_track_ids(self) -> tuple[UUID, ...]:
        """
        Return every track associated with the turntable, including the bridge.
        """
        return (
            self.bridge_track_id,
            self.approach_track_id,
            *self.stall_track_ids,
            *self.service_track_ids,
        )

    def can_align_to(self, track_id: UUID) -> bool:
        """
        Return True if the track is one of the turntable's connected
        non-bridge tracks.
        """
        return track_id in self.connected_track_ids

    def align_to(
        self,
        track_id: UUID,
        *,
        protected_extent: ConsistExtent | None = None,
    ) -> None:
        """
        Align the turntable bridge to the requested connected track.

        V1 rule:
        - exactly one connected non-bridge track may be aligned at a time

        Safety rule:
        - if a protected extent is provided, it must be fully on the bridge
          before the turntable may be re-aligned
        """
        if not self.can_align_to(track_id):
            raise ValueError(
                f"Track id {track_id} is not connected to turntable '{self.name}'."
            )

        if protected_extent is not None and not self._extent_fully_on_bridge(
            protected_extent
        ):
            raise ValueError(
                f"Turntable '{self.name}' can only be aligned when the protected "
                "extent is fully on the bridge."
            )

        self.aligned_track_id = track_id

    def clear_alignment(self) -> None:
        """Clear any current alignment."""
        self.aligned_track_id = None

    def is_aligned_to(self, track_id: UUID) -> bool:
        """Return True if the bridge is currently aligned to the given track."""
        return self.aligned_track_id == track_id

    def all_stall_track_ids(self) -> tuple[UUID, ...]:
        """Return all stall track ids."""
        return self.stall_track_ids

    def all_service_track_ids(self) -> tuple[UUID, ...]:
        """Return all non-stall service track ids."""
        return self.service_track_ids

    def _validate_track_membership(self) -> None:
        if self.bridge_track_id in self.connected_track_ids:
            raise ValueError(
                f"Turntable '{self.name}' bridge_track_id must be distinct from "
                "the approach, stall, and service tracks."
            )

        all_tracks = self.all_track_ids

        if len(set(all_tracks)) != len(all_tracks):
            raise ValueError(f"Turntable '{self.name}' has duplicate track ids.")

    def _validate_alignment(self) -> None:
        if self.aligned_track_id is None:
            return

        if self.aligned_track_id not in self.connected_track_ids:
            raise ValueError(
                f"aligned_track_id for turntable '{self.name}' must reference "
                "the approach, a stall track, or a service track."
            )

    # helper that checks if the Consist is fully on the bridge
    def _extent_fully_on_bridge(self, extent: ConsistExtent) -> bool:
        return (
            extent.rear_position.track_id == self.bridge_track_id
            and extent.front_position.track_id == self.bridge_track_id
        )
