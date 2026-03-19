from __future__ import annotations

from dataclasses import dataclass

from railroad_sim.domain.network.footprint_service import FootprintService
from railroad_sim.domain.network.position_types import ConsistExtent
from railroad_sim.domain.network.turnout_occupancy import TurnoutFoulingState


@dataclass(frozen=True)
class TurnoutWindow:
    turnout_name: str
    track_key: str
    start_ft: float
    end_ft: float


def ranges_overlap(
    a_start: float,
    a_end: float,
    b_start: float,
    b_end: float,
) -> bool:
    return max(a_start, b_start) < min(a_end, b_end)


class TurnoutEvaluator:
    """
    Evaluates turnout fouling for a consist extent against defined turnout windows.

    This works from footprint segments, so it supports:
    - same-track extents
    - multi-track extents
    - turnout windows spanning multiple tracks
    """

    def __init__(
        self,
        *,
        footprint_service: FootprintService,
        track_key_by_id: dict[str, str],
    ) -> None:
        self._footprint_service = footprint_service
        self._track_key_by_id = track_key_by_id

    def evaluate_extent_against_turnout(
        self,
        *,
        extent: ConsistExtent,
        turnout_name: str,
        turnout_windows: list[TurnoutWindow],
    ) -> TurnoutFoulingState:
        footprint = self._footprint_service.footprint_for_extent(extent)

        is_fouled = False

        for segment in footprint.segments:
            segment_track_key = self._track_key_by_id[str(segment.track_id)]

            for window in turnout_windows:
                if segment_track_key != window.track_key:
                    continue

                if ranges_overlap(
                    segment.rear_offset_ft,
                    segment.front_offset_ft,
                    window.start_ft,
                    window.end_ft,
                ):
                    is_fouled = True
                    break

            if is_fouled:
                break

        return TurnoutFoulingState(
            turnout_name=turnout_name,
            is_fouled=is_fouled,
        )

    def evaluate_extent(
        self,
        *,
        extent: ConsistExtent,
        turnout_windows_by_key: dict[str, list[TurnoutWindow]],
    ) -> dict[str, TurnoutFoulingState]:
        results: dict[str, TurnoutFoulingState] = {}

        for _, windows in turnout_windows_by_key.items():
            if not windows:
                continue

            turnout_name = windows[0].turnout_name
            results[turnout_name] = self.evaluate_extent_against_turnout(
                extent=extent,
                turnout_name=turnout_name,
                turnout_windows=windows,
            )

        return results
