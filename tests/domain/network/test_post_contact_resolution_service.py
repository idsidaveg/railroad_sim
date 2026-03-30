from railroad_sim.domain.consist import Consist
from railroad_sim.domain.enums import (
    DamageRating,
    RollingStockCondition,
    TrackType,
    TravelDirection,
)
from railroad_sim.domain.equipment.boxcar import BoxCar
from railroad_sim.domain.network.consist_movement_service import ConsistMovementService
from railroad_sim.domain.network.consist_movement_types import MoveCommand
from railroad_sim.domain.network.contact_resolution_service import (
    ContactResolutionService,
)
from railroad_sim.domain.network.footprint_service import FootprintService
from railroad_sim.domain.network.position_types import ConsistExtent, NetworkPosition
from railroad_sim.domain.network.post_contact_resolution_service import (
    PostContactResolutionService,
)
from railroad_sim.domain.network.rail_network import RailNetwork
from railroad_sim.domain.network.topology_movement_service import (
    TopologyMovementService,
)
from railroad_sim.domain.network.turnout_evaluator import TurnoutEvaluator
from railroad_sim.domain.track import Track


def build_consist(car_count: int) -> Consist:
    cars = []

    for i in range(car_count):
        car = BoxCar(reporting_mark="TST", road_number=f"{i + 1:04d}")
        cars.append(car)

    for left, right in zip(cars, cars[1:]):
        left.rear_coupler.connect(right.front_coupler)

    return Consist(anchor=cars[0])


def make_extent(
    consist: Consist,
    track: Track,
    rear: float,
    front: float,
    direction: TravelDirection,
) -> ConsistExtent:
    return ConsistExtent(
        consist=consist,
        rear_position=NetworkPosition(track_id=track.track_id, offset_ft=rear),
        front_position=NetworkPosition(track_id=track.track_id, offset_ft=front),
        travel_direction=direction,
    )


def test_resolve_applies_hard_collision_damage_to_correct_cars() -> None:
    Consist._reset_registry_for_tests()

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

    resolver = PostContactResolutionService()

    moved = build_consist(2)
    other = build_consist(2)

    moved_mass_lb = moved.gross_weight_lb
    other_mass_lb = other.gross_weight_lb

    moved_extent = make_extent(moved, track, 100.0, 210.0, TravelDirection.TOWARD_B)
    other_extent = make_extent(other, track, 400.0, 510.0, TravelDirection.STATIONARY)

    other_footprint = footprint.footprint_for_extent(other_extent)

    move_result = movement.move_extent(
        extent=moved_extent,
        command=MoveCommand.FORWARD,
        distance_ft=300.0,
        turnout_windows_by_key={},
        active_footprints=(other_footprint,),
    )

    resolution = resolver.resolve(
        movement_result=move_result,
        other_consists=(other,),
        moved_speed_mph=12.0,
        other_speed_mph=0.0,
        other_direction=TravelDirection.STATIONARY,
        moved_mass_lb=moved_mass_lb,
        other_mass_lb=other_mass_lb,
        moved_car_count=2,
        other_car_count=2,
        moved_contact_from_front=True,
        other_contact_from_front=False,
    )

    assert resolution.coupling_result.outcome.name == "TOO_FAST_TO_COUPLE"
    assert resolution.impact_result.outcome.name == "HARD_COLLISION"
    assert resolution.behavior_result.incident_required is False

    moved_order = moved.ordered_equipment()
    other_order = other.ordered_equipment()

    moved_impact_car = moved_order[0]
    moved_non_impact_car = moved_order[1]

    other_non_impact_car = other_order[0]
    other_impact_car = other_order[1]

    assert moved_impact_car.condition is RollingStockCondition.DAMAGED
    assert moved_impact_car.damage_rating is DamageRating.MODERATE
    assert moved_impact_car.front_coupler.is_damaged is True
    assert moved_impact_car.rear_coupler.is_damaged is True

    assert moved_non_impact_car.condition is RollingStockCondition.IN_SERVICE
    assert moved_non_impact_car.damage_rating is None
    assert moved_non_impact_car.front_coupler.is_damaged is False
    assert moved_non_impact_car.rear_coupler.is_damaged is False

    assert other_impact_car.condition is RollingStockCondition.DAMAGED
    assert other_impact_car.damage_rating is DamageRating.MODERATE
    assert other_impact_car.front_coupler.is_damaged is True
    assert other_impact_car.rear_coupler.is_damaged is True

    assert other_non_impact_car.condition is RollingStockCondition.IN_SERVICE
    assert other_non_impact_car.damage_rating is None
    assert other_non_impact_car.front_coupler.is_damaged is False
    assert other_non_impact_car.rear_coupler.is_damaged is False

    Consist._reset_registry_for_tests()
