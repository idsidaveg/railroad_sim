from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from uuid import UUID


class ContactRelationship(str, Enum):
    """
    Spatial relationship between a moving footprint and another active footprint.

    CLEAR:
        No shared occupied space and no exact boundary contact.

    CONTACT:
        Exact boundary touch only. This is the future hook for controlled
        coupling/contact handling.

    OVERLAP:
        Illegal shared occupied space on the same track.
    """

    CLEAR = "clear"
    CONTACT = "contact"
    OVERLAP = "overlap"


@dataclass(frozen=True, slots=True)
class FootprintInteraction:
    """
    Result of comparing one moving footprint against another active footprint.
    """

    relationship: ContactRelationship
    other_consist_id: UUID | None = None
    shared_track_id: UUID | None = None
