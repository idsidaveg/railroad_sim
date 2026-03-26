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
from railroad_sim.domain.network.footprint_service import FootprintService
from railroad_sim.domain.network.position_types import ConsistExtent, NetworkPosition
from railroad_sim.domain.network.rail_network import RailNetwork
from railroad_sim.domain.network.topology_movement_service import (
    TopologyMovementService,
)
from railroad_sim.domain.network.turnout_evaluator import TurnoutEvaluator
from railroad_sim.domain.track import Track

# -------------------------
# Helpers
# -------------------------


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


# -------------------------
# Scenario
# -------------------------


def main():
    print("\n=== CONTACT SCENARIO DEBUG ===\n")

    # Build network
    network = RailNetwork(name="Contact Test Network")

    track = Track(
        name="Main",
        track_type=TrackType.MAINLINE,
        length_ft=1000.0,
    )
    network.add_track(track)

    topology = TopologyMovementService(network)
    footprint_service = FootprintService(network, movement_service=topology)
    turnout_evaluator = TurnoutEvaluator(
        footprint_service=footprint_service,
        track_key_by_id={},
    )
    contact_service = ContactResolutionService()

    movement_service = ConsistMovementService(
        network=network,
        footprint_service=footprint_service,
        turnout_evaluator=turnout_evaluator,
        topology_movement_service=topology,
        contact_resolution_service=contact_service,
    )

    # Build consists
    consist_a = build_consist(2)  # 110 ft
    consist_b = build_consist(2)  # 110 ft

    # Place them on track
    extent_a = make_extent(
        consist=consist_a,
        track=track,
        rear=100.0,
        front=210.0,
        direction=TravelDirection.TOWARD_B,
    )

    extent_b = make_extent(
        consist=consist_b,
        track=track,
        rear=400.0,
        front=510.0,
        direction=TravelDirection.STATIONARY,
    )

    footprint_b = footprint_service.footprint_for_extent(extent_b)

    print("Initial positions:")
    print(
        f"A: {extent_a.rear_position.offset_ft} → {extent_a.front_position.offset_ft}"
    )
    print(
        f"B: {extent_b.rear_position.offset_ft} → {extent_b.front_position.offset_ft}"
    )
    print()

    # Move A toward B
    requested_distance = 300.0

    result = movement_service.move_extent(
        extent=extent_a,
        command=MoveCommand.FORWARD,
        distance_ft=requested_distance,
        turnout_windows_by_key={},
        active_footprints=(footprint_b,),
    )

    print("Movement result:")
    print(f"Requested distance: {requested_distance}")
    print(f"Actual distance:    {result.actual_distance_ft}")
    print()

    new_extent = result.new_extent

    print("Final positions:")
    print(
        f"A: {new_extent.rear_position.offset_ft} → {new_extent.front_position.offset_ft}"
    )
    print(
        f"B: {extent_b.rear_position.offset_ft} → {extent_b.front_position.offset_ft}"
    )
    print()

    gap = extent_b.rear_position.offset_ft - new_extent.front_position.offset_ft

    print(f"Gap after move (should be 0): {gap}")
    print()

    print("Movement flags:")
    print(f"movement_limited:      {result.movement_limited}")
    print(f"stop_reason:           {result.stop_reason}")
    print(f"contact_occurred:      {result.contact_occurred}")
    print(f"contact_with_consist:  {result.contact_with_consist_id}")
    print()


if __name__ == "__main__":
    main()
