from __future__ import annotations

from collections import deque
from uuid import UUID

from railroad_sim.domain.enums import TrackEnd
from railroad_sim.domain.junction import Junction, JunctionRoute, TrackEndpoint
from railroad_sim.domain.network.movement_types import (
    MovementFeasibilityResult,
    MovementOption,
    MovementPath,
    MovementPathStep,
)
from railroad_sim.domain.network.rail_network import RailNetwork
from railroad_sim.domain.network.topology_movement_enums import (
    MovementBlockReason,
    MovementOptionKind,
)
from railroad_sim.domain.track import Track


class TopologyMovementService:
    """
    Read-only service for determining legal movement options at the network topology layer.

    Scope of v1:
    - immediate movement options from a track or endpoint
    - single-path discovery between tracks
    - path feasibility based on:
        * topology connectivity
        * required junction route alignment
        * track condition passability

    Out of scope:
    - physics
    - occupancy movement
    - dispatch authority
    - alternate path search/scoring
    - conflict resolution
    """

    def __init__(self, network: RailNetwork) -> None:
        self._network = network

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def movement_options_from_track(
        self,
        track_id: UUID,
    ) -> tuple[MovementOption, ...]:
        track = self._get_track(track_id)
        options: list[MovementOption] = []

        for endpoint in self._endpoints_for_track(track):
            options.extend(self.movement_options_from_endpoint(endpoint))

        return self._sort_options(tuple(options))

    def movement_options_from_endpoint(
        self,
        endpoint: TrackEndpoint,
    ) -> tuple[MovementOption, ...]:
        self._validate_endpoint(endpoint)

        options: list[MovementOption] = []
        source_track_id = endpoint.track.track_id

        # Boundary exits
        for boundary in self._network.boundary_connections_for_endpoint(endpoint):
            options.append(
                MovementOption(
                    source_track_id=source_track_id,
                    source_endpoint=endpoint,
                    kind=MovementOptionKind.BOUNDARY,
                    boundary_connection_id=boundary.connection_id,
                )
            )

        # Junction-mediated exits
        for junction in self._network.junctions_for_endpoint(endpoint):
            for route in junction.available_routes_from(endpoint):
                destination = route.other_endpoint(endpoint)

                options.append(
                    MovementOption(
                        source_track_id=source_track_id,
                        source_endpoint=endpoint,
                        kind=MovementOptionKind.TRACK,
                        destination_track_id=destination.track.track_id,
                        destination_endpoint=destination,
                        junction_id=junction.junction_id,
                        required_route=route,
                        is_currently_aligned=self._is_route_currently_aligned(
                            junction, route
                        ),
                    )
                )

        return self._sort_options(tuple(options))

    def find_path_between_tracks(
        self,
        from_track_id: UUID,
        to_track_id: UUID,
    ) -> MovementPath | None:
        """
        Find one topological path between tracks using BFS.

        Notes:
        - shortest by hop count
        - deterministic if neighbor ordering is deterministic
        - ignores passability and alignment as blockers during discovery;
          those are evaluated later by can_move_between_tracks()
        """
        self._get_track(from_track_id)
        self._get_track(to_track_id)

        if from_track_id == to_track_id:
            return MovementPath(track_ids=(from_track_id,), steps=())

        queue: deque[UUID] = deque([from_track_id])
        visited: set[UUID] = {from_track_id}
        prev: dict[UUID, tuple[UUID, MovementPathStep]] = {}

        while queue:
            current_track_id = queue.popleft()

            for step in self._neighbor_steps_from_track(current_track_id):
                neighbor_track_id = step.to_track_id

                if neighbor_track_id in visited:
                    continue

                visited.add(neighbor_track_id)
                prev[neighbor_track_id] = (current_track_id, step)

                if neighbor_track_id == to_track_id:
                    return self._reconstruct_path(
                        start_track_id=from_track_id,
                        end_track_id=to_track_id,
                        prev=prev,
                    )

                queue.append(neighbor_track_id)

        return None

    def can_move_between_tracks(
        self,
        from_track_id: UUID,
        to_track_id: UUID,
    ) -> MovementFeasibilityResult:
        self._get_track(from_track_id)
        self._get_track(to_track_id)

        path = self.find_path_between_tracks(from_track_id, to_track_id)
        if path is None:
            return MovementFeasibilityResult(
                from_track_id=from_track_id,
                to_track_id=to_track_id,
                path_exists=False,
                can_move=False,
                path=None,
                blocked_reason=MovementBlockReason.NO_PATH,
            )

        # Track condition screening
        for track_id in path.track_ids:
            track = self._get_track(track_id)
            if not self._is_track_passable(track):
                return MovementFeasibilityResult(
                    from_track_id=from_track_id,
                    to_track_id=to_track_id,
                    path_exists=True,
                    can_move=False,
                    path=path,
                    blocked_reason=MovementBlockReason.TRACK_CONDITION,
                    blocked_track_id=track_id,
                    required_routes=path.required_routes,
                    misaligned_routes=path.misaligned_routes,
                )

        # Route alignment screening
        misaligned = path.misaligned_routes
        if misaligned:
            return MovementFeasibilityResult(
                from_track_id=from_track_id,
                to_track_id=to_track_id,
                path_exists=True,
                can_move=False,
                path=path,
                blocked_reason=MovementBlockReason.ROUTE_MISALIGNED,
                blocked_route=misaligned[0],
                required_routes=path.required_routes,
                misaligned_routes=misaligned,
            )

        return MovementFeasibilityResult(
            from_track_id=from_track_id,
            to_track_id=to_track_id,
            path_exists=True,
            can_move=True,
            path=path,
            blocked_reason=MovementBlockReason.NONE,
            required_routes=path.required_routes,
            misaligned_routes=(),
        )

    def boundary_exists_at_endpoint(self, endpoint: TrackEndpoint) -> bool:
        self._validate_endpoint(endpoint)
        return bool(self._network.boundary_connections_for_endpoint(endpoint))

    # -------------------------------------------------------------------------
    # Path helpers
    # -------------------------------------------------------------------------

    def _neighbor_steps_from_track(
        self,
        track_id: UUID,
    ) -> tuple[MovementPathStep, ...]:
        track = self._get_track(track_id)
        steps: list[MovementPathStep] = []

        for endpoint in self._endpoints_for_track(track):
            for option in self.movement_options_from_endpoint(endpoint):
                if option.kind is not MovementOptionKind.TRACK:
                    continue
                if (
                    option.destination_track_id is None
                    or option.destination_endpoint is None
                ):
                    continue

                steps.append(
                    MovementPathStep(
                        from_track_id=track_id,
                        to_track_id=option.destination_track_id,
                        from_endpoint=endpoint,
                        to_endpoint=option.destination_endpoint,
                        junction_id=option.junction_id,
                        required_route=option.required_route,
                        is_currently_aligned=option.is_currently_aligned,
                        boundary_connection_id=option.boundary_connection_id,
                    )
                )

        return self._sort_steps(tuple(steps))

    def _reconstruct_path(
        self,
        start_track_id: UUID,
        end_track_id: UUID,
        prev: dict[UUID, tuple[UUID, MovementPathStep]],
    ) -> MovementPath:
        ordered_steps: list[MovementPathStep] = []
        cursor = end_track_id

        while cursor != start_track_id:
            parent_track_id, step = prev[cursor]
            ordered_steps.append(step)
            cursor = parent_track_id

        ordered_steps.reverse()

        track_ids = [start_track_id]
        for step in ordered_steps:
            track_ids.append(step.to_track_id)

        return MovementPath(
            track_ids=tuple(track_ids),
            steps=tuple(ordered_steps),
        )

    # -------------------------------------------------------------------------
    # Track passability
    # -------------------------------------------------------------------------

    def _is_track_passable(self, track: Track) -> bool:
        return track.is_available()

    # -------------------------------------------------------------------------
    # Sorting / determinism
    # -------------------------------------------------------------------------

    def _sort_options(
        self,
        options: tuple[MovementOption, ...],
    ) -> tuple[MovementOption, ...]:
        return tuple(
            sorted(
                options,
                key=lambda o: (
                    self._endpoint_sort_key(o.source_endpoint),
                    o.kind.value,
                    str(o.destination_track_id)
                    if o.destination_track_id is not None
                    else "",
                    str(o.junction_id) if o.junction_id is not None else "",
                    self._route_sort_key(o.required_route),
                    str(o.boundary_connection_id)
                    if o.boundary_connection_id is not None
                    else "",
                ),
            )
        )

    def _sort_steps(
        self,
        steps: tuple[MovementPathStep, ...],
    ) -> tuple[MovementPathStep, ...]:
        return tuple(
            sorted(
                steps,
                key=lambda s: (
                    str(s.from_track_id),
                    self._endpoint_sort_key(s.from_endpoint),
                    str(s.to_track_id),
                    self._endpoint_sort_key(s.to_endpoint),
                    str(s.junction_id) if s.junction_id is not None else "",
                    self._route_sort_key(s.required_route),
                ),
            )
        )

    def _route_sort_key(self, route: JunctionRoute | None) -> tuple[str, str, str, str]:
        if route is None:
            return ("", "", "", "")

        return (
            str(route.from_endpoint.track.track_id),
            route.from_endpoint.end.value,
            str(route.to_endpoint.track.track_id),
            route.to_endpoint.end.value,
        )

    # -------------------------------------------------------------------------
    # Network / endpoint helpers
    # -------------------------------------------------------------------------

    def _get_track(self, track_id: UUID) -> Track:
        return self._network.get_track(track_id)

    def _endpoints_for_track(self, track: Track) -> tuple[TrackEndpoint, TrackEndpoint]:
        return (
            TrackEndpoint(track=track, end=TrackEnd.A),
            TrackEndpoint(track=track, end=TrackEnd.B),
        )

    def _validate_endpoint(self, endpoint: TrackEndpoint) -> None:
        self._get_track(endpoint.track.track_id)

    def _endpoint_sort_key(self, endpoint: TrackEndpoint) -> tuple[str, str]:
        return (str(endpoint.track.track_id), endpoint.end.value)

    # -------------------------------------------------------------------------
    # Junction helpers
    # -------------------------------------------------------------------------

    def _is_route_currently_aligned(
        self,
        junction: Junction,
        route: JunctionRoute,
    ) -> bool:
        return route in junction.aligned_routes
