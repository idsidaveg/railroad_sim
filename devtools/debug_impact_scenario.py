import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from _impact_debug_view import render_impact_debug_block

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
from railroad_sim.domain.network.relative_speed import compute_closing_speed_mph
from railroad_sim.domain.network.topology_movement_service import (
    TopologyMovementService,
)
from railroad_sim.domain.network.turnout_evaluator import TurnoutEvaluator
from railroad_sim.domain.track import Track


def build_consist(car_count: int) -> Consist:
    cars = []

    for i in range(car_count):
        car = BoxCar(reporting_mark="DBG", road_number=f"{i + 1:04d}")
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


def run_scenario(
    speed_a: float,
    speed_b: float,
    label: str,
    *,
    moved_car_count: int = 2,
    other_car_count: int = 2,
):
    print(f"\n=== {label} ===\n")

    network = RailNetwork(name="Impact Debug Network")
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

    # coupling = CouplingService()
    # impact = ImpactService()
    # impact_behavior = ImpactBehaviorService()
    # post_contact = PostContactResolutionService()
    # impact_damage = ImpactDamageService()
    orchestrator = MovementOrchestrationService(
        movement_service=movement,
    )

    a = build_consist(moved_car_count)
    b = build_consist(other_car_count)

    # Capture pre-contact masses before coupling mutates topology.
    moved_mass_lb = a.gross_weight_lb
    other_mass_lb = b.gross_weight_lb

    extent_a = make_extent(
        a, track, 100.0, 100.0 + a.operational_length_ft, TravelDirection.TOWARD_B
    )
    extent_b = make_extent(
        b, track, 400.0, 400.0 + b.operational_length_ft, TravelDirection.STATIONARY
    )

    footprint_b = footprint.footprint_for_extent(extent_b)

    orchestration_result = orchestrator.execute_move(
        extent=extent_a,
        command=MoveCommand.FORWARD,
        distance_ft=300.0,
        turnout_windows_by_key={},
        active_footprints=(footprint_b,),
        post_contact_context=PostContactContext(
            other_consists=(b,),
            moved_speed_mph=speed_a,
            other_speed_mph=speed_b,
            other_direction=TravelDirection.STATIONARY,
            moved_mass_lb=moved_mass_lb,
            other_mass_lb=other_mass_lb,
            moved_car_count=moved_car_count,
            other_car_count=other_car_count,
            moved_contact_from_front=True,
            other_contact_from_front=False,
        ),
    )

    move_result = orchestration_result.movement_result
    resolution_result = orchestration_result.post_contact_result

    print("Movement:")
    print(f"   actual_distance: {move_result.actual_distance_ft}")
    print(f"   stop_reason:     {move_result.stop_reason}")
    print(f"   contact:         {move_result.contact_occurred}")

    closing_speed = compute_closing_speed_mph(
        moved_speed_mph=speed_a,
        moved_direction=move_result.new_extent.travel_direction,
        other_speed_mph=speed_b,
        other_direction=TravelDirection.STATIONARY,
    )

    if resolution_result is None:
        raise RuntimeError(
            "Expected post-contact resolution result, but none produced."
        )

    coupling_result = resolution_result.coupling_result
    impact_result = resolution_result.impact_result
    behavior_result = resolution_result.behavior_result

    print("Coupling:")
    print(f"  outcome: {coupling_result.outcome}")

    print(
        render_impact_debug_block(
            movement_result=move_result,
            closing_speed_mph=closing_speed,
            impact_result=impact_result,
            behavior_result=behavior_result,
            moved_mass_lb=moved_mass_lb,
            other_mass_lb=other_mass_lb,
            moved_car_count=moved_car_count,
            other_car_count=other_car_count,
        )
    )

    print_damage_state("Moved consist", a)
    print_damage_state("Other consist", b)

    if coupling_result.merged_consist:
        print()
        print("Merged consist:")
        print(coupling_result.merged_consist.diagram())


def print_damage_state(label: str, consist: Consist) -> None:
    ordered = consist.ordered_equipment()

    print(f"{label} damage state:")
    print("   order:", " -> ".join(car.equipment_id for car in ordered))
    for idx, car in enumerate(consist.ordered_equipment(), start=1):
        print(
            f"  [{idx}] {car.equipment_id} "
            f"condition={car.condition} "
            f"damage_rating={car.damage_rating} "
            f"front_damaged={car.front_coupler.is_damaged} "
            f"front_rating={car.front_coupler.damage_rating} "
            f"rear_damaged={car.rear_coupler.is_damaged} "
            f"rear_rating={car.rear_coupler.damage_rating}"
        )
    print()


def main():
    run_scenario(2.0, 0.0, "LOW SPEED (should couple)")
    run_scenario(6.0, 0.0, "HIGH SPEED (should bounce)")
    run_scenario(
        6.0,
        0.0,
        "ASYMMETRIC MASS (moved lighter, should bounce unevenly)",
        moved_car_count=1,
        other_car_count=4,
    )
    run_scenario(
        10.0,
        0.0,
        "HIGH SPEED (still bounce, no incident)",
        moved_car_count=2,
        other_car_count=2,
    )
    run_scenario(
        12.0,
        0.0,
        "HARD COLLISION THRESHOLD CHECK (12 mph)",
        moved_car_count=2,
        other_car_count=2,
    )
    run_scenario(
        14.0,
        0.0,
        "HARD COLLISION MID-BAND CHECK (14 mph)",
        moved_car_count=2,
        other_car_count=2,
    )
    run_scenario(
        21.0,
        0.0,
        "HARD COLLISION (incident required)",
        moved_car_count=2,
        other_car_count=2,
    )


if __name__ == "__main__":
    main()
