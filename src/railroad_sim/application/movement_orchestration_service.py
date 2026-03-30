from __future__ import annotations

from railroad_sim.application.movement_orchestration_result import (
    MovementOrchestrationResult,
)
from railroad_sim.application.post_contact_context import PostContactContext
from railroad_sim.domain.network.consist_movement_service import (
    ConsistMovementService,
)
from railroad_sim.domain.network.consist_movement_types import MoveCommand
from railroad_sim.domain.network.post_contact_resolution_service import (
    PostContactResolutionService,
)


class MovementOrchestrationService:
    def __init__(
        self,
        *,
        movement_service: ConsistMovementService,
        post_contact_service: PostContactResolutionService | None = None,
    ) -> None:
        self._movement = movement_service
        self._post_contact = post_contact_service or PostContactResolutionService()

    def execute_move(
        self,
        *,
        extent,
        command: MoveCommand,
        distance_ft: float,
        turnout_windows_by_key: dict,
        active_footprints=(),
        post_contact_context: PostContactContext | None = None,
    ) -> MovementOrchestrationResult:

        # 1. Execute movement
        movement_result = self._movement.move_extent(
            extent=extent,
            command=command,
            distance_ft=distance_ft,
            turnout_windows_by_key=turnout_windows_by_key,
            active_footprints=active_footprints,
        )

        # 2. Default: no post-contact result
        post_contact_result = None

        # 3. Only resolve if:
        #    - contact occurred
        #    - AND context is provided
        if movement_result.contact_occurred and post_contact_context is not None:
            ctx = post_contact_context

            post_contact_result = self._post_contact.resolve(
                movement_result=movement_result,
                other_consists=ctx.other_consists,
                moved_speed_mph=ctx.moved_speed_mph,
                other_speed_mph=ctx.other_speed_mph,
                other_direction=ctx.other_direction,
                moved_mass_lb=ctx.moved_mass_lb,
                other_mass_lb=ctx.other_mass_lb,
                moved_car_count=ctx.moved_car_count,
                other_car_count=ctx.other_car_count,
                moved_contact_from_front=ctx.moved_contact_from_front,
                other_contact_from_front=ctx.other_contact_from_front,
                max_coupling_speed_mph=ctx.max_coupling_speed_mph,
                hard_collision_speed_mph=ctx.hard_collision_speed_mph,
            )

        # 4. Return unified result
        return MovementOrchestrationResult(
            movement_result=movement_result,
            post_contact_result=post_contact_result,
        )
