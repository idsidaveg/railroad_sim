from railroad_sim.application.movement_orchestration_service import (
    MovementOrchestrationService,
)
from railroad_sim.application.post_contact_context import PostContactContext
from railroad_sim.domain.consist import Consist
from railroad_sim.domain.enums import TrackType, TravelDirection
from railroad_sim.domain.equipment.boxcar import BoxCar
from railroad_sim.domain.network.consist_movement_service import ConsistMovementService
from railroad_sim.domain.network.consist_movement_types import MoveCommand
from railroad_sim.domain.network.contact_resolution_service import (
    ContactResolutionService,
)
from railroad_sim.domain.network.footprint_service import FootprintService
from railroad_sim.domain.network.position_types import ConsistExtent, NetworkPosition
from railroad_sim.domain.network.rail_network import RailNetwork
from railroad_sim.domain.network.topology_movement_service import (
    TopologyMovementService,
)
from railroad_sim.domain.network.turnout_evaluator import TurnoutEvaluator
from railroad_sim.domain.track import Track


def build_consist(count: int) -> Consist:
    cars = []
    for i in range(count):
        car = BoxCar(reporting_mark="TST", road_number=f"{i + 1:04d}")
        cars.append(car)

    for left, right in zip(cars, cars[1:]):
        left.rear_coupler.connect(right.front_coupler)

    return Consist(anchor=cars[0])


def make_extent(consist, track, rear, front, direction):
    return ConsistExtent(
        consist=consist,
        rear_position=NetworkPosition(track_id=track.track_id, offset_ft=rear),
        front_position=NetworkPosition(track_id=track.track_id, offset_ft=front),
        travel_direction=direction,
    )


def test_execute_move_triggers_post_contact_resolution_on_contact():
    network = RailNetwork(name="Test Network")
    track = Track(name="Main", track_type=TrackType.MAINLINE, length_ft=1000.0)
    network.add_track(track)

    topology = TopologyMovementService(network)
    footprint = FootprintService(network=network, movement_service=topology)
    turnout_eval = TurnoutEvaluator(footprint_service=footprint, track_key_by_id={})

    movement = ConsistMovementService(
        network=network,
        footprint_service=footprint,
        turnout_evaluator=turnout_eval,
        topology_movement_service=topology,
        contact_resolution_service=ContactResolutionService(),
    )

    orchestrator = MovementOrchestrationService(
        movement_service=movement,
    )

    a = build_consist(2)
    b = build_consist(2)

    extent_a = make_extent(
        a, track, 100.0, 100.0 + a.operational_length_ft, TravelDirection.TOWARD_B
    )
    extent_b = make_extent(
        b, track, 400.0, 400.0 + b.operational_length_ft, TravelDirection.STATIONARY
    )

    footprint_b = footprint.footprint_for_extent(extent_b)

    result = orchestrator.execute_move(
        extent=extent_a,
        command=MoveCommand.FORWARD,
        distance_ft=300.0,
        turnout_windows_by_key={},
        active_footprints=(footprint_b,),
        post_contact_context=PostContactContext(
            other_consists=(b,),
            moved_speed_mph=2.0,
            other_speed_mph=0.0,
            other_direction=TravelDirection.STATIONARY,
            moved_mass_lb=a.gross_weight_lb,
            other_mass_lb=b.gross_weight_lb,
        ),
    )

    # Movement occurred
    assert result.movement_result.contact_occurred is True

    # Post-contact pipeline executed
    assert result.post_contact_result is not None

    # Coupling occurred at low speed
    assert result.post_contact_result.coupling_result is not None


def test_execute_move_without_contact_returns_no_post_contact_result():
    network = RailNetwork(name="Test Network")
    track = Track(name="Main", track_type=TrackType.MAINLINE, length_ft=1000.0)
    network.add_track(track)

    topology = TopologyMovementService(network)
    footprint = FootprintService(network=network, movement_service=topology)
    turnout_eval = TurnoutEvaluator(footprint_service=footprint, track_key_by_id={})

    movement = ConsistMovementService(
        network=network,
        footprint_service=footprint,
        turnout_evaluator=turnout_eval,
        topology_movement_service=topology,
        contact_resolution_service=ContactResolutionService(),
    )

    orchestrator = MovementOrchestrationService(
        movement_service=movement,
    )

    a = build_consist(2)

    extent_a = make_extent(
        a,
        track,
        100.0,
        100.0 + a.operational_length_ft,
        TravelDirection.TOWARD_B,
    )

    result = orchestrator.execute_move(
        extent=extent_a,
        command=MoveCommand.FORWARD,
        distance_ft=50.0,
        turnout_windows_by_key={},
        active_footprints=(),
        post_contact_context=None,
    )

    assert result.movement_result.contact_occurred is False
    assert result.post_contact_result is None
    assert result.movement_result.actual_distance_ft == 50.0
