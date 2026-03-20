from __future__ import annotations

from enum import Enum


class FacilityType(str, Enum):
    """
    High-level yard / railroad facility categories.

    These represent physical places or structures associated with railroad
    operations. They do not imply movement behavior by themselves.
    """

    ROUNDHOUSE = "roundhouse"
    ENGINE_HOUSE = "engine_house"
    ENGINE_MAINTENANCE = "engine_maintenance"
    REPAIR_SHOP = "repair_shop"
    FREIGHT_HOUSE = "freight_house"
    DEPOT = "depot"
    OFFICE = "office"
    FUEL = "fuel"
    SAND = "sand"
    WATER = "water"
    WAREHOUSE = "warehouse"
    INDUSTRY = "industry"
    STORAGE = "storage"
    OTHER = "other"


class TurntableTrackRole(str, Enum):
    """
    Role of a track relative to a turntable.

    APPROACH:
        The lead / approach track used to access the turntable bridge.

    STALL:
        Typically a roundhouse stall or storage stall track.

    SERVICE:
        Other service-connected tracks, such as shop leads or maintenance
        tracks that are not part of a roundhouse stall fan.
    """

    APPROACH = "approach"
    STALL = "stall"
    SERVICE = "service"
