from __future__ import annotations

from railroad_sim.domain.yard.roundhouse import Roundhouse
from railroad_sim.domain.yard.turntable import Turntable


class RoundhouseValidator:
    """
    Validates consistency between a Roundhouse and its Turntable.

    Rules enforced (v1):
    - Roundhouse must reference the correct turntable
    - All roundhouse stall tracks must exist on the turntable
    """

    @staticmethod
    def validate(roundhouse: Roundhouse, turntable: Turntable) -> None:
        RoundhouseValidator._validate_turntable_reference(roundhouse, turntable)
        RoundhouseValidator._validate_stall_tracks(roundhouse, turntable)

    # -------------------------
    # Internal validation
    # -------------------------

    @staticmethod
    def _validate_turntable_reference(
        roundhouse: Roundhouse,
        turntable: Turntable,
    ) -> None:
        if roundhouse.turntable_id != turntable.turntable_id:
            raise ValueError(
                f"Roundhouse '{roundhouse.name}' references turntable "
                f"{roundhouse.turntable_id}, but received turntable "
                f"{turntable.turntable_id}."
            )

    @staticmethod
    def _validate_stall_tracks(
        roundhouse: Roundhouse,
        turntable: Turntable,
    ) -> None:
        turntable_stalls = set(turntable.stall_track_ids)

        for track_id in roundhouse.stall_track_ids:
            if track_id not in turntable_stalls:
                raise ValueError(
                    f"Roundhouse '{roundhouse.name}' has stall track {track_id} "
                    f"which is not registered on turntable '{turntable.name}'."
                )
