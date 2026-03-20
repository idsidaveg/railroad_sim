from __future__ import annotations

from railroad_sim.domain.junction import Junction
from railroad_sim.domain.network.rail_network import RailNetwork
from railroad_sim.domain.network.yard_throat_topology import YardThroatTopology
from railroad_sim.domain.track import Track


def build_single_ladder_throat(
    *,
    mainline_track: Track,
    lead_track: Track,
    entry_junction: Junction,
    ladder_junctions: tuple[Junction, ...],
    ad_tracks: tuple[Track, ...] = (),
    yard_tracks: tuple[Track, ...] = (),
    auxiliary_tracks: tuple[Track, ...] = (),
) -> YardThroatTopology:
    """
    Assemble a first-version yard throat topology from prebuilt domain objects.

    Design intent:
    - caller owns Track/Junction creation
    - builder groups those objects into a consistent throat structure
    - no hidden infrastructure is created here
    - no movement or turnout logic is performed here

    V1 scope:
    - exactly one mainline track
    - exactly one lead track
    - exactly one entry junction
    - one or more ladder junctions
    - optional A/D, yard, and auxiliary tracks
    """

    if not ladder_junctions:
        raise ValueError("ladder_junctions must contain at least one junction.")

    _validate_distinct_track_roles(
        mainline_track=mainline_track,
        lead_track=lead_track,
    )

    all_tracks = _build_all_tracks(
        mainline_track=mainline_track,
        lead_track=lead_track,
        ad_tracks=ad_tracks,
        yard_tracks=yard_tracks,
        auxiliary_tracks=auxiliary_tracks,
    )
    _validate_unique_tracks(all_tracks)

    all_junctions = (entry_junction, *ladder_junctions)
    _validate_unique_junctions(all_junctions)

    return YardThroatTopology(
        mainline_track=mainline_track,
        lead_track=lead_track,
        entry_junction=entry_junction,
        ladder_junctions=ladder_junctions,
        ad_tracks=ad_tracks,
        yard_tracks=yard_tracks,
        auxiliary_tracks=auxiliary_tracks,
        all_tracks=all_tracks,
        all_junctions=all_junctions,
    )


def register_yard_throat(
    *,
    network: RailNetwork,
    topology: YardThroatTopology,
) -> None:
    """
    Register all tracks and junctions from a throat topology into a RailNetwork.

    The network already enforces that any Junction added must reference tracks
    that are already registered, so tracks are added first, then junctions.
    """

    for track in topology.all_tracks:
        if track.track_id not in network.tracks:
            network.add_track(track)

    for junction in topology.all_junctions:
        if junction.junction_id not in network.junctions:
            network.add_junction(junction)


def _build_all_tracks(
    *,
    mainline_track: Track,
    lead_track: Track,
    ad_tracks: tuple[Track, ...],
    yard_tracks: tuple[Track, ...],
    auxiliary_tracks: tuple[Track, ...],
) -> tuple[Track, ...]:
    return (
        mainline_track,
        lead_track,
        *ad_tracks,
        *yard_tracks,
        *auxiliary_tracks,
    )


def _validate_distinct_track_roles(
    *,
    mainline_track: Track,
    lead_track: Track,
) -> None:
    if mainline_track.track_id == lead_track.track_id:
        raise ValueError("mainline_track and lead_track must be different tracks.")


def _validate_unique_tracks(tracks: tuple[Track, ...]) -> None:
    seen: set[str] = set()

    for track in tracks:
        track_id = str(track.track_id)
        if track_id in seen:
            raise ValueError(
                f"Duplicate track detected in yard throat: '{track.name}'."
            )
        seen.add(track_id)


def _validate_unique_junctions(junctions: tuple[Junction, ...]) -> None:
    seen: set[str] = set()

    for junction in junctions:
        junction_id = str(junction.junction_id)
        if junction_id in seen:
            raise ValueError(
                f"Duplicate junction detected in yard throat: '{junction.name}'."
            )
        seen.add(junction_id)
