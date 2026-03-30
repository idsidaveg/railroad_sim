from __future__ import annotations

from dataclasses import dataclass

from railroad_sim.domain.consist import Consist
from railroad_sim.domain.enums import TravelDirection


@dataclass(frozen=True, slots=True)
class PostContactContext:
    other_consists: tuple[Consist, ...]

    moved_speed_mph: float
    other_speed_mph: float
    other_direction: TravelDirection

    moved_mass_lb: float
    other_mass_lb: float

    moved_car_count: int | None = None
    other_car_count: int | None = None

    moved_contact_from_front: bool = True
    other_contact_from_front: bool = False

    max_coupling_speed_mph: float = 4.0
    hard_collision_speed_mph: float = 12.0
