from __future__ import annotations

from uuid import UUID

from railroad_sim.domain.enums import TrackEnd
from railroad_sim.domain.junction import TrackEndpoint
from railroad_sim.domain.network.position_types import (
    ConsistExtent,
    ConsistFootprint,
    ExtentValidationReason,
    ExtentValidationResult,
    NetworkPosition,
    TrackOccupancySegment,
)
from railroad_sim.domain.network.rail_network import RailNetwork
from railroad_sim.domain.network.topology_movement_service import (
    TopologyMovementService,
)
from railroad_sim.domain.track import Track


class FootprintService:
    """
    Read-only service that validates consist extents and derives their
    multi-track occupied footprint across a rail network.

    v1 assumptions:
    - rear_position and front_position define a continuous occupied span
    - if rear/front are on different tracks, the shortest discovered path
      between them is used
    - current junction alignment is NOT used as a blocker for footprint
      derivation, because footprint represents physical occupancy truth
    """

    def __init__(
        self,
        network: RailNetwork,
        movement_service: TopologyMovementService | None = None,
    ) -> None:
        self._network = network
        self._movement_service = movement_service or TopologyMovementService(network)

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def validate_extent(self, extent: ConsistExtent) -> ExtentValidationResult:
        rear_track = self._safe_get_track(extent.rear_position.track_id)
        if rear_track is None:
            return ExtentValidationResult(
                is_valid=False,
                reason=ExtentValidationReason.UNKNOWN_REAR_TRACK,
                path_track_ids=(),
            )

        front_track = self._safe_get_track(extent.front_position.track_id)
        if front_track is None:
            return ExtentValidationResult(
                is_valid=False,
                reason=ExtentValidationReason.UNKNOWN_FRONT_TRACK,
                path_track_ids=(),
            )

        if not self._position_in_range(extent.rear_position, rear_track):
            return ExtentValidationResult(
                is_valid=False,
                reason=ExtentValidationReason.REAR_OFFSET_OUT_OF_RANGE,
                path_track_ids=(),
            )

        if not self._position_in_range(extent.front_position, front_track):
            return ExtentValidationResult(
                is_valid=False,
                reason=ExtentValidationReason.FRONT_OFFSET_OUT_OF_RANGE,
                path_track_ids=(),
            )

        if extent.rear_position.track_id == extent.front_position.track_id:
            if extent.rear_position.offset_ft > extent.front_position.offset_ft:
                return ExtentValidationResult(
                    is_valid=False,
                    reason=ExtentValidationReason.SAME_TRACK_OFFSETS_INVALID,
                    path_track_ids=(),
                )

            return ExtentValidationResult(
                is_valid=True,
                reason=ExtentValidationReason.VALID,
                path_track_ids=(extent.rear_position.track_id,),
            )

        path = self._movement_service.find_path_between_tracks(
            extent.rear_position.track_id,
            extent.front_position.track_id,
        )

        if path is None:
            return ExtentValidationResult(
                is_valid=False,
                reason=ExtentValidationReason.NO_PATH,
                path_track_ids=(),
            )

        return ExtentValidationResult(
            is_valid=True,
            reason=ExtentValidationReason.VALID,
            path_track_ids=path.track_ids,
        )

    def footprint_for_extent(self, extent: ConsistExtent) -> ConsistFootprint:
        validation = self.validate_extent(extent)
        if not validation.is_valid:
            raise ValueError(f"Invalid consist extent: {validation.reason.value}")

        path_track_ids = validation.path_track_ids

        if len(path_track_ids) == 1:
            segment = TrackOccupancySegment(
                track_id=extent.rear_position.track_id,
                rear_offset_ft=extent.rear_position.offset_ft,
                front_offset_ft=extent.front_position.offset_ft,
            )
            return ConsistFootprint(
                consist=extent.consist,
                segments=(segment,),
            )

        segments = self._segments_for_multi_track_extent(
            extent=extent,
            path_track_ids=path_track_ids,
        )

        return ConsistFootprint(
            consist=extent.consist,
            segments=segments,
        )

    def occupied_track_ids_for_extent(
        self,
        extent: ConsistExtent,
    ) -> tuple[UUID, ...]:
        validation = self.validate_extent(extent)
        if not validation.is_valid:
            raise ValueError(f"Invalid consist extent: {validation.reason.value}")
        return validation.path_track_ids

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _segments_for_multi_track_extent(
        self,
        extent: ConsistExtent,
        path_track_ids: tuple[UUID, ...],
    ) -> tuple[TrackOccupancySegment, ...]:
        rear_track_id = extent.rear_position.track_id
        front_track_id = extent.front_position.track_id

        # Defensive sanity check
        if path_track_ids[0] != rear_track_id or path_track_ids[-1] != front_track_id:
            raise ValueError("Derived path does not match extent endpoints.")

        # Special handling for 2-track spans.
        #
        # We must derive segment direction from the actual connected endpoints
        # between the two tracks, not from midpoint heuristics. This is required
        # for cases like:
        # - A <-> A  (approach -> bridge)
        # - B <-> B  (lead -> approach in scenario wiring)
        # - B <-> A  (bridge -> stall)
        if len(path_track_ids) == 2:
            rear_track = self._get_track(rear_track_id)
            front_track = self._get_track(front_track_id)

            rear_connected_end = self._connected_end_between_tracks(
                source_track=rear_track,
                destination_track=front_track,
            )
            front_connected_end = self._connected_end_between_tracks(
                source_track=front_track,
                destination_track=rear_track,
            )

            rear_end_offset = (
                0.0 if rear_connected_end is TrackEnd.A else rear_track.length_ft
            )
            front_start_offset = (
                0.0 if front_connected_end is TrackEnd.A else front_track.length_ft
            )

            rear_segment_rear = min(extent.rear_position.offset_ft, rear_end_offset)
            rear_segment_front = max(extent.rear_position.offset_ft, rear_end_offset)

            front_segment_rear = min(
                front_start_offset,
                extent.front_position.offset_ft,
            )
            front_segment_front = max(
                front_start_offset,
                extent.front_position.offset_ft,
            )

            return (
                TrackOccupancySegment(
                    track_id=rear_track_id,
                    rear_offset_ft=rear_segment_rear,
                    front_offset_ft=rear_segment_front,
                ),
                TrackOccupancySegment(
                    track_id=front_track_id,
                    rear_offset_ft=front_segment_rear,
                    front_offset_ft=front_segment_front,
                ),
            )

        # Default behavior for 3+ track paths
        segments: list[TrackOccupancySegment] = []

        for index, track_id in enumerate(path_track_ids):
            track = self._get_track(track_id)

            if index == 0:
                segments.append(
                    TrackOccupancySegment(
                        track_id=track_id,
                        rear_offset_ft=extent.rear_position.offset_ft,
                        front_offset_ft=track.length_ft,
                    )
                )
            elif index == len(path_track_ids) - 1:
                segments.append(
                    TrackOccupancySegment(
                        track_id=track_id,
                        rear_offset_ft=0.0,
                        front_offset_ft=extent.front_position.offset_ft,
                    )
                )
            else:
                segments.append(
                    TrackOccupancySegment(
                        track_id=track_id,
                        rear_offset_ft=0.0,
                        front_offset_ft=track.length_ft,
                    )
                )

        return tuple(segments)

    def _connected_end_between_tracks(
        self,
        *,
        source_track: Track,
        destination_track: Track,
    ) -> TrackEnd:
        """
        Determine which endpoint of source_track is currently connected to
        destination_track in topology.

        This supports normal fixed junctions as well as dynamic connections
        exposed by TurntableConnection.
        """
        endpoint_a = TrackEndpoint(track=source_track, end=TrackEnd.A)
        endpoint_b = TrackEndpoint(track=source_track, end=TrackEnd.B)

        for endpoint in (endpoint_a, endpoint_b):
            options = self._movement_service.movement_options_from_endpoint(endpoint)

            for option in options:
                if option.destination_track_id == destination_track.track_id:
                    return endpoint.end

        raise ValueError(
            "Could not determine connected endpoint between tracks "
            f"{source_track.track_id} and {destination_track.track_id}."
        )

    def _position_in_range(self, position: NetworkPosition, track: Track) -> bool:
        return 0 <= position.offset_ft <= track.length_ft

    def _safe_get_track(self, track_id: UUID) -> Track | None:
        try:
            return self._network.get_track(track_id)
        except ValueError:
            return None

    def _get_track(self, track_id: UUID) -> Track:
        return self._network.get_track(track_id)
