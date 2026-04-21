from __future__ import annotations

import math
from typing import Protocol

# ---------------------------------------------------------------------
# Element protocols
# ---------------------------------------------------------------------


class StraightTrackRotatable(Protocol):
    x1: float
    y1: float
    x2: float
    y2: float


class TurnoutRotatable(Protocol):
    x: float
    y: float
    angle_degrees: float
    diverge_angle_degrees: float
    length: float
    diverge_length: float
    is_left_hand: bool


# ---------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------


def normalize_angle_degrees(angle_degrees: float) -> float:
    """
    Normalize an angle to the range [-180, 180).
    """
    return (angle_degrees + 180.0) % 360.0 - 180.0


def rotate_point_about_pivot(
    x: float,
    y: float,
    pivot_x: float,
    pivot_y: float,
    delta_degrees: float,
) -> tuple[float, float]:
    """
    Rotate a point around a pivot by delta_degrees.
    Positive values are standard mathematical CCW rotation.
    """
    radians_ = math.radians(delta_degrees)
    cos_a = math.cos(radians_)
    sin_a = math.sin(radians_)

    dx = x - pivot_x
    dy = y - pivot_y

    rotated_x = pivot_x + (dx * cos_a) - (dy * sin_a)
    rotated_y = pivot_y + (dx * sin_a) + (dy * cos_a)
    return rotated_x, rotated_y


# ---------------------------------------------------------------------
# Straight track helpers
# ---------------------------------------------------------------------


def get_straight_track_midpoint(
    track: StraightTrackRotatable,
) -> tuple[float, float]:
    return ((track.x1 + track.x2) / 2.0, (track.y1 + track.y2) / 2.0)


def get_straight_track_length(
    track: StraightTrackRotatable,
) -> float:
    return math.hypot(track.x2 - track.x1, track.y2 - track.y1)


def get_straight_track_angle_degrees(
    track: StraightTrackRotatable,
) -> float:
    return math.degrees(math.atan2(track.y2 - track.y1, track.x2 - track.x1))


def rotate_straight_track(
    track: StraightTrackRotatable,
    delta_degrees: float,
) -> None:
    """
    Rotate a straight track about its midpoint.

    Important:
    - preserves exact current length
    - recomputes endpoints from midpoint + length + new angle
    - does not depend on any canvas/prototype-only sync methods
    """
    cx, cy = get_straight_track_midpoint(track)
    length = get_straight_track_length(track)

    if length <= 1e-9:
        return

    new_angle_degrees = normalize_angle_degrees(
        get_straight_track_angle_degrees(track) + delta_degrees
    )
    new_angle_radians = math.radians(new_angle_degrees)

    half_length = length / 2.0
    half_dx = math.cos(new_angle_radians) * half_length
    half_dy = math.sin(new_angle_radians) * half_length

    track.x1 = cx - half_dx
    track.y1 = cy - half_dy
    track.x2 = cx + half_dx
    track.y2 = cy + half_dy


# ---------------------------------------------------------------------
# Turnout helpers
# ---------------------------------------------------------------------


def rotate_turnout(
    turnout: TurnoutRotatable,
    delta_degrees: float,
) -> None:
    """
    Rotate a turnout about its trunk anchor/origin.

    Important:
    - turnout.x / turnout.y remain fixed
    - only the base heading changes
    - turnout geometry should be redrawn by the canvas from canonical fields
    - deliberately does NOT preserve visual center
    """
    turnout.angle_degrees = normalize_angle_degrees(
        turnout.angle_degrees + delta_degrees
    )


# ---------------------------------------------------------------------
# Optional future helpers for group rotation
# ---------------------------------------------------------------------


def rotate_straight_track_about_pivot(
    track: StraightTrackRotatable,
    pivot_x: float,
    pivot_y: float,
    delta_degrees: float,
) -> None:
    """
    Rotate an entire straight track about an arbitrary group pivot.

    This is for later group rotation work, not required for the
    first single-object rotation pass.
    """
    new_x1, new_y1 = rotate_point_about_pivot(
        track.x1,
        track.y1,
        pivot_x,
        pivot_y,
        delta_degrees,
    )
    new_x2, new_y2 = rotate_point_about_pivot(
        track.x2,
        track.y2,
        pivot_x,
        pivot_y,
        delta_degrees,
    )

    track.x1 = new_x1
    track.y1 = new_y1
    track.x2 = new_x2
    track.y2 = new_y2


def rotate_turnout_about_pivot(
    turnout: TurnoutRotatable,
    pivot_x: float,
    pivot_y: float,
    delta_degrees: float,
) -> None:
    """
    Rotate an entire turnout about an arbitrary group pivot.

    This moves the turnout anchor/origin and rotates the turnout heading.
    Useful later for group rotation.
    """
    new_x, new_y = rotate_point_about_pivot(
        turnout.x,
        turnout.y,
        pivot_x,
        pivot_y,
        delta_degrees,
    )

    turnout.x = new_x
    turnout.y = new_y
    turnout.angle_degrees = normalize_angle_degrees(
        turnout.angle_degrees + delta_degrees
    )
