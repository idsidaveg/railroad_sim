from railroad_sim.domain.yard.facility_types import FacilityType, TurntableTrackRole


def test_facility_type_enum_values() -> None:
    assert FacilityType.ROUNDHOUSE.value == "roundhouse"
    assert FacilityType.REPAIR_SHOP.value == "repair_shop"
    assert FacilityType.INDUSTRY.value == "industry"


def test_turntable_track_role_enum_values() -> None:
    assert TurntableTrackRole.APPROACH.value == "approach"
    assert TurntableTrackRole.STALL.value == "stall"
    assert TurntableTrackRole.SERVICE.value == "service"
