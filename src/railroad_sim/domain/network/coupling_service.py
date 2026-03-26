from __future__ import annotations

from railroad_sim.domain.consist import Consist
from railroad_sim.domain.enums import TravelDirection
from railroad_sim.domain.network.consist_movement_types import MovementExecutionResult
from railroad_sim.domain.network.coupling_types import CouplingOutcome, CouplingResult
from railroad_sim.domain.network.relative_speed import compute_closing_speed_mph
from railroad_sim.domain.network.topology_movement_enums import MovementBlockReason


class CouplingService:
    """
    Post-movement coupling orchestration.

    This service does not implement low-level coupler mechanics itself.
    It uses the existing Consist.merge_with(...) behavior once a valid
    contact event has been identified by the movement layer.
    """

    def try_couple(
        self,
        *,
        movement_result: MovementExecutionResult,
        other_consists: tuple[Consist, ...],
        closing_speed_mph: float | None = None,
        moved_speed_mph: float | None = None,
        other_speed_mph: float | None = None,
        other_direction: TravelDirection | None = None,
        max_coupling_speed_mph: float = 4.0,
    ) -> CouplingResult:
        moved_consist = movement_result.new_extent.consist

        if max_coupling_speed_mph < 0:
            raise ValueError("max_coupling_speed_mph must be >= 0")

        if not movement_result.contact_occurred:
            return CouplingResult(
                outcome=CouplingOutcome.NO_CONTACT,
                moved_consist_id=moved_consist.consist_id,
                other_consist_id=None,
                merged_consist=None,
            )

        if movement_result.stop_reason is not MovementBlockReason.CONTACT:
            return CouplingResult(
                outcome=CouplingOutcome.CONTACT_STOP_REQUIRED,
                moved_consist_id=moved_consist.consist_id,
                other_consist_id=movement_result.contact_with_consist_id,
                merged_consist=None,
            )

        if closing_speed_mph is None:
            if moved_speed_mph is None:
                raise ValueError(
                    "moved_speed_mph is required when closing_speed_mph is not provided"
                )

            if other_speed_mph is None:
                raise ValueError(
                    "other_speed_mph is required when closing_speed_mph is not provided"
                )

            if other_direction is None:
                raise ValueError(
                    "other_direction is required when closing_speed_mph is not provided"
                )

            closing_speed_mph = compute_closing_speed_mph(
                moved_speed_mph=moved_speed_mph,
                moved_direction=movement_result.new_extent.travel_direction,
                other_speed_mph=other_speed_mph,
                other_direction=other_direction,
            )

        if closing_speed_mph < 0:
            raise ValueError("closing_speed_mph must be >= 0")

        if closing_speed_mph > max_coupling_speed_mph:
            return CouplingResult(
                outcome=CouplingOutcome.TOO_FAST_TO_COUPLE,
                moved_consist_id=moved_consist.consist_id,
                other_consist_id=movement_result.contact_with_consist_id,
                merged_consist=None,
            )

        other_consist_id = movement_result.contact_with_consist_id
        if other_consist_id is None:
            return CouplingResult(
                outcome=CouplingOutcome.INVALID_CONTACT,
                moved_consist_id=moved_consist.consist_id,
                other_consist_id=None,
                merged_consist=None,
            )

        other_consist = next(
            (
                consist
                for consist in other_consists
                if consist.consist_id == other_consist_id
            ),
            None,
        )
        if other_consist is None:
            return CouplingResult(
                outcome=CouplingOutcome.OTHER_CONSIST_NOT_FOUND,
                moved_consist_id=moved_consist.consist_id,
                other_consist_id=other_consist_id,
                merged_consist=None,
            )

        moved_coupler, other_coupler = self._select_contact_couplers(
            movement_result=movement_result,
            other_consist=other_consist,
        )

        merged = moved_consist.merge_with(
            other_consist,
            moved_coupler,
            other_coupler,
        )

        return CouplingResult(
            outcome=CouplingOutcome.COUPLED,
            moved_consist_id=moved_consist.consist_id,
            other_consist_id=other_consist.consist_id,
            merged_consist=merged,
        )

    def _select_contact_couplers(
        self,
        *,
        movement_result: MovementExecutionResult,
        other_consist: Consist,
    ):
        """
        Select the exposed end couplers that should be joined for a contact event.

        v1 assumption:
        - FORWARD contact means the moved consist contacted with its front end
        - REVERSE contact means the moved consist contacted with its rear end
        - the contacted consist presents the opposite exposed end
        """

        moved_consist = movement_result.new_extent.consist
        moved_extent = movement_result.new_extent

        moved_front_coupler = moved_consist.head_end.front_coupler
        moved_rear_coupler = moved_consist.rear_end.rear_coupler

        other_front_coupler = other_consist.head_end.front_coupler
        other_rear_coupler = other_consist.rear_end.rear_coupler

        if moved_extent.travel_direction is TravelDirection.TOWARD_B:
            return moved_rear_coupler, other_front_coupler

        if moved_extent.travel_direction is TravelDirection.TOWARD_A:
            return moved_front_coupler, other_rear_coupler

        raise ValueError(
            "Cannot select coupling couplers for a stationary moved consist."
        )
