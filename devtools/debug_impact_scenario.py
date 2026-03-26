import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from railroad_sim.domain.consist import Consist
from railroad_sim.domain.enums import TrackType, TravelDirection
from railroad_sim.domain.equipment.boxcar import BoxCar
from railroad_sim.domain.network.consist_movement_service import ConsistMovementService
from railroad_sim.domain.network.consist_movement_types import MoveCommand
from railroad_sim.domain.network.contact_resolution_service import (
    ContactResolutionService,
)
from railroad_sim.domain.network.coupling_service import CouplingService
from railroad_sim.domain.network.footprint_service import FootprintService
from railroad_sim.domain.network.impact_service import ImpactService
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


def run_scenario(speed_a, speed_b, label):
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

    coupling = CouplingService()
    impact = ImpactService()

    a = build_consist(2)
    b = build_consist(2)

    extent_a = make_extent(a, track, 100.0, 210.0, TravelDirection.TOWARD_B)
    extent_b = make_extent(b, track, 400.0, 510.0, TravelDirection.STATIONARY)

    footprint_b = footprint.footprint_for_extent(extent_b)

    move_result = movement.move_extent(
        extent=extent_a,
        command=MoveCommand.FORWARD,
        distance_ft=300.0,
        turnout_windows_by_key={},
        active_footprints=(footprint_b,),
    )

    print("Movement:")
    print(f"  actual_distance: {move_result.actual_distance_ft}")
    print(f"  stop_reason:     {move_result.stop_reason}")
    print(f"  contact:         {move_result.contact_occurred}")
    print()

    coupling_result = coupling.try_couple(
        movement_result=move_result,
        other_consists=(b,),
        moved_speed_mph=speed_a,
        other_speed_mph=speed_b,
        other_direction=TravelDirection.STATIONARY,
    )

    print("Coupling:")
    print(f"  outcome: {coupling_result.outcome}")
    print()

    closing_speed = compute_closing_speed_mph(
        moved_speed_mph=speed_a,
        moved_direction=move_result.new_extent.travel_direction,
        other_speed_mph=speed_b,
        other_direction=TravelDirection.STATIONARY,
    )

    # consist b is stationary
    impact_result = impact.evaluate_from_coupling_result(
        coupling_result=coupling_result,
        closing_speed_mph=closing_speed,
        moved_mass_lb=a.gross_weight_lb,
        other_mass_lb=b.gross_weight_lb,
    )

    print("Impact:")
    print(f"  outcome: {impact_result.outcome}")
    print(f"  severity_score: {impact_result.severity_score}")
    print()

    if coupling_result.merged_consist:
        print("Merged consist:")
        print(coupling_result.merged_consist.diagram())


def main():
    run_scenario(2.0, 0.0, "LOW SPEED (should couple)")
    run_scenario(6.0, 0.0, "HIGH SPEED (should bounce)")


if __name__ == "__main__":
    main()
