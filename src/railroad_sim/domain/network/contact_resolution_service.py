from __future__ import annotations

from railroad_sim.domain.network.contact_resolution_types import (
    ContactRelationship,
    FootprintInteraction,
)
from railroad_sim.domain.network.position_types import ConsistFootprint


class ContactResolutionService:
    """
    Read-only classifier for spatial interaction between one moving footprint
    and other active footprints.

    v1 behavior:
    - CLEAR: no overlap and no exact boundary contact
    - CONTACT: exact boundary touch only
    - OVERLAP: illegal shared occupied space on the same track
    """

    def classify_against_active_footprints(
        self,
        *,
        moving_footprint: ConsistFootprint,
        active_footprints: tuple[ConsistFootprint, ...],
    ) -> FootprintInteraction:
        for other in active_footprints:
            if other.consist is moving_footprint.consist:
                continue

            interaction = self._classify_pair(
                moving_footprint=moving_footprint,
                other_footprint=other,
            )

            if interaction.relationship is not ContactRelationship.CLEAR:
                return interaction

        return FootprintInteraction(
            relationship=ContactRelationship.CLEAR,
        )

    def _classify_pair(
        self,
        *,
        moving_footprint: ConsistFootprint,
        other_footprint: ConsistFootprint,
    ) -> FootprintInteraction:
        for moving_segment in moving_footprint.segments:
            for other_segment in other_footprint.segments:
                if moving_segment.track_id != other_segment.track_id:
                    continue

                if (
                    moving_segment.rear_offset_ft < other_segment.front_offset_ft
                    and other_segment.rear_offset_ft < moving_segment.front_offset_ft
                ):
                    return FootprintInteraction(
                        relationship=ContactRelationship.OVERLAP,
                        other_consist_id=other_footprint.consist.consist_id,
                        shared_track_id=moving_segment.track_id,
                    )

                if (
                    moving_segment.front_offset_ft == other_segment.rear_offset_ft
                    or moving_segment.rear_offset_ft == other_segment.front_offset_ft
                ):
                    return FootprintInteraction(
                        relationship=ContactRelationship.CONTACT,
                        other_consist_id=other_footprint.consist.consist_id,
                        shared_track_id=moving_segment.track_id,
                    )

        return FootprintInteraction(
            relationship=ContactRelationship.CLEAR,
            other_consist_id=other_footprint.consist.consist_id,
        )
