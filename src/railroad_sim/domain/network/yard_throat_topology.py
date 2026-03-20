from __future__ import annotations

from dataclasses import dataclass

from railroad_sim.domain.junction import Junction
from railroad_sim.domain.track import Track


@dataclass(frozen=True, slots=True)
class YardThroatTopology:
    """
    Structured result returned by yard-throat topology builders.

    This object is intentionally lightweight. It does not perform movement,
    routing, or occupancy evaluation. It simply groups together the core
    tracks and junctions that make up a yard-throat pattern so they can be
    consumed easily by:

    - tests
    - topology builder helpers
    - future yard assembly code
    - later CTC / visualization layers
    """

    mainline_track: Track
    lead_track: Track

    entry_junction: Junction
    ladder_junctions: tuple[Junction, ...]

    ad_tracks: tuple[Track, ...]
    yard_tracks: tuple[Track, ...]
    auxiliary_tracks: tuple[Track, ...]

    all_tracks: tuple[Track, ...]
    all_junctions: tuple[Junction, ...]
