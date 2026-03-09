from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from railroad_sim.domain.enums import (
    EventSeverity,
    RollingStockEventType,
    TrainEventType,
)


@dataclass(frozen=True, slots=True)
class RollingStockEvent:
    """
    Immutable event record for a single piece of rolling stock.

    sequence:
        Monotonic event number within the owning RollingStock history.

    event_type:
        Type of lifecycle / operational event recorded for the asset.

    occurred_at:
        Timestamp when the event occurred. Intended to be timezone-aware.

    details:
        Optional human-readable narrative describing the event.

    location:
        Optional railroad/location context for the event.

    related_train_id:
        Optional operational train reference when the event occurred
        in the context of a train assignment or movement.

    severity:
        Level of an orchestrated event
    """

    sequence: int
    event_type: RollingStockEventType
    occurred_at: datetime
    details: str | None = None
    location: str | None = None
    related_train_id: str | None = None
    severity: EventSeverity = EventSeverity.INFO


@dataclass(frozen=True, slots=True)
class TrainEvent:
    """
    Immutable event record for a train.

    sequence:
        Monotonic event number within the owning Train history.

    event_type:
        Type of operational event affecting the train.

    occurred_at:
        Timestamp when the event occurred.

    details:
        Optional narrative describing the event.

    location:
        Optional railroad/location context.

    related_consist_id:
        Optional consist reference involved in the event.

    related_asset_id:
        Optional rolling stock asset involved in the event.

    severity:
        Level of an orchestrated event
    """

    sequence: int
    event_type: TrainEventType
    occurred_at: datetime
    details: str | None = None
    location: str | None = None
    related_consist_id: str | None = None
    related_asset_id: str | None = None
    severity: EventSeverity = EventSeverity.INFO
