from __future__ import annotations

from dataclasses import InitVar, dataclass, field
from datetime import datetime, timezone
from typing import Any

from railroad_sim.domain.consist import Consist
from railroad_sim.domain.enums import EventSeverity, TrainEventType, TrainStatus
from railroad_sim.domain.events import TrainEvent


@dataclass(slots=True)
class Train:
    """
    Operational domain object representing a train.

    A Train is not a physical consist. It is an operational wrapper
    around a consist and maintains its own event history.

    Train owns:
        - operational identity
        - current consist reference
        - status
        - append-only train event history

    Consist remains responsible for physical topology and equipment order.

    Normal construction represents creation of a brand new train.
    Use from_snapshot() to restore a previously saved train state
    without injecting a fake CREATED event.
    """

    train_id: str
    symbol: str
    created_at_value: InitVar[datetime | None] = None
    _suppress_creation_event: InitVar[bool] = False

    origin: str | None = None
    destination: str | None = None
    current_consist: Consist | None = None
    status: TrainStatus = TrainStatus.PLANNED

    _event_history: list[TrainEvent] = field(
        init=False,
        default_factory=list,
        repr=False,
    )

    def __post_init__(
        self,
        created_at_value: datetime | None,
        _suppress_creation_event: bool,
    ) -> None:
        self.train_id = self.train_id.strip()
        self.symbol = self.symbol.strip().upper()

        if not self.train_id:
            raise ValueError("train_id cannot be empty.")

        if not self.symbol:
            raise ValueError("symbol cannot be empty.")

        if _suppress_creation_event:
            return

        created_at = (
            created_at_value
            if created_at_value is not None
            else datetime.now(timezone.utc)
        )

        self._record_event(
            TrainEventType.CREATED,
            occurred_at=created_at,
            details="Train created.",
            related_consist_id=self._consist_reference(self.current_consist),
        )

        if self.current_consist is not None:
            self._record_event(
                TrainEventType.CONSIST_ASSIGNED,
                occurred_at=created_at,
                details="Initial consist assigned at train creation.",
                related_consist_id=self._consist_reference(self.current_consist),
            )

    @property
    def event_history(self) -> tuple[TrainEvent, ...]:
        """Read-only view of train event history."""
        return tuple(self._event_history)

    @property
    def has_consist(self) -> bool:
        """True when the train currently has a consist assigned."""
        return self.current_consist is not None

    def assign_consist(
        self,
        consist: Consist,
        *,
        occurred_at: datetime | None = None,
        details: str | None = None,
        location: str | None = None,
    ) -> None:
        """
        Assign a consist to this train.

        If the train already has a consist, this is treated as a consist change.
        """
        if self.current_consist is consist:
            return

        timestamp = (
            occurred_at if occurred_at is not None else datetime.now(timezone.utc)
        )

        if self.current_consist is not None:
            self._record_event(
                TrainEventType.CONSIST_CHANGED,
                occurred_at=timestamp,
                details=details or "Train consist changed.",
                location=location,
                related_consist_id=self._consist_reference(consist),
            )
        else:
            self._record_event(
                TrainEventType.CONSIST_ASSIGNED,
                occurred_at=timestamp,
                details=details or "Consist assigned to train.",
                location=location,
                related_consist_id=self._consist_reference(consist),
            )

        self.current_consist = consist

    def release_consist(
        self,
        *,
        occurred_at: datetime | None = None,
        details: str | None = None,
        location: str | None = None,
    ) -> None:
        """
        Release the currently assigned consist from this train.
        """
        if self.current_consist is None:
            return

        current_consist_id = self._consist_reference(self.current_consist)
        timestamp = (
            occurred_at if occurred_at is not None else datetime.now(timezone.utc)
        )

        self.current_consist = None

        self._record_event(
            TrainEventType.CONSIST_RELEASED,
            occurred_at=timestamp,
            details=details or "Consist released from train.",
            location=location,
            related_consist_id=current_consist_id,
        )

    def depart(
        self,
        *,
        occurred_at: datetime | None = None,
        details: str | None = None,
        location: str | None = None,
    ) -> None:
        """
        Mark the train as active and record a departure event.
        """
        self.status = TrainStatus.ACTIVE

        self._record_event(
            TrainEventType.DEPARTED,
            occurred_at=occurred_at,
            details=details or "Train departed.",
            location=location,
            related_consist_id=self._consist_reference(self.current_consist),
        )

    def arrive(
        self,
        *,
        occurred_at: datetime | None = None,
        details: str | None = None,
        location: str | None = None,
    ) -> None:
        """
        Record an arrival event.
        """
        self._record_event(
            TrainEventType.ARRIVED,
            occurred_at=occurred_at,
            details=details or "Train arrived.",
            location=location,
            related_consist_id=self._consist_reference(self.current_consist),
        )

    def hold(
        self,
        *,
        occurred_at: datetime | None = None,
        details: str | None = None,
        location: str | None = None,
    ) -> None:
        """
        Mark the train as held and record the event.
        """
        self.status = TrainStatus.HELD

        self._record_event(
            TrainEventType.HELD,
            occurred_at=occurred_at,
            details=details or "Train held.",
            location=location,
            related_consist_id=self._consist_reference(self.current_consist),
        )

    def complete(
        self,
        *,
        occurred_at: datetime | None = None,
        details: str | None = None,
        location: str | None = None,
    ) -> None:
        """
        Mark the train as completed and record the event.
        """
        self.status = TrainStatus.COMPLETED

        self._record_event(
            TrainEventType.COMPLETED,
            occurred_at=occurred_at,
            details=details or "Train completed.",
            location=location,
            related_consist_id=self._consist_reference(self.current_consist),
        )

    def cancel(
        self,
        *,
        occurred_at: datetime | None = None,
        details: str | None = None,
        location: str | None = None,
    ) -> None:
        """
        Mark the train as canceled and record the event.
        """
        self.status = TrainStatus.CANCELED

        self._record_event(
            TrainEventType.CANCELED,
            occurred_at=occurred_at,
            details=details or "Train canceled.",
            location=location,
            related_consist_id=self._consist_reference(self.current_consist),
        )

    def record_asset_event(
        self,
        event_type: TrainEventType,
        *,
        related_asset_id: str,
        occurred_at: datetime | None = None,
        details: str | None = None,
        location: str | None = None,
        severity: EventSeverity = EventSeverity.INFO,
    ) -> None:
        """
        Record a train event involving a specific rolling stock asset.

        Example uses:
            - CAR_ADDED
            - CAR_REMOVED
            - ROLLING_STOCK_DAMAGED
        """
        related_asset_id = related_asset_id.strip()
        if not related_asset_id:
            raise ValueError("related_asset_id cannot be empty.")

        self._record_event(
            event_type,
            occurred_at=occurred_at,
            details=details,
            location=location,
            related_consist_id=self._consist_reference(self.current_consist),
            related_asset_id=related_asset_id,
            severity=severity,
        )

    def to_snapshot(self) -> dict[str, Any]:
        """
        Serialize this train to a plain snapshot dictionary suitable
        for later JSON persistence.

        Object references are not serialized directly. The current
        consist is represented by its identifier when available.
        """
        return {
            "train_id": self.train_id,
            "symbol": self.symbol,
            "origin": self.origin,
            "destination": self.destination,
            "status": self.status.value,
            "current_consist_id": self._consist_reference(self.current_consist),
            "event_history": [
                {
                    "sequence": event.sequence,
                    "event_type": event.event_type.value,
                    "occurred_at": event.occurred_at.isoformat(),
                    "details": event.details,
                    "location": event.location,
                    "related_consist_id": event.related_consist_id,
                    "related_asset_id": event.related_asset_id,
                }
                for event in self._event_history
            ],
        }

    @classmethod
    def from_snapshot(
        cls,
        snapshot: dict[str, Any],
        *,
        current_consist: Consist | None = None,
    ) -> Train:
        """
        Reconstitute a Train from a previously saved snapshot.

        This method does NOT create a new CREATED event. It restores the
        saved event history exactly as provided.
        """
        train = cls(
            train_id=snapshot["train_id"],
            symbol=snapshot["symbol"],
            origin=snapshot.get("origin"),
            destination=snapshot.get("destination"),
            current_consist=current_consist,
            status=TrainStatus(snapshot["status"]),
            _suppress_creation_event=True,
        )

        restored_events = [
            TrainEvent(
                sequence=event_data["sequence"],
                event_type=TrainEventType(event_data["event_type"]),
                occurred_at=datetime.fromisoformat(event_data["occurred_at"]),
                details=event_data.get("details"),
                location=event_data.get("location"),
                related_consist_id=event_data.get("related_consist_id"),
                related_asset_id=event_data.get("related_asset_id"),
            )
            for event_data in snapshot.get("event_history", [])
        ]

        train._event_history = restored_events
        return train

    def _record_event(
        self,
        event_type: TrainEventType,
        *,
        occurred_at: datetime | None = None,
        details: str | None = None,
        location: str | None = None,
        related_consist_id: str | None = None,
        related_asset_id: str | None = None,
        severity: EventSeverity = EventSeverity.INFO,
    ) -> None:
        """
        Append a new train event.

        Event sequence numbers are monotonic within the owning train:
        1, 2, 3, 4, ...
        """
        timestamp = (
            occurred_at if occurred_at is not None else datetime.now(timezone.utc)
        )

        self._event_history.append(
            TrainEvent(
                sequence=len(self._event_history) + 1,
                event_type=event_type,
                occurred_at=timestamp,
                details=details,
                location=location,
                related_consist_id=related_consist_id,
                related_asset_id=related_asset_id,
                severity=severity,
            )
        )

    def emergency_stop(
        self,
        *,
        occurred_at: datetime | None = None,
        details: str | None = None,
        location: str | None = None,
        severity: EventSeverity = EventSeverity.CRITICAL,
    ) -> None:
        """
        Mark the train as emergency stopped and record the event.
        """
        self.status = TrainStatus.EMERGENCY_STOPPED

        self._record_event(
            TrainEventType.EMERGENCY_STOPPED,
            occurred_at=occurred_at,
            details=details or "Train emergency stopped.",
            location=location,
            related_consist_id=self._consist_reference(self.current_consist),
            severity=severity,
        )

    @staticmethod
    def _consist_reference(consist: Consist | None) -> str | None:
        """
        Return a string identifier for a consist when available.

        If the Consist class later gains a formal consist_id, this method
        can be updated to use it directly.
        """
        if consist is None:
            return None

        consist_id = getattr(consist, "consist_id", None)
        if consist_id is not None:
            return str(consist_id)

        return None

    def __repr__(self) -> str:
        return f"Train({self.symbol})"
