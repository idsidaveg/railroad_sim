from __future__ import annotations

from dataclasses import InitVar, dataclass, field
from datetime import date, datetime, timezone
from uuid import UUID, uuid4

from railroad_sim.domain.couplers import Coupler
from railroad_sim.domain.enums import (
    CouplerPosition,
    EventSeverity,
    MaintenanceStatus,
    RollingStockCondition,
    RollingStockEventType,
)
from railroad_sim.domain.events import RollingStockEvent


@dataclass(slots=True)
class RollingStock:
    """
    Base domain object representing a single piece of railroad equipment.

    Each RollingStock instance owns two couplers:
        - front_coupler
        - rear_coupler

    Couplers define the physical connections that form a consist.

    Identity is anchored by immutable asset_id.
    reporting_mark and road_number may change over time.

    RollingStock also tracks:
        - current condition / serviceability state
        - maintenance placeholders
        - append-only asset event history
    """

    reporting_mark: str
    road_number: str
    asset_id_value: InitVar[UUID | None] = None

    # created_at_value exists to support reconstruction of assets
    # from persisted storage (catalog files, snapshots, etc.)
    # so that the original CREATED event timestamp can be preserved.
    created_at_value: InitVar[datetime | None] = None
    owner: str | None = None

    _asset_id: UUID = field(init=False, repr=False)
    front_coupler: Coupler = field(init=False)
    rear_coupler: Coupler = field(init=False)

    condition: RollingStockCondition = field(
        init=False,
        default=RollingStockCondition.IN_SERVICE,
    )
    maintenance_status: MaintenanceStatus = field(
        init=False,
        default=MaintenanceStatus.NONE,
    )
    inspection_due_miles: int | None = field(init=False, default=None)
    inspection_due_date: date | None = field(init=False, default=None)
    restricted_from_service: bool = field(init=False, default=False)

    _event_history: list[RollingStockEvent] = field(
        init=False,
        default_factory=list,
        repr=False,
    )

    def __post_init__(
        self, asset_id_value: UUID | None, created_at_value: datetime | None
    ) -> None:
        self._asset_id = asset_id_value if asset_id_value is not None else uuid4()

        self.reporting_mark = self.reporting_mark.strip().upper()
        self.road_number = self.road_number.strip()

        if not self.reporting_mark:
            raise ValueError("reporting_mark cannot be empty.")

        if not self.road_number:
            raise ValueError("road_number cannot be empty.")

        self.front_coupler = Coupler(
            owner=self,
            position=CouplerPosition.FRONT,
        )
        self.rear_coupler = Coupler(
            owner=self,
            position=CouplerPosition.REAR,
        )

        created_at = (
            created_at_value
            if created_at_value is not None
            else datetime.now(timezone.utc)
        )

        self._record_event(
            RollingStockEventType.CREATED,
            occurred_at=created_at,
            details="Rolling stock created.",
        )

    @property
    def operational_length_ft(self) -> float:
        raise NotImplementedError

    @property
    def asset_id(self) -> UUID:
        """Immutable unique identity for this equipment."""
        return self._asset_id

    @property
    def equipment_id(self) -> str:
        """Human-readable railroad identifier."""
        return f"{self.reporting_mark} {self.road_number}"

    @property
    def event_history(self) -> tuple[RollingStockEvent, ...]:
        """Read-only view of this asset's event history."""
        return tuple(self._event_history)

    @property
    def is_serviceable(self) -> bool:
        """
        Return True when this asset is currently fit for service
        according to its summarized state.
        """
        if self.restricted_from_service:
            return False

        if self.condition is not RollingStockCondition.IN_SERVICE:
            return False

        if self.maintenance_status is MaintenanceStatus.OVERDUE:
            return False

        return True

    @property
    def equipment_class(self) -> str:
        """Return the operational classification for this equipment"""
        return "ROLLING_STOCK"

    @property
    def equipment_short_name(self) -> str:
        """short name used for GUI and rendering requirements for this equipment"""
        return self.equipment_class

    def can_complete_trip(self, distance_miles: int) -> bool:
        """
        Determine whether this asset can complete a proposed trip
        based on current serviceability and inspection mileage.
        """
        if distance_miles < 0:
            raise ValueError("distance_miles cannot be negative.")

        if not self.is_serviceable:
            return False

        if (
            self.inspection_due_miles is not None
            and self.inspection_due_miles < distance_miles
        ):
            return False

        return True

    def rename_equipment(self, reporting_mark: str, road_number: str) -> None:
        """
        Update the visible railroad identifier without changing asset identity.

        A RENAMED event is recorded only when the visible identifier
        actually changes.
        """
        reporting_mark = reporting_mark.strip().upper()
        road_number = road_number.strip()

        if not reporting_mark:
            raise ValueError("reporting_mark cannot be empty.")

        if not road_number:
            raise ValueError("road_number cannot be empty.")

        old_equipment_id = self.equipment_id
        new_equipment_id = f"{reporting_mark} {road_number}"

        if old_equipment_id == new_equipment_id:
            return

        self.reporting_mark = reporting_mark
        self.road_number = road_number

        self._record_event(
            RollingStockEventType.RENAMED,
            details=f"Renamed from {old_equipment_id} to {new_equipment_id}.",
        )

    def mark_damaged(
        self,
        *,
        occurred_at: datetime | None = None,
        details: str | None = None,
        location: str | None = None,
        related_train_id: str | None = None,
    ) -> None:
        """
        Mark this asset as damaged and restrict it from service.
        """
        self.condition = RollingStockCondition.DAMAGED
        self.restricted_from_service = True

        self._record_event(
            RollingStockEventType.DAMAGED,
            occurred_at=occurred_at,
            details=details or "Asset marked damaged.",
            location=location,
            related_train_id=related_train_id,
        )

    def mark_bad_order(
        self,
        *,
        occurred_at: datetime | None = None,
        details: str | None = None,
        location: str | None = None,
        related_train_id: str | None = None,
    ) -> None:
        """
        Mark this asset as bad order and restrict it from service.
        """
        self.condition = RollingStockCondition.BAD_ORDER
        self.restricted_from_service = True

        self._record_event(
            RollingStockEventType.BAD_ORDERED,
            occurred_at=occurred_at,
            details=details or "Asset marked bad order.",
            location=location,
            related_train_id=related_train_id,
        )

    def schedule_maintenance(
        self,
        *,
        occurred_at: datetime | None = None,
        details: str | None = None,
        location: str | None = None,
        due_miles: int | None = None,
        due_date: date | None = None,
    ) -> None:
        """
        Schedule maintenance for this asset.

        This does not automatically remove the asset from service.
        It only updates maintenance placeholders and records history.
        """
        if due_miles is not None and due_miles < 0:
            raise ValueError("due_miles cannot be negative.")

        self.maintenance_status = MaintenanceStatus.SCHEDULED
        self.inspection_due_miles = due_miles
        self.inspection_due_date = due_date

        self._record_event(
            RollingStockEventType.MAINTENANCE_SCHEDULED,
            occurred_at=occurred_at,
            details=details or "Maintenance scheduled.",
            location=location,
        )

    def complete_maintenance(
        self,
        *,
        occurred_at: datetime | None = None,
        details: str | None = None,
        location: str | None = None,
        clear_due_flags: bool = True,
    ) -> None:
        """
        Mark maintenance as completed.

        By default, due-mile and due-date placeholders are cleared.
        """
        self.maintenance_status = MaintenanceStatus.NONE

        if clear_due_flags:
            self.inspection_due_miles = None
            self.inspection_due_date = None

        self._record_event(
            RollingStockEventType.MAINTENANCE_COMPLETED,
            occurred_at=occurred_at,
            details=details or "Maintenance completed.",
            location=location,
        )

    def release_to_service(
        self,
        *,
        occurred_at: datetime | None = None,
        details: str | None = None,
        location: str | None = None,
    ) -> None:
        """
        Return this asset to in-service status.

        This is intended for use after repair, inspection, or other
        hold conditions have been cleared.
        """
        self.condition = RollingStockCondition.IN_SERVICE
        self.restricted_from_service = False

        if self.maintenance_status is MaintenanceStatus.OVERDUE:
            self.maintenance_status = MaintenanceStatus.NONE

        self._record_event(
            RollingStockEventType.RELEASED_TO_SERVICE,
            occurred_at=occurred_at,
            details=details or "Asset released to service.",
            location=location,
        )

    def assign_to_train(
        self,
        train_id: str,
        *,
        occurred_at: datetime | None = None,
        details: str | None = None,
        location: str | None = None,
    ) -> None:
        """
        Record that this asset was assigned to a train.

        This only records asset history. It does not perform consist
        coupling or train assignment logic.
        """
        train_id = train_id.strip()
        if not train_id:
            raise ValueError("train_id cannot be empty.")

        self._record_event(
            RollingStockEventType.ASSIGNED_TO_TRAIN,
            occurred_at=occurred_at,
            details=details or f"Assigned to train {train_id}.",
            location=location,
            related_train_id=train_id,
        )

    def remove_from_train(
        self,
        train_id: str,
        *,
        occurred_at: datetime | None = None,
        details: str | None = None,
        location: str | None = None,
    ) -> None:
        """
        Record that this asset was removed from a train.

        This only records asset history. It does not perform consist
        splitting or reassignment logic.
        """
        train_id = train_id.strip()
        if not train_id:
            raise ValueError("train_id cannot be empty.")

        self._record_event(
            RollingStockEventType.REMOVED_FROM_TRAIN,
            occurred_at=occurred_at,
            details=details or f"Removed from train {train_id}.",
            location=location,
            related_train_id=train_id,
        )

    def _record_event(
        self,
        event_type: RollingStockEventType,
        *,
        occurred_at: datetime | None = None,
        details: str | None = None,
        location: str | None = None,
        related_train_id: str | None = None,
        severity: EventSeverity = EventSeverity.INFO,
    ) -> None:
        """
        Append a new event to this asset's internal event history.

        Event sequence numbers are monotonic within the owning asset:
        1, 2, 3, 4, ...
        """
        timestamp = (
            occurred_at if occurred_at is not None else datetime.now(timezone.utc)
        )

        self._event_history.append(
            RollingStockEvent(
                sequence=len(self._event_history) + 1,
                event_type=event_type,
                occurred_at=timestamp,
                details=details,
                location=location,
                related_train_id=related_train_id,
                severity=severity,
            )
        )

    def record_incident(
        self,
        event_type: RollingStockEventType,
        *,
        occurred_at: datetime | None = None,
        details: str | None = None,
        location: str | None = None,
        related_train_id: str | None = None,
        severity: EventSeverity = EventSeverity.WARNING,
        restrict_from_service: bool = True,
    ) -> None:
        """
        Record a significant incident against this asset.

        This provides a generic path for incidents that are more specific than
        simple damage or bad-order handling, such as derailments or hazmat leaks.
        """
        if restrict_from_service:
            self.restricted_from_service = True

            if event_type is RollingStockEventType.DERAILED:
                self.condition = RollingStockCondition.BAD_ORDER
            elif severity in (EventSeverity.MAJOR, EventSeverity.CRITICAL):
                self.condition = RollingStockCondition.DAMAGED

        self._record_event(
            event_type,
            occurred_at=occurred_at,
            details=details,
            location=location,
            related_train_id=related_train_id,
            severity=severity,
        )

    def __repr__(self) -> str:
        return f"RollingStock({self.equipment_id})"
