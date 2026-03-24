from __future__ import annotations

from dataclasses import dataclass

from railroad_sim.domain.enums import TrackEnd, TravelDirection
from railroad_sim.domain.junction import TrackEndpoint
from railroad_sim.domain.network.consist_movement_types import (
    MoveCommand,
    MovementExecutionResult,
)
from railroad_sim.domain.network.contact_resolution_service import (
    ContactResolutionService,
)
from railroad_sim.domain.network.contact_resolution_types import ContactRelationship
from railroad_sim.domain.network.footprint_service import FootprintService
from railroad_sim.domain.network.position_types import (
    ConsistExtent,
    ConsistFootprint,
    NetworkPosition,
)
from railroad_sim.domain.network.rail_network import RailNetwork
from railroad_sim.domain.network.topology_movement_enums import (
    MovementBlockReason,
    MovementOptionKind,
)
from railroad_sim.domain.network.topology_movement_service import (
    TopologyMovementService,
)
from railroad_sim.domain.network.turnout_evaluator import TurnoutEvaluator


@dataclass(frozen=True, slots=True)
class _WalkResult:
    position: NetworkPosition
    actual_distance_ft: float
    final_direction: TravelDirection
    stop_reason: MovementBlockReason | None = None


class ConsistMovementService:
    """
    Execution-layer movement service for displacing an existing ConsistExtent
    through the rail network by distance.

    This service does NOT replace the existing MovementService. It uses that
    service's topology and alignment knowledge to move one physical end of
    the consist, then derives the opposite end using consist length.

    v1 behavior:
    - moves an extent forward or reverse by distance
    - obeys current topology and route alignment
    - stops early at dead ends, boundaries, or ambiguous continuations
    - recomputes footprint and turnout fouling after movement

    v1 non-goals:
    - physics / acceleration
    - train-to-train collision detection
    - signal enforcement
    - automatic turnout throwing
    - multi-path route selection
    """

    def __init__(
        self,
        *,
        network: RailNetwork,
        footprint_service: FootprintService,
        turnout_evaluator: TurnoutEvaluator,
        topology_movement_service: TopologyMovementService | None = None,
        contact_resolution_service: ContactResolutionService | None = None,
    ) -> None:
        self._network = network
        self._footprint_service = footprint_service
        self._turnout_evaluator = turnout_evaluator
        self._topology = topology_movement_service or TopologyMovementService(network)
        self._contact_resolution = (
            contact_resolution_service or ContactResolutionService()
        )

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def move_extent(
        self,
        *,
        extent: ConsistExtent,
        command: MoveCommand,
        distance_ft: float,
        turnout_windows_by_key: dict,
        active_footprints: tuple[ConsistFootprint, ...] = (),
    ) -> MovementExecutionResult:
        if distance_ft < 0:
            raise ValueError("distance_ft must be >= 0")

        consist_length_ft = extent.consist.operational_length_ft
        current_direction = self._normalized_travel_direction(extent)

        if command is MoveCommand.FORWARD:
            advanced_front = self._walk_position(
                start=extent.front_position,
                direction=current_direction,
                distance_ft=distance_ft,
            )

            derived_rear = self._walk_position_strict(
                start=advanced_front.position,
                direction=self._opposite_direction(advanced_front.final_direction),
                distance_ft=consist_length_ft,
                context="derive rear_position from moved front_position",
            )

            bridge_length_ft = self._topology.bridge_length_for_track(
                advanced_front.position.track_id
            )
            max_bridge_gross_weight_lb = (
                self._topology.max_gross_weight_for_bridge_track(
                    advanced_front.position.track_id
                )
            )
            entering_bridge_from_non_bridge = (
                bridge_length_ft is not None
                and extent.front_position.track_id != advanced_front.position.track_id
            )
            bridge_cannot_contain_consist = (
                bridge_length_ft is not None
                and consist_length_ft > bridge_length_ft
                and derived_rear.position.track_id != advanced_front.position.track_id
            )
            bridge_gross_weight_exceeded = (
                max_bridge_gross_weight_lb is not None
                and extent.consist.gross_weight_lb > max_bridge_gross_weight_lb
            )
            stopped_at_bridge_limit = (
                advanced_front.stop_reason == MovementBlockReason.ROUTE_MISALIGNED
            )
            # length refusal block
            if (
                entering_bridge_from_non_bridge
                and bridge_cannot_contain_consist
                and stopped_at_bridge_limit
            ):
                blocked_footprint = self._footprint_service.footprint_for_extent(extent)
                blocked_turnout_states = self._turnout_evaluator.evaluate_extent(
                    extent=extent,
                    turnout_windows_by_key=turnout_windows_by_key,
                )
                return MovementExecutionResult(
                    requested_distance_ft=distance_ft,
                    actual_distance_ft=0.0,
                    prior_extent=extent,
                    new_extent=extent,
                    footprint=blocked_footprint,
                    turnout_states=blocked_turnout_states,
                    movement_limited=True,
                    stop_reason=MovementBlockReason.TURNTABLE_BRIDGE_LENGTH_EXCEEDED,
                )

            # gross weight refusal block
            if entering_bridge_from_non_bridge and bridge_gross_weight_exceeded:
                blocked_footprint = self._footprint_service.footprint_for_extent(extent)
                blocked_turnout_states = self._turnout_evaluator.evaluate_extent(
                    extent=extent,
                    turnout_windows_by_key=turnout_windows_by_key,
                )
                return MovementExecutionResult(
                    requested_distance_ft=distance_ft,
                    actual_distance_ft=0.0,
                    prior_extent=extent,
                    new_extent=extent,
                    footprint=blocked_footprint,
                    turnout_states=blocked_turnout_states,
                    movement_limited=True,
                    stop_reason=MovementBlockReason.TURNTABLE_BRIDGE_WEIGHT_EXCEEDED,
                )

            new_extent = ConsistExtent(
                consist=extent.consist,
                rear_position=derived_rear.position,
                front_position=advanced_front.position,
                travel_direction=advanced_front.final_direction,
            )

            actual_distance_ft = advanced_front.actual_distance_ft
            movement_limited = actual_distance_ft < distance_ft
            stop_reason = advanced_front.stop_reason or MovementBlockReason.NONE

        elif command is MoveCommand.REVERSE:
            reverse_direction = self._opposite_direction(current_direction)

            advanced_rear = self._walk_position(
                start=extent.rear_position,
                direction=reverse_direction,
                distance_ft=distance_ft,
            )

            derived_front = self._walk_position_strict(
                start=advanced_rear.position,
                direction=self._opposite_direction(advanced_rear.final_direction),
                distance_ft=consist_length_ft,
                context="derive front_position from moved rear_position",
            )

            new_extent = ConsistExtent(
                consist=extent.consist,
                rear_position=advanced_rear.position,
                front_position=derived_front.position,
                travel_direction=advanced_rear.final_direction,
            )

            actual_distance_ft = advanced_rear.actual_distance_ft
            movement_limited = actual_distance_ft < distance_ft
            stop_reason = advanced_rear.stop_reason or MovementBlockReason.NONE

        else:
            raise ValueError(f"Unsupported MoveCommand: {command}")

        footprint = self._footprint_service.footprint_for_extent(new_extent)

        interaction = self._contact_resolution.classify_against_active_footprints(
            moving_footprint=footprint,
            active_footprints=active_footprints,
        )

        if interaction.relationship is ContactRelationship.OVERLAP:
            blocked_footprint = self._footprint_service.footprint_for_extent(extent)
            blocked_turnout_states = self._turnout_evaluator.evaluate_extent(
                extent=extent, turnout_windows_by_key=turnout_windows_by_key
            )
            return MovementExecutionResult(
                requested_distance_ft=distance_ft,
                actual_distance_ft=0.0,
                prior_extent=extent,
                new_extent=extent,
                footprint=blocked_footprint,
                turnout_states=blocked_turnout_states,
                movement_limited=True,
                stop_reason=MovementBlockReason.TRACK_OCCUPIED,
            )

        turnout_states = self._turnout_evaluator.evaluate_extent(
            extent=new_extent,
            turnout_windows_by_key=turnout_windows_by_key,
        )

        return MovementExecutionResult(
            requested_distance_ft=distance_ft,
            actual_distance_ft=actual_distance_ft,
            prior_extent=extent,
            new_extent=new_extent,
            footprint=footprint,
            turnout_states=turnout_states,
            movement_limited=movement_limited,
            stop_reason=stop_reason,
        )

    # -------------------------------------------------------------------------
    # Position walking
    # -------------------------------------------------------------------------

    def _walk_position(
        self,
        *,
        start: NetworkPosition,
        direction: TravelDirection,
        distance_ft: float,
    ) -> _WalkResult:
        if distance_ft < 0:
            raise ValueError("distance_ft must be >= 0")

        self._get_track(start.track_id)
        current = start
        current_direction = direction
        moved_ft = 0.0
        remaining_ft = distance_ft

        while remaining_ft > 0:
            track = self._get_track(current.track_id)

            if current_direction is TravelDirection.TOWARD_B:
                distance_to_exit_ft = track.length_ft - current.offset_ft
                exit_end = TrackEnd.B
            elif current_direction is TravelDirection.TOWARD_A:
                distance_to_exit_ft = current.offset_ft
                exit_end = TrackEnd.A
            else:
                raise ValueError(
                    "Cannot walk a position with TravelDirection.STATIONARY."
                )

            # Entire move fits on current track.
            if remaining_ft <= distance_to_exit_ft:
                if current_direction is TravelDirection.TOWARD_B:
                    new_offset_ft = current.offset_ft + remaining_ft
                else:
                    new_offset_ft = current.offset_ft - remaining_ft

                moved_ft += remaining_ft
                return _WalkResult(
                    position=NetworkPosition(
                        track_id=current.track_id,
                        offset_ft=new_offset_ft,
                    ),
                    actual_distance_ft=moved_ft,
                    final_direction=current_direction,
                    stop_reason=None,
                )

            # Move exactly to the current track endpoint, then try to continue.
            current = NetworkPosition(
                track_id=current.track_id,
                offset_ft=track.length_ft if exit_end is TrackEnd.B else 0.0,
            )
            moved_ft += distance_to_exit_ft
            remaining_ft -= distance_to_exit_ft

            continuation = self._resolve_continuation(
                track_id=current.track_id,
                exit_end=exit_end,
            )
            if continuation is None:
                return _WalkResult(
                    position=current,
                    actual_distance_ft=moved_ft,
                    final_direction=current_direction,
                    stop_reason=MovementBlockReason.NO_PATH,
                )

            if continuation.stop_reason is not None:
                return _WalkResult(
                    position=current,
                    actual_distance_ft=moved_ft,
                    final_direction=current_direction,
                    stop_reason=continuation.stop_reason,
                )

            current = continuation.position
            current_direction = continuation.direction

        return _WalkResult(
            position=current,
            actual_distance_ft=moved_ft,
            final_direction=current_direction,
            stop_reason=None,
        )

    def _walk_position_strict(
        self,
        *,
        start: NetworkPosition,
        direction: TravelDirection,
        distance_ft: float,
        context: str,
    ) -> _WalkResult:
        result = self._walk_position(
            start=start,
            direction=direction,
            distance_ft=distance_ft,
        )
        if result.actual_distance_ft < distance_ft:
            raise ValueError(
                f"Unable to {context}: requested {distance_ft:.3f} ft, "
                f"actual {result.actual_distance_ft:.3f} ft, "
                f"stop_reason={result.stop_reason!r}"
            )
        return result

    # -------------------------------------------------------------------------
    # Continuation resolution
    # -------------------------------------------------------------------------

    @dataclass(frozen=True, slots=True)
    class _Continuation:
        position: NetworkPosition
        direction: TravelDirection
        stop_reason: MovementBlockReason | None = None

    def _resolve_continuation(
        self,
        *,
        track_id,
        exit_end: TrackEnd,
    ) -> _Continuation | None:
        track = self._get_track(track_id)
        endpoint = TrackEndpoint(track=track, end=exit_end)

        options = self._topology.movement_options_from_endpoint(endpoint)

        # Boundaries mean we reached the edge of the known network.
        boundary_options = [
            option for option in options if option.kind is MovementOptionKind.BOUNDARY
        ]
        if boundary_options:
            return self._Continuation(
                position=NetworkPosition(
                    track_id=track.track_id,
                    offset_ft=track.length_ft if exit_end is TrackEnd.B else 0.0,
                ),
                direction=TravelDirection.STATIONARY,
                stop_reason=MovementBlockReason.BOUNDARY_EXIT,
            )

        aligned_track_options = [
            option
            for option in options
            if option.kind is MovementOptionKind.TRACK
            and option.destination_track_id is not None
            and option.destination_endpoint is not None
            and option.is_currently_aligned is True
        ]

        if not aligned_track_options:
            return self._Continuation(
                position=NetworkPosition(
                    track_id=track.track_id,
                    offset_ft=track.length_ft if exit_end is TrackEnd.B else 0.0,
                ),
                direction=TravelDirection.STATIONARY,
                stop_reason=MovementBlockReason.ROUTE_MISALIGNED,
            )

        if len(aligned_track_options) > 1:
            return self._Continuation(
                position=NetworkPosition(
                    track_id=track.track_id,
                    offset_ft=track.length_ft if exit_end is TrackEnd.B else 0.0,
                ),
                direction=TravelDirection.STATIONARY,
                stop_reason=MovementBlockReason.AMBIGUOUS_CONTINUATION,
            )

        option = aligned_track_options[0]
        destination = option.destination_endpoint
        destination_track_id = option.destination_track_id

        if destination is None or destination_track_id is None:
            return self._Continuation(
                position=NetworkPosition(
                    track_id=track.track_id,
                    offset_ft=track.length_ft if exit_end is TrackEnd.B else 0.0,
                ),
                direction=TravelDirection.STATIONARY,
                stop_reason=MovementBlockReason.INVALID_TRACK_OPTION,
            )

        destination_track = destination.track

        if destination.end is TrackEnd.A:
            entry_offset_ft = 0.0
            new_direction = TravelDirection.TOWARD_B
        else:
            entry_offset_ft = destination_track.length_ft
            new_direction = TravelDirection.TOWARD_A

        return self._Continuation(
            position=NetworkPosition(
                track_id=destination_track.track_id,
                offset_ft=entry_offset_ft,
            ),
            direction=new_direction,
            stop_reason=None,
        )

    # -------------------------------------------------------------------------
    # Direction / extent helpers
    # -------------------------------------------------------------------------

    def _normalized_travel_direction(
        self,
        extent: ConsistExtent,
    ) -> TravelDirection:
        if extent.travel_direction is not TravelDirection.STATIONARY:
            return extent.travel_direction

        rear = extent.rear_position
        front = extent.front_position

        if rear.track_id == front.track_id:
            return TravelDirection.TOWARD_B

        path = self._topology.find_path_between_tracks(
            rear.track_id,
            front.track_id,
        )
        if path is None or not path.steps:
            raise ValueError(
                "Cannot infer travel direction for extent with no inter-track path."
            )

        first_step = path.steps[0]
        if first_step.from_endpoint.end is TrackEnd.A:
            return TravelDirection.TOWARD_A
        return TravelDirection.TOWARD_B

    def _opposite_direction(self, direction: TravelDirection) -> TravelDirection:
        if direction is TravelDirection.TOWARD_A:
            return TravelDirection.TOWARD_B
        if direction is TravelDirection.TOWARD_B:
            return TravelDirection.TOWARD_A
        raise ValueError("TravelDirection.STATIONARY has no opposite direction.")

    def _get_track(self, track_id):
        return self._network.get_track(track_id)
