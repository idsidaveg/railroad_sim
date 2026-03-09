from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from railroad_sim.domain.enums import (
    EventSeverity,
    RollingStockEventType,
    TrainEventType,
)
from railroad_sim.domain.rolling_stock import RollingStock
from railroad_sim.domain.train import Train


@dataclass(frozen=True, slots=True)
class IncidentOutcome:
    """
    Result of processing a coordinated incident.

    train_stopped:
        True when the coordinator caused the train to stop.

    asset_restricted:
        True when the asset is restricted from further service.

    train_event_type:
        The primary train-side event recorded.

    asset_event_type:
        The asset-side event recorded.
    """

    train_stopped: bool
    asset_restricted: bool
    train_event_type: TrainEventType
    asset_event_type: RollingStockEventType


class IncidentService:
    """
    Minimal coordination service for serious rolling stock incidents.

    This service coordinates cross-entity consequences:
        - record incident on the asset
        - record operational consequence on the train
        - stop the train when required

    It does NOT manipulate consist topology directly.
    """

    _TRAIN_EVENT_MAP: dict[RollingStockEventType, TrainEventType] = {
        RollingStockEventType.DERAILED: TrainEventType.ROLLING_STOCK_DERAILED,
        RollingStockEventType.HAZMAT_LEAK: TrainEventType.HAZMAT_LEAK_REPORTED,
        RollingStockEventType.MECHANICAL_FAILURE: TrainEventType.MECHANICAL_FAILURE_REPORTED,
        RollingStockEventType.LOAD_SHIFT: TrainEventType.LOAD_SHIFT_REPORTED,
        RollingStockEventType.DAMAGED: TrainEventType.INCIDENT_REPORTED,
        RollingStockEventType.BAD_ORDERED: TrainEventType.INCIDENT_REPORTED,
    }

    _AUTO_STOP_ASSET_EVENTS: set[RollingStockEventType] = {
        RollingStockEventType.DERAILED,
        RollingStockEventType.HAZMAT_LEAK,
    }

    _AUTO_STOP_SEVERITIES: set[EventSeverity] = {
        EventSeverity.CRITICAL,
    }

    def report_asset_incident(
        self,
        *,
        train: Train,
        asset: RollingStock,
        asset_event_type: RollingStockEventType,
        severity: EventSeverity,
        occurred_at: datetime | None = None,
        details: str | None = None,
        location: str | None = None,
        stop_train: bool | None = None,
        restrict_asset: bool = True,
    ) -> IncidentOutcome:
        """
        Record a coordinated asset incident and apply train-level consequences.

        stop_train:
            If None, stop behavior is inferred from event type and severity.
            If True/False, explicit caller choice overrides inference.
        """
        train_event_type = self._TRAIN_EVENT_MAP.get(
            asset_event_type,
            TrainEventType.INCIDENT_REPORTED,
        )

        should_stop_train = (
            stop_train
            if stop_train is not None
            else self._should_stop_train(
                asset_event_type=asset_event_type,
                severity=severity,
            )
        )

        asset.record_incident(
            asset_event_type,
            occurred_at=occurred_at,
            details=details,
            location=location,
            related_train_id=train.train_id,
            severity=severity,
            restrict_from_service=restrict_asset,
        )

        train.record_asset_event(
            train_event_type,
            related_asset_id=str(asset.asset_id),
            occurred_at=occurred_at,
            details=details,
            location=location,
            severity=severity,
        )

        if should_stop_train:
            train.emergency_stop(
                occurred_at=occurred_at,
                details=self._stop_message(asset_event_type, asset.equipment_id),
                location=location,
                severity=severity,
            )

        return IncidentOutcome(
            train_stopped=should_stop_train,
            asset_restricted=restrict_asset,
            train_event_type=train_event_type,
            asset_event_type=asset_event_type,
        )

    def _should_stop_train(
        self,
        *,
        asset_event_type: RollingStockEventType,
        severity: EventSeverity,
    ) -> bool:
        if asset_event_type in self._AUTO_STOP_ASSET_EVENTS:
            return True

        if severity in self._AUTO_STOP_SEVERITIES:
            return True

        return False

    @staticmethod
    def _stop_message(
        asset_event_type: RollingStockEventType,
        equipment_id: str,
    ) -> str:
        if asset_event_type is RollingStockEventType.DERAILED:
            return f"Emergency stop: {equipment_id} derailed."
        if asset_event_type is RollingStockEventType.HAZMAT_LEAK:
            return f"Emergency stop: hazardous leak reported on {equipment_id}."
        return f"Emergency stop: critical incident reported on {equipment_id}."
