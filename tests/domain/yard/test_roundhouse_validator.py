from uuid import uuid4

import pytest

from railroad_sim.domain.yard.facility_types import FacilityType
from railroad_sim.domain.yard.roundhouse import Roundhouse
from railroad_sim.domain.yard.roundhouse_validator import RoundhouseValidator
from railroad_sim.domain.yard.turntable import Turntable


def test_roundhouse_validator_passes_valid_configuration() -> None:
    bridge = uuid4()
    approach = uuid4()
    stall_1 = uuid4()
    stall_2 = uuid4()

    turntable = Turntable(
        name="TT",
        bridge_length_ft=100,
        bridge_track_id=bridge,
        approach_track_id=approach,
        stall_track_ids=(stall_1, stall_2),
    )

    roundhouse = Roundhouse(
        name="RH",
        facility_type=FacilityType.ROUNDHOUSE,
        turntable_id=turntable.turntable_id,
        stall_track_ids=(stall_1, stall_2),
    )

    RoundhouseValidator.validate(roundhouse, turntable)


def test_validator_fails_if_turntable_id_mismatch() -> None:
    turntable = Turntable(
        name="TT",
        bridge_length_ft=100,
        bridge_track_id=uuid4(),
        approach_track_id=uuid4(),
    )

    roundhouse = Roundhouse(
        name="RH",
        facility_type=FacilityType.ROUNDHOUSE,
        turntable_id=uuid4(),  # intentionally wrong
    )

    with pytest.raises(ValueError, match="references turntable"):
        RoundhouseValidator.validate(roundhouse, turntable)


def test_validator_fails_if_stall_not_on_turntable() -> None:
    bridge = uuid4()
    approach = uuid4()
    stall_valid = uuid4()
    stall_invalid = uuid4()

    turntable = Turntable(
        name="TT",
        bridge_length_ft=100,
        bridge_track_id=bridge,
        approach_track_id=approach,
        stall_track_ids=(stall_valid,),
    )

    roundhouse = Roundhouse(
        name="RH",
        facility_type=FacilityType.ROUNDHOUSE,
        turntable_id=turntable.turntable_id,
        stall_track_ids=(stall_valid, stall_invalid),
    )

    with pytest.raises(ValueError, match="not registered on turntable"):
        RoundhouseValidator.validate(roundhouse, turntable)
