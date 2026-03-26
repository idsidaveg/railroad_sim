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
from railroad_sim.domain.network.coupling_types import CouplingOutcome
from railroad_sim.domain.network.footprint_service import FootprintService
from railroad_sim.domain.network.position_types import ConsistExtent, NetworkPosition
from railroad_sim.domain.network.rail_network import RailNetwork
from railroad_sim.domain.network.topology_movement_service import (
    TopologyMovementService,
)
from railroad_sim.domain.network.turnout_evaluator import TurnoutEvaluator
from railroad_sim.domain.track import Track


def build_consist(car_count: int) -> Consist:
    cars: list[BoxCar] = []

    for i in range(car_count):
        car = BoxCar(reporting_mark="DBG", road_number=f"{i + 1:04d}")
        cars.append(car)

    for left, right in zip(cars, cars[1:]):
        left.rear_coupler.connect(right.front_coupler)

    return Consist(anchor=cars[0])


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


def main() -> None:
    print("\n=== COUPLING SCENARIO DEBUG ===\n")

    network = RailNetwork(name="Coupling Debug Network")
    track = Track(
        name="Main",
        track_type=TrackType.MAINLINE,
        length_ft=1000.0,
    )
    network.add_track(track)

    topology = TopologyMovementService(network)
    footprint_service = FootprintService(network=network, movement_service=topology)
    turnout_evaluator = TurnoutEvaluator(
        footprint_service=footprint_service,
        track_key_by_id={},
    )

    movement_service = ConsistMovementService(
        network=network,
        footprint_service=footprint_service,
        turnout_evaluator=turnout_evaluator,
        topology_movement_service=topology,
        contact_resolution_service=ContactResolutionService(),
    )
    coupling_service = CouplingService()

    consist_a = build_consist(2)
    consist_b = build_consist(2)

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

    footprint_b = footprint_service.footprint_for_extent(extent_b)

    print("Initial consists:")
    print(f"A consist_id: {consist_a.consist_id}")
    print(f"B consist_id: {consist_b.consist_id}")
    print(f"A cars:       {len(consist_a)}")
    print(f"B cars:       {len(consist_b)}")
    print()

    print("Initial positions:")
    print(
        f"A: {extent_a.rear_position.offset_ft} -> {extent_a.front_position.offset_ft}"
    )
    print(
        f"B: {extent_b.rear_position.offset_ft} -> {extent_b.front_position.offset_ft}"
    )
    print()

    movement_result = movement_service.move_extent(
        extent=extent_a,
        command=MoveCommand.FORWARD,
        distance_ft=300.0,
        turnout_windows_by_key={},
        active_footprints=(footprint_b,),
    )

    print("Movement result:")
    print(f"requested_distance_ft:   {movement_result.requested_distance_ft}")
    print(f"actual_distance_ft:      {movement_result.actual_distance_ft}")
    print(f"movement_limited:        {movement_result.movement_limited}")
    print(f"stop_reason:             {movement_result.stop_reason}")
    print(f"contact_occurred:        {movement_result.contact_occurred}")
    print(f"contact_with_consist_id: {movement_result.contact_with_consist_id}")
    print()

    print("Post-move positions:")
    print(
        "A: "
        f"{movement_result.new_extent.rear_position.offset_ft} -> "
        f"{movement_result.new_extent.front_position.offset_ft}"
    )
    print(
        f"B: {extent_b.rear_position.offset_ft} -> {extent_b.front_position.offset_ft}"
    )
    print()

    coupling_result = coupling_service.try_couple(
        movement_result=movement_result,
        other_consists=(consist_b,),
    )

    print("Coupling result:")
    print(f"outcome:          {coupling_result.outcome}")
    print(f"moved_consist_id: {coupling_result.moved_consist_id}")
    print(f"other_consist_id: {coupling_result.other_consist_id}")
    print()

    if coupling_result.outcome is CouplingOutcome.COUPLED:
        merged = coupling_result.merged_consist
        assert merged is not None

        print("Merged consist:")
        print(f"merged_consist_id: {merged.consist_id}")
        print(f"car_count:         {len(merged)}")
        print(f"length_ft:         {merged.operational_length_ft}")
        print(f"gross_weight_lb:   {merged.gross_weight_lb}")
        print()
        print("Merged diagram:")
        print(merged.diagram())
    else:
        print("No merged consist was created.")


if __name__ == "__main__":
    main()
