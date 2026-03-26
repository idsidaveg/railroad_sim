from __future__ import annotations

from uuid import uuid4

from railroad_sim.domain.consist import Consist
from railroad_sim.domain.enums import TrackType, TravelDirection
from railroad_sim.domain.equipment.boxcar import BoxCar
from railroad_sim.domain.network.consist_movement_service import ConsistMovementService
from railroad_sim.domain.network.consist_movement_types import (
    MoveCommand,
    MovementExecutionResult,
)
from railroad_sim.domain.network.contact_resolution_service import (
    ContactResolutionService,
)
from railroad_sim.domain.network.coupling_service import CouplingService
from railroad_sim.domain.network.coupling_types import CouplingOutcome
from railroad_sim.domain.network.footprint_service import FootprintService
from railroad_sim.domain.network.position_types import ConsistExtent, NetworkPosition
from railroad_sim.domain.network.rail_network import RailNetwork
from railroad_sim.domain.network.topology_movement_enums import MovementBlockReason
from railroad_sim.domain.network.topology_movement_service import (
    TopologyMovementService,
)
from railroad_sim.domain.network.turnout_evaluator import TurnoutEvaluator
from railroad_sim.domain.track import Track


def build_test_consist(*, car_count: int) -> Consist:
    if car_count <= 0:
        raise ValueError("car_count must be positive")

    equipment: list[BoxCar] = []

    for index in range(1, car_count + 1):
        car = BoxCar(
            reporting_mark="TST",
            road_number=f"{index:04d}",
        )
        equipment.append(car)

    for left, right in zip(equipment, equipment[1:]):
        left.rear_coupler.connect(right.front_coupler)

    return Consist(anchor=equipment[0])


def make_extent(
    *,
    consist: Consist,
    track: Track,
    rear_offset_ft: float,
    front_offset_ft: float,
    travel_direction: TravelDirection,
) -> ConsistExtent:
    return ConsistExtent(
        consist=consist,
        rear_position=NetworkPosition(
            track_id=track.track_id,
            offset_ft=rear_offset_ft,
        ),
        front_position=NetworkPosition(
            track_id=track.track_id,
            offset_ft=front_offset_ft,
        ),
        travel_direction=travel_direction,
    )


def build_service(network: RailNetwork) -> ConsistMovementService:
    topology = TopologyMovementService(network)
    footprint = FootprintService(network=network, movement_service=topology)
    evaluator = TurnoutEvaluator(
        footprint_service=footprint,
        track_key_by_id={},
    )
    contact_service = ContactResolutionService()

    return ConsistMovementService(
        network=network,
        footprint_service=footprint,
        turnout_evaluator=evaluator,
        topology_movement_service=topology,
        contact_resolution_service=contact_service,
    )


def test_try_couple_merges_consists_after_forward_contact() -> None:
    network = RailNetwork(name="Coupling Test Network")
    track = Track(
        name="Main",
        track_type=TrackType.MAINLINE,
        length_ft=1000.0,
    )
    network.add_track(track)

    movement_service = build_service(network)
    coupling_service = CouplingService()

    consist_a = build_test_consist(car_count=2)
    consist_b = build_test_consist(car_count=2)

    extent_a = make_extent(
        consist=consist_a,
        track=track,
        rear_offset_ft=100.0,
        front_offset_ft=210.0,
        travel_direction=TravelDirection.TOWARD_B,
    )

    extent_b = make_extent(
        consist=consist_b,
        track=track,
        rear_offset_ft=400.0,
        front_offset_ft=510.0,
        travel_direction=TravelDirection.STATIONARY,
    )

    footprint_b = movement_service._footprint_service.footprint_for_extent(extent_b)

    movement_result = movement_service.move_extent(
        extent=extent_a,
        command=MoveCommand.FORWARD,
        distance_ft=300.0,
        turnout_windows_by_key={},
        active_footprints=(footprint_b,),
    )

    assert movement_result.contact_occurred is True
    assert movement_result.contact_with_consist_id == consist_b.consist_id

    coupling_result = coupling_service.try_couple(
        movement_result=movement_result,
        other_consists=(consist_b,),
        closing_speed_mph=3.0,
    )

    assert coupling_result.outcome is CouplingOutcome.COUPLED
    assert coupling_result.moved_consist_id == consist_a.consist_id
    assert coupling_result.other_consist_id == consist_b.consist_id
    assert coupling_result.merged_consist is not None
    assert len(coupling_result.merged_consist) == 4


def test_try_couple_returns_no_contact_when_movement_result_has_no_contact() -> None:
    network = RailNetwork(name="Coupling Test Network")
    track = Track(
        name="Main",
        track_type=TrackType.MAINLINE,
        length_ft=1000.0,
    )
    network.add_track(track)

    movement_service = build_service(network)
    coupling_service = CouplingService()

    consist_a = build_test_consist(car_count=2)

    extent_a = make_extent(
        consist=consist_a,
        track=track,
        rear_offset_ft=100.0,
        front_offset_ft=210.0,
        travel_direction=TravelDirection.TOWARD_B,
    )

    movement_result = movement_service.move_extent(
        extent=extent_a,
        command=MoveCommand.FORWARD,
        distance_ft=50.0,
        turnout_windows_by_key={},
        active_footprints=(),
    )

    assert movement_result.contact_occurred is False
    assert movement_result.contact_with_consist_id is None

    coupling_result = coupling_service.try_couple(
        movement_result=movement_result,
        other_consists=(),
        closing_speed_mph=3.0,
    )

    assert coupling_result.outcome is CouplingOutcome.NO_CONTACT
    assert coupling_result.moved_consist_id == consist_a.consist_id
    assert coupling_result.other_consist_id is None
    assert coupling_result.merged_consist is None


def test_try_couple_returns_other_consist_not_found_when_contact_id_is_missing() -> (
    None
):
    network = RailNetwork(name="Coupling Test Network")
    track = Track(
        name="Main",
        track_type=TrackType.MAINLINE,
        length_ft=1000.0,
    )
    network.add_track(track)

    movement_service = build_service(network)
    coupling_service = CouplingService()

    consist_a = build_test_consist(car_count=2)
    consist_b = build_test_consist(car_count=2)

    extent_a = make_extent(
        consist=consist_a,
        track=track,
        rear_offset_ft=100.0,
        front_offset_ft=210.0,
        travel_direction=TravelDirection.TOWARD_B,
    )

    extent_b = make_extent(
        consist=consist_b,
        track=track,
        rear_offset_ft=400.0,
        front_offset_ft=510.0,
        travel_direction=TravelDirection.STATIONARY,
    )

    footprint_b = movement_service._footprint_service.footprint_for_extent(extent_b)

    movement_result = movement_service.move_extent(
        extent=extent_a,
        command=MoveCommand.FORWARD,
        distance_ft=300.0,
        turnout_windows_by_key={},
        active_footprints=(footprint_b,),
    )

    assert movement_result.contact_occurred is True
    assert movement_result.contact_with_consist_id == consist_b.consist_id

    coupling_result = coupling_service.try_couple(
        movement_result=movement_result,
        other_consists=(),
        closing_speed_mph=3.0,
    )

    assert coupling_result.outcome is CouplingOutcome.OTHER_CONSIST_NOT_FOUND
    assert coupling_result.moved_consist_id == consist_a.consist_id
    assert coupling_result.other_consist_id == consist_b.consist_id
    assert coupling_result.merged_consist is None


def test_try_couple_returns_invalid_contact_when_contact_id_is_missing() -> None:
    network = RailNetwork(name="Coupling Test Network")
    track = Track(
        name="Main",
        track_type=TrackType.MAINLINE,
        length_ft=1000.0,
    )
    network.add_track(track)

    topology = TopologyMovementService(network)
    footprint_service = FootprintService(network=network, movement_service=topology)
    coupling_service = CouplingService()

    consist_a = build_test_consist(car_count=2)

    extent_a = make_extent(
        consist=consist_a,
        track=track,
        rear_offset_ft=100.0,
        front_offset_ft=210.0,
        travel_direction=TravelDirection.TOWARD_B,
    )

    footprint_a = footprint_service.footprint_for_extent(extent_a)

    movement_result = MovementExecutionResult(
        requested_distance_ft=10.0,
        actual_distance_ft=10.0,
        prior_extent=extent_a,
        new_extent=extent_a,
        footprint=footprint_a,
        turnout_states={},
        movement_limited=False,
        stop_reason=MovementBlockReason.CONTACT,
        contact_occurred=True,
        contact_with_consist_id=None,
    )

    coupling_result = coupling_service.try_couple(
        movement_result=movement_result,
        other_consists=(),
        closing_speed_mph=3.0,
    )

    assert coupling_result.outcome is CouplingOutcome.INVALID_CONTACT
    assert coupling_result.moved_consist_id == consist_a.consist_id
    assert coupling_result.other_consist_id is None
    assert coupling_result.merged_consist is None


def test_try_couple_returns_contact_stop_required_when_contact_did_not_stop_on_contact() -> (
    None
):
    network = RailNetwork(name="Coupling Test Network")
    track = Track(
        name="Main",
        track_type=TrackType.MAINLINE,
        length_ft=1000.0,
    )
    network.add_track(track)

    topology = TopologyMovementService(network)
    footprint_service = FootprintService(network=network, movement_service=topology)
    coupling_service = CouplingService()

    consist_a = build_test_consist(car_count=2)

    extent_a = make_extent(
        consist=consist_a,
        track=track,
        rear_offset_ft=100.0,
        front_offset_ft=210.0,
        travel_direction=TravelDirection.TOWARD_B,
    )

    footprint_a = footprint_service.footprint_for_extent(extent_a)

    movement_result = MovementExecutionResult(
        requested_distance_ft=10.0,
        actual_distance_ft=10.0,
        prior_extent=extent_a,
        new_extent=extent_a,
        footprint=footprint_a,
        turnout_states={},
        movement_limited=False,
        stop_reason=MovementBlockReason.NONE,
        contact_occurred=True,
        contact_with_consist_id=uuid4(),
    )

    coupling_result = coupling_service.try_couple(
        movement_result=movement_result,
        other_consists=(),
        closing_speed_mph=3.0,
    )

    assert coupling_result.outcome is CouplingOutcome.CONTACT_STOP_REQUIRED
    assert coupling_result.moved_consist_id == consist_a.consist_id
    assert coupling_result.other_consist_id == movement_result.contact_with_consist_id
    assert coupling_result.merged_consist is None


def test_try_couple_returns_too_fast_to_couple_when_speed_exceeds_threshold() -> None:
    network = RailNetwork(name="Coupling Test Network")
    track = Track(
        name="Main",
        track_type=TrackType.MAINLINE,
        length_ft=1000.0,
    )
    network.add_track(track)

    movement_service = build_service(network)
    coupling_service = CouplingService()

    consist_a = build_test_consist(car_count=2)
    consist_b = build_test_consist(car_count=2)

    extent_a = make_extent(
        consist=consist_a,
        track=track,
        rear_offset_ft=100.0,
        front_offset_ft=210.0,
        travel_direction=TravelDirection.TOWARD_B,
    )

    extent_b = make_extent(
        consist=consist_b,
        track=track,
        rear_offset_ft=400.0,
        front_offset_ft=510.0,
        travel_direction=TravelDirection.STATIONARY,
    )

    footprint_b = movement_service._footprint_service.footprint_for_extent(extent_b)

    movement_result = movement_service.move_extent(
        extent=extent_a,
        command=MoveCommand.FORWARD,
        distance_ft=300.0,
        turnout_windows_by_key={},
        active_footprints=(footprint_b,),
    )

    assert movement_result.contact_occurred is True
    assert movement_result.stop_reason is MovementBlockReason.CONTACT

    coupling_result = coupling_service.try_couple(
        movement_result=movement_result,
        other_consists=(consist_b,),
        closing_speed_mph=6.0,  # intentionally too fast
    )

    assert coupling_result.outcome is CouplingOutcome.TOO_FAST_TO_COUPLE
    assert coupling_result.moved_consist_id == consist_a.consist_id
    assert coupling_result.other_consist_id == consist_b.consist_id
    assert coupling_result.merged_consist is None


def test_try_couple_computes_closing_speed_from_relative_motion() -> None:
    network = RailNetwork(name="Coupling Test Network")
    track = Track(
        name="Main",
        track_type=TrackType.MAINLINE,
        length_ft=1000.0,
    )
    network.add_track(track)

    movement_service = build_service(network)
    coupling_service = CouplingService()

    consist_a = build_test_consist(car_count=2)
    consist_b = build_test_consist(car_count=2)

    extent_a = make_extent(
        consist=consist_a,
        track=track,
        rear_offset_ft=100.0,
        front_offset_ft=210.0,
        travel_direction=TravelDirection.TOWARD_B,
    )

    extent_b = make_extent(
        consist=consist_b,
        track=track,
        rear_offset_ft=400.0,
        front_offset_ft=510.0,
        travel_direction=TravelDirection.STATIONARY,
    )

    footprint_b = movement_service._footprint_service.footprint_for_extent(extent_b)

    movement_result = movement_service.move_extent(
        extent=extent_a,
        command=MoveCommand.FORWARD,
        distance_ft=300.0,
        turnout_windows_by_key={},
        active_footprints=(footprint_b,),
    )

    assert movement_result.contact_occurred is True
    assert movement_result.stop_reason is MovementBlockReason.CONTACT

    coupling_result = coupling_service.try_couple(
        movement_result=movement_result,
        other_consists=(consist_b,),
        moved_speed_mph=2.0,
        other_speed_mph=1.0,
        other_direction=TravelDirection.TOWARD_A,
    )

    assert coupling_result.outcome is CouplingOutcome.COUPLED
    assert coupling_result.moved_consist_id == consist_a.consist_id
    assert coupling_result.other_consist_id == consist_b.consist_id
    assert coupling_result.merged_consist is not None
    assert len(coupling_result.merged_consist) == 4


def test_try_couple_returns_too_fast_to_couple_from_relative_motion() -> None:
    network = RailNetwork(name="Coupling Test Network")
    track = Track(
        name="Main",
        track_type=TrackType.MAINLINE,
        length_ft=1000.0,
    )
    network.add_track(track)

    movement_service = build_service(network)
    coupling_service = CouplingService()

    consist_a = build_test_consist(car_count=2)
    consist_b = build_test_consist(car_count=2)

    extent_a = make_extent(
        consist=consist_a,
        track=track,
        rear_offset_ft=100.0,
        front_offset_ft=210.0,
        travel_direction=TravelDirection.TOWARD_B,
    )

    extent_b = make_extent(
        consist=consist_b,
        track=track,
        rear_offset_ft=400.0,
        front_offset_ft=510.0,
        travel_direction=TravelDirection.STATIONARY,
    )

    footprint_b = movement_service._footprint_service.footprint_for_extent(extent_b)

    movement_result = movement_service.move_extent(
        extent=extent_a,
        command=MoveCommand.FORWARD,
        distance_ft=300.0,
        turnout_windows_by_key={},
        active_footprints=(footprint_b,),
    )

    assert movement_result.contact_occurred is True
    assert movement_result.stop_reason is MovementBlockReason.CONTACT

    coupling_result = coupling_service.try_couple(
        movement_result=movement_result,
        other_consists=(consist_b,),
        moved_speed_mph=3.0,
        other_speed_mph=2.5,
        other_direction=TravelDirection.TOWARD_A,
    )

    assert coupling_result.outcome is CouplingOutcome.TOO_FAST_TO_COUPLE
    assert coupling_result.moved_consist_id == consist_a.consist_id
    assert coupling_result.other_consist_id == consist_b.consist_id
    assert coupling_result.merged_consist is None
