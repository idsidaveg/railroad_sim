from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass
class StraightTrackElement:
    id: str
    x1: float
    y1: float
    x2: float
    y2: float

    @classmethod
    def create(
        cls, x1: float, y1: float, x2: float, y2: float
    ) -> "StraightTrackElement":
        return cls(
            id=str(uuid.uuid4()),
            x1=x1,
            y1=y1,
            x2=x2,
            y2=y2,
        )

    def move(self, dx: float, dy: float) -> None:
        self.x1 += dx
        self.y1 += dy
        self.x2 += dx
        self.y2 += dy

    def set_endpoint_2(self, x: float, y: float) -> None:
        self.x2 = x
        self.y2 = y
