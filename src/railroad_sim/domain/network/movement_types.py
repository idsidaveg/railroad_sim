from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from railroad_sim.domain.junction import JunctionRoute, TrackEndpoint
from railroad_sim.domain.network.movement_enums import (
    MovementBlockReason,
    MovementOptionKind,
)


@dataclass(frozen=True)
class MovementOption:
    source_track_id: UUID
    source_endpoint: TrackEndpoint
    kind: MovementOptionKind

    destination_track_id: UUID | None = None
    destination_endpoint: TrackEndpoint | None = None

    junction_id: UUID | None = None
    required_route: JunctionRoute | None = None
    is_currently_aligned: bool | None = None

    boundary_connection_id: UUID | None = None


@dataclass(frozen=True)
class MovementPathStep:
    from_track_id: UUID
    to_track_id: UUID
    from_endpoint: TrackEndpoint
    to_endpoint: TrackEndpoint
    junction_id: UUID | None = None
    required_route: JunctionRoute | None = None
    is_currently_aligned: bool | None = None
    boundary_connection_id: UUID | None = None


@dataclass(frozen=True)
class MovementPath:
    track_ids: tuple[UUID, ...]
    steps: tuple[MovementPathStep, ...] = field(default_factory=tuple)

    @property
    def required_routes(self) -> tuple[JunctionRoute, ...]:
        return tuple(
            step.required_route
            for step in self.steps
            if step.required_route is not None
        )

    @property
    def misaligned_routes(self) -> tuple[JunctionRoute, ...]:
        return tuple(
            step.required_route
            for step in self.steps
            if step.required_route is not None and step.is_currently_aligned is False
        )


@dataclass(frozen=True)
class MovementFeasibilityResult:
    from_track_id: UUID
    to_track_id: UUID

    path_exists: bool
    can_move: bool

    path: MovementPath | None = None

    blocked_reason: MovementBlockReason = MovementBlockReason.NONE
    blocked_track_id: UUID | None = None
    blocked_route: JunctionRoute | None = None

    required_routes: tuple[JunctionRoute, ...] = field(default_factory=tuple)
    misaligned_routes: tuple[JunctionRoute, ...] = field(default_factory=tuple)
