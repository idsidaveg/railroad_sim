from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class GuideModel:
    """
    Presentation-layer guide storage for ruler-created alignment guides.

    Guides are stored in world coordinates:
    - vertical_guides store X positions
    - horizontal_guides store Y positions
    """

    max_vertical_guides: int = 5
    max_horizontal_guides: int = 5
    vertical_guides: list[float] = field(default_factory=list)
    horizontal_guides: list[float] = field(default_factory=list)

    def can_add_vertical(self) -> bool:
        return len(self.vertical_guides) < self.max_vertical_guides

    def can_add_horizontal(self) -> bool:
        return len(self.horizontal_guides) < self.max_horizontal_guides

    def add_vertical(self, x: float) -> bool:
        if not self.can_add_vertical():
            return False
        self.vertical_guides.append(x)
        return True

    def add_horizontal(self, y: float) -> bool:
        if not self.can_add_horizontal():
            return False
        self.horizontal_guides.append(y)
        return True

    def move_vertical(self, index: int, x: float) -> bool:
        if index < 0 or index >= len(self.vertical_guides):
            return False
        self.vertical_guides[index] = x
        return True

    def move_horizontal(self, index: int, y: float) -> bool:
        if index < 0 or index >= len(self.horizontal_guides):
            return False
        self.horizontal_guides[index] = y
        return True

    def find_nearest_vertical(self, x: float, tolerance: float) -> int | None:
        nearest_index: int | None = None
        nearest_distance = tolerance

        for index, guide_x in enumerate(self.vertical_guides):
            distance = abs(guide_x - x)
            if distance <= nearest_distance:
                nearest_distance = distance
                nearest_index = index

        return nearest_index

    def find_nearest_horizontal(self, y: float, tolerance: float) -> int | None:
        nearest_index: int | None = None
        nearest_distance = tolerance

        for index, guide_y in enumerate(self.horizontal_guides):
            distance = abs(guide_y - y)
            if distance <= nearest_distance:
                nearest_distance = distance
                nearest_index = index

        return nearest_index

    def remove_vertical(self, index: int) -> bool:
        if index < 0 or index >= len(self.vertical_guides):
            return False
        del self.vertical_guides[index]
        return True

    def remove_horizontal(self, index: int) -> bool:
        if index < 0 or index >= len(self.horizontal_guides):
            return False
        del self.horizontal_guides[index]
        return True

    def clear_vertical(self) -> None:
        self.vertical_guides.clear()

    def clear_horizontal(self) -> None:
        self.horizontal_guides.clear()

    def clear(self) -> None:
        self.vertical_guides.clear()
        self.horizontal_guides.clear()
