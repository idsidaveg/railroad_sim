from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from railroad_sim.domain.enums import JunctionType, TrackEnd
from railroad_sim.domain.junction import Junction, JunctionRoute, TrackEndpoint
from railroad_sim.domain.track import Track
from railroad_sim.domain.yard.turntable import Turntable


@dataclass(slots=True)
class TurntableConnection:
    """
    Builds a temporary junction representing the turntable's current alignment.

    V1 rules:
    - the turntable itself is not a Junction
    - the bridge is a real Track
    - exactly one non-bridge track may be aligned at a time
    - if no alignment exists, there is no active junction

    Endpoint convention for V1:
    - bridge TrackEnd.A faces the approach side
    - bridge TrackEnd.B faces the radial side (stalls / service tracks)
    - aligned approach uses TrackEnd.A on the external track
    - aligned stall/service uses TrackEnd.A on the external track

    This keeps the first implementation deterministic without trying to model
    full turntable geometry yet.
    """

    turntable: Turntable
    bridge_track: Track
    connected_tracks_by_id: Mapping[object, Track]

    def build_active_junction(self) -> Junction | None:
        """
        Return a Junction representing the current turntable alignment.

        Returns:
            Junction | None:
                - None if the turntable has no current alignment
                - a Junction connecting the bridge to the aligned external track
        """
        self._validate_bridge_track()

        aligned_track_id = self.turntable.aligned_track_id
        if aligned_track_id is None:
            return None

        aligned_track = self.connected_tracks_by_id.get(aligned_track_id)
        if aligned_track is None:
            raise ValueError(
                f"Aligned track id {aligned_track_id} was not provided for "
                f"turntable '{self.turntable.name}'."
            )

        self._validate_aligned_track(aligned_track)

        bridge_endpoint = self._bridge_endpoint_for(aligned_track.track_id)
        external_endpoint = TrackEndpoint(
            track=aligned_track,
            end=TrackEnd.A,
        )

        route = JunctionRoute(
            from_endpoint=bridge_endpoint,
            to_endpoint=external_endpoint,
        )

        return Junction(
            name=f"{self.turntable.name}_active_connection",
            junction_type=JunctionType.TURNOUT,
            endpoints={bridge_endpoint, external_endpoint},
            routes={route},
            aligned_routes={route},
        )

    def _validate_bridge_track(self) -> None:
        if self.bridge_track.track_id != self.turntable.bridge_track_id:
            raise ValueError(
                f"Bridge track '{self.bridge_track.name}' does not match "
                f"turntable '{self.turntable.name}' bridge_track_id."
            )

    def _validate_aligned_track(self, aligned_track: Track) -> None:
        if aligned_track.track_id == self.turntable.bridge_track_id:
            raise ValueError(
                f"Turntable '{self.turntable.name}' cannot align the bridge to itself."
            )

        if aligned_track.track_id not in self.turntable.connected_track_ids:
            raise ValueError(
                f"Track '{aligned_track.name}' is not a connected track for "
                f"turntable '{self.turntable.name}'."
            )

        if aligned_track.track_id != self.turntable.aligned_track_id:
            raise ValueError(
                f"Connected track lookup returned track '{aligned_track.name}' with "
                "a track_id that does not match the current turntable alignment."
            )

    def _bridge_endpoint_for(self, aligned_track_id: object) -> TrackEndpoint:
        if aligned_track_id == self.turntable.approach_track_id:
            return TrackEndpoint(
                track=self.bridge_track,
                end=TrackEnd.A,
            )

        return TrackEndpoint(
            track=self.bridge_track,
            end=TrackEnd.B,
        )
