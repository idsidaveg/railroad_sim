import math
from dataclasses import dataclass
from typing import Optional

from railroad_sim.presentation.gui.tkinter.canvas.elements.straight_track import (
    StraightTrackElement,
)


@dataclass
class CanvasEndpoint:
    x: float
    y: float
    owner: StraightTrackElement
    endpoint_index: int  # 1 or 2


@dataclass
class SnapCandidate:
    x: float
    y: float
    is_valid: bool
    endpoint: CanvasEndpoint


SNAP_TOLERANCE = 12.0
COINCIDENT_ENDPOINT_TOLERANCE = 1.0


def distance(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.hypot(x2 - x1, y2 - y1)


def extract_endpoints(track: StraightTrackElement) -> list[CanvasEndpoint]:
    return [
        CanvasEndpoint(track.x1, track.y1, track, 1),
        CanvasEndpoint(track.x2, track.y2, track, 2),
    ]


def endpoint_has_existing_connection(
    target_endpoint: CanvasEndpoint,
    tracks: list[StraightTrackElement],
    ignore_track: Optional[StraightTrackElement] = None,
) -> bool:
    """
    First-pass invalid rule:
    treat an endpoint as already connected if another committed endpoint
    from a different track already occupies the same coordinates.

    The actively dragged track must be ignored, otherwise a live drag preview
    makes the target endpoint appear falsely occupied.
    """
    for track in tracks:
        if track is target_endpoint.owner:
            continue

        if ignore_track is not None and track is ignore_track:
            continue

        for endpoint in extract_endpoints(track):
            if (
                distance(
                    target_endpoint.x,
                    target_endpoint.y,
                    endpoint.x,
                    endpoint.y,
                )
                <= COINCIDENT_ENDPOINT_TOLERANCE
            ):
                return True

    return False


def find_nearest_endpoint(
    x: float,
    y: float,
    tracks: list[StraightTrackElement],
    ignore_track: Optional[StraightTrackElement] = None,
) -> Optional[SnapCandidate]:
    best: Optional[CanvasEndpoint] = None
    best_dist = SNAP_TOLERANCE

    for track in tracks:
        if track is ignore_track:
            continue

        for ep in extract_endpoints(track):
            d = distance(x, y, ep.x, ep.y)
            if d <= best_dist:
                best = ep
                best_dist = d

    if best is None:
        return None

    is_valid = not endpoint_has_existing_connection(
        best,
        tracks,
        ignore_track=ignore_track,
    )

    return SnapCandidate(
        x=best.x,
        y=best.y,
        is_valid=is_valid,
        endpoint=best,
    )
