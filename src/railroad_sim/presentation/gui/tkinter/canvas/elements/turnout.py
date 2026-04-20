from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass
class TurnoutElement:
    id: str
    x: float
    y: float
    angle_degrees: float
    length: float
    diverge_length: float
    diverge_angle_degrees: float
    is_left_hand: bool

    @classmethod
    def create(
        cls,
        x: float,
        y: float,
        *,
        angle_degrees: float = 0.0,
        length: float = 120.0,
        diverge_length: float = 75.0,
        diverge_angle_degrees: float = 12.0,
        is_left_hand: bool = True,
    ) -> "TurnoutElement":
        return cls(
            id=str(uuid.uuid4()),
            x=x,
            y=y,
            angle_degrees=angle_degrees,
            length=length,
            diverge_length=diverge_length,
            diverge_angle_degrees=diverge_angle_degrees,
            is_left_hand=is_left_hand,
        )

    def move(self, dx: float, dy: float) -> None:
        self.x += dx
        self.y += dy
