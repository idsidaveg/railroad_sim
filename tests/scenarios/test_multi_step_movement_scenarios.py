from __future__ import annotations

import pytest

from railroad_sim.domain.consist import Consist
from railroad_sim.domain.enums import (
    TrackEnd,
    TravelDirection,
)
from railroad_sim.domain.equipment.boxcar import BoxCar
from railroad_sim.domain.equipment.locomotive import Locomotive
from railroad_sim.domain.network.consist_movement_service import ConsistMovementService
from railroad_sim.domain.network.consist_movement_types import MoveCommand
from railroad_sim.domain.network.footprint_service import FootprintService
from railroad_sim.domain.network.position_types import ConsistExtent, NetworkPosition
from railroad_sim.domain.network.rail_network import RailNetwork
from railroad_sim.domain.network.topology_movement_enums import (
    MovementBlockReason,
)
from railroad_sim.domain.network.topology_movement_service import (
    TopologyMovementService,
)
from railroad_sim.domain.network.turnout_evaluator import TurnoutEvaluator
from railroad_sim.domain.track import Track
from railroad_sim.domain.yard.turntable import Turntable
from railroad_sim.domain.yard.turntable_connection import TurntableConnection
from tests.support.junction_builders import make_connection_junction
from tests.support.track_builders import make_track

# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


def build_service(
    network: RailNetwork,
    *,
    turntable_connections: tuple[TurntableConnection, ...] = (),
) -> tuple[ConsistMovementService, FootprintService]:
    """
    Build the real movement stack used by the existing movement tests.

    This keeps the scenario test aligned with current service wiring:
    - TopologyMovementService handles route/topology traversal
    - FootprintService computes multi-track occupancy
    - TurnoutEvaluator is still present, even though this scenario does not
      use turnout fouling windows
    """
    topology = TopologyMovementService(
        network,
        turntable_connections=turntable_connections,
    )
    footprint = FootprintService(network=network, movement_service=topology)
    evaluator = TurnoutEvaluator(
        footprint_service=footprint,
        track_key_by_id={},
    )

    service = ConsistMovementService(
        network=network,
        footprint_service=footprint,
        turnout_evaluator=evaluator,
        topology_movement_service=topology,
    )
    return service, footprint


def make_extent(
    *,
    consist: Consist,
    rear_track: Track,
    rear_offset_ft: float,
    front_track: Track,
    front_offset_ft: float,
    travel_direction: TravelDirection,
) -> ConsistExtent:
    """
    Construct a real ConsistExtent using the same pattern as the existing
    movement-service tests.
    """
    return ConsistExtent(
        consist=consist,
        rear_position=NetworkPosition(
            track_id=rear_track.track_id,
            offset_ft=rear_offset_ft,
        ),
        front_position=NetworkPosition(
            track_id=front_track.track_id,
            offset_ft=front_offset_ft,
        ),
        travel_direction=travel_direction,
    )


def build_locomotive_boxcar_consist() -> Consist:
    """
    Build a real 2-piece consist:

    - Locomotive = 73 ft
    - BoxCar     = 55 ft
    - Total      = 128 ft

    This scenario intentionally uses real equipment rather than synthetic test
    doubles so bridge-capacity assumptions are based on operational lengths
    already defined in the domain model.
    """
    loco = Locomotive(
        reporting_mark="TST",
        road_number="0001",
    )
    box = BoxCar(
        reporting_mark="TST",
        road_number="0002",
    )

    loco.rear_coupler.connect(box.front_coupler)

    return Consist(anchor=loco)


def build_turntable_capacity_scenario_network() -> tuple[
    RailNetwork,
    Track,
    Track,
    Track,
    Track,
    Turntable,
    TurntableConnection,
]:
    """
    Scenario topology under test:

        lead:B <-> approach:A
        approach:A <-> bridge:A   when aligned to approach
        stall_1:A <-> bridge:B    when aligned to stall_1

    Track lengths are deliberately chosen for bridge-capacity testing:

    - lead     = 200 ft
    - approach = 150 ft
    - bridge   = 150 ft
    - stall_1  = 200 ft

    The bridge is long enough to fully hold the test consist (128 ft) with
    some margin, which is required before turntable re-alignment.
    """
    network = RailNetwork(name="turntable-capacity-scenario")

    lead = make_track("Lead", length_ft=200.0)
    approach = make_track("Approach", length_ft=150.0)
    bridge = make_track("Bridge", length_ft=150.0)
    stall_1 = make_track("Stall 1", length_ft=200.0)

    for track in (lead, approach, bridge, stall_1):
        network.add_track(track)

    #  Fixed connection:
    # lead:B <-> approach:B
    #
    # This is intentional. The turntable connection to the approach is at
    # approach:A, so entering the approach from B allows a forward move to
    # continue toward A and then onto the bridge when aligned.
    lead_to_approach_junction, _ = make_connection_junction(
        name="LEAD_APPROACH",
        left_track=lead,
        left_end=TrackEnd.B,
        right_track=approach,
        right_end=TrackEnd.B,
        aligned=True,
    )
    network.add_junction(lead_to_approach_junction)

    turntable = Turntable(
        name="TT",
        bridge_length_ft=150.0,
        max_gross_weight_lb=600_000.0,
        bridge_track_id=bridge.track_id,
        approach_track_id=approach.track_id,
        stall_track_ids=(stall_1.track_id,),
    )

    connection = TurntableConnection(
        turntable=turntable,
        bridge_track=bridge,
        connected_tracks_by_id={
            approach.track_id: approach,
            stall_1.track_id: stall_1,
        },
    )

    return network, lead, approach, bridge, stall_1, turntable, connection


def build_turntable_insufficient_capacity_scenario_network():
    """
    Same topology as the valid-capacity turntable scenario, but with a bridge
    that is too short for the test consist.

        lead:B <-> approach:B
        approach:A <-> bridge:A   when aligned to approach
        stall_1:A <-> bridge:B    when aligned to stall_1

    Track lengths:
    - lead     = 200 ft
    - approach = 150 ft
    - bridge   = 100 ft
    - stall_1  = 200 ft

    The standard locomotive + boxcar consist is 128 ft total, so the bridge
    cannot fully contain it.
    """
    network = RailNetwork(name="turntable-capacity-scenario")

    lead = make_track("Lead", length_ft=200.0)
    approach = make_track("Approach", length_ft=150.0)
    bridge = make_track("Bridge", length_ft=100.0)
    stall_1 = make_track("Stall 1", length_ft=200.0)

    for track in (lead, approach, bridge, stall_1):
        network.add_track(track)

    #  Fixed connection:
    # lead:B <-> approach:B
    #
    # This is intentional. The turntable connection to the approach is at
    # approach:A, so entering the approach from B allows a forward move to
    # continue toward A and then onto the bridge when aligned.
    lead_to_approach_junction, _ = make_connection_junction(
        name="LEAD_APPROACH",
        left_track=lead,
        left_end=TrackEnd.B,
        right_track=approach,
        right_end=TrackEnd.B,
        aligned=True,
    )
    network.add_junction(lead_to_approach_junction)

    turntable = Turntable(
        name="TT",
        bridge_length_ft=100.0,
        max_gross_weight_lb=600_000.0,
        bridge_track_id=bridge.track_id,
        approach_track_id=approach.track_id,
        stall_track_ids=(stall_1.track_id,),
    )

    connection = TurntableConnection(
        turntable=turntable,
        bridge_track=bridge,
        connected_tracks_by_id={
            approach.track_id: approach,
            stall_1.track_id: stall_1,
        },
    )

    return network, lead, approach, bridge, stall_1, turntable, connection


# ---------------------------------------------------------------------
# Scenario tests
# ---------------------------------------------------------------------


def test_chained_forward_moves_through_turntable_with_valid_bridge_capacity() -> None:
    """
    Scenario:
    A locomotive + boxcar consist (128 ft total) performs a multi-step forward
    move through a turntable path:

        lead -> approach -> bridge -> stall_1

    Operational sequence:
    1. Start entirely on lead.
    2. Move forward onto approach.
    3. Align turntable to approach and move fully onto bridge.
    4. Confirm the consist is fully on the bridge before any turntable change.
    5. Re-align turntable to stall_1.
    6. Move forward off the bridge toward stall_1.

    What this validates:
    - Multi-step movement across multiple topology transitions.
    - Correct handling of A-to-A entry from approach onto bridge.
    - Bridge capacity is sufficient for the consist (128 <= 150).
    - The consist can be fully contained on the bridge before rotation.
    - FootprintService remains consistent with movement results at each phase.
    - Final movement off the bridge occupies bridge + stall_1 as expected.

    Important future rule:
    This test asserts the valid pre-turn condition today. A later production
    rule should explicitly reject turntable alignment changes when any part of
    the consist still occupies approach + bridge at the same time.
    """
    network, lead, approach, bridge, stall_1, turntable, connection = (
        build_turntable_capacity_scenario_network()
    )
    service, footprint_service = build_service(
        network,
        turntable_connections=(connection,),
    )

    consist = build_locomotive_boxcar_consist()
    consist_length = consist.operational_length_ft

    # Sanity checks for the core capacity assumption in this scenario.
    assert consist_length == pytest.approx(128.0)
    assert turntable.bridge_length_ft == pytest.approx(150.0)
    assert consist_length <= turntable.bridge_length_ft

    # Initial placement:
    # Entire consist sits on lead, facing toward the turntable path.
    #
    # rear = 20
    # front = 148
    # occupied length = 128
    extent = make_extent(
        consist=consist,
        rear_track=lead,
        rear_offset_ft=20.0,
        front_track=lead,
        front_offset_ft=148.0,
        travel_direction=TravelDirection.TOWARD_B,
    )

    initial_footprint = footprint_service.footprint_for_extent(extent)
    assert initial_footprint.track_count == 1
    assert initial_footprint.total_occupied_length_ft == pytest.approx(128.0)
    assert initial_footprint.occupied_track_ids == (lead.track_id,)

    # -----------------------------------------------------------------
    # Phase 1: Move from lead onto approach.
    #
    # Move 80 ft:
    # - rear remains on lead at 100 ft
    # - front crosses from lead:B into approach:B
    # - after moving 28 ft onto the 150 ft approach from the B end,
    #   the stored offset on approach is 122 ft
    #
    # Expected occupancy:
    #   lead + approach
    # -----------------------------------------------------------------
    phase_1 = service.move_extent(
        extent=extent,
        command=MoveCommand.FORWARD,
        distance_ft=80.0,
        turnout_windows_by_key={},
    )

    assert phase_1.actual_distance_ft == pytest.approx(80.0)
    assert phase_1.movement_limited is False
    assert phase_1.stop_reason is MovementBlockReason.NONE

    assert phase_1.new_extent.rear_position.track_id == lead.track_id
    assert phase_1.new_extent.rear_position.offset_ft == pytest.approx(100.0)
    assert phase_1.new_extent.front_position.track_id == approach.track_id
    assert phase_1.new_extent.front_position.offset_ft == pytest.approx(122.0)
    assert phase_1.new_extent.travel_direction is TravelDirection.TOWARD_A

    assert phase_1.footprint.track_count == 2
    assert phase_1.footprint.total_occupied_length_ft == pytest.approx(128.0)
    assert phase_1.footprint.occupied_track_ids == (
        lead.track_id,
        approach.track_id,
    )

    # -----------------------------------------------------------------
    # Phase 2: Align turntable to approach and move fully onto bridge.
    #
    # Move 260 ft from Phase 1 extent:
    # - rear absolute path position: 100 + 260 = 360
    # - front absolute path position: 228 + 260 = 488
    #
    # With path cumulative lengths:
    # - lead end     = 200
    # - approach end = 350
    # - bridge end   = 500
    #
    # So:
    # - rear lands 10 ft onto bridge
    # - front lands 138 ft onto bridge
    #
    # This is the key checkpoint:
    # the entire consist is now fully on the bridge and clear of approach.
    # -----------------------------------------------------------------
    # old code before the align_to correction: turntable.align_to(approach.track_id)
    # Align turntable to approach WITHOUT safety check
    # (initial alignment state)
    turntable.align_to(approach.track_id)

    # Now move onto the bridge
    phase_2 = service.move_extent(
        extent=phase_1.new_extent,
        command=MoveCommand.FORWARD,
        distance_ft=260.0,
        turnout_windows_by_key={},
    )

    assert phase_2.actual_distance_ft == pytest.approx(260.0)
    assert phase_2.movement_limited is False
    assert phase_2.stop_reason is MovementBlockReason.NONE

    assert phase_2.new_extent.rear_position.track_id == bridge.track_id
    assert phase_2.new_extent.rear_position.offset_ft == pytest.approx(10.0)
    assert phase_2.new_extent.front_position.track_id == bridge.track_id
    assert phase_2.new_extent.front_position.offset_ft == pytest.approx(138.0)

    # Existing turntable movement behavior should preserve the forward
    # orientation correctly after the A-to-A entry onto the bridge.
    assert phase_2.new_extent.travel_direction is TravelDirection.TOWARD_B

    assert phase_2.footprint.track_count == 1
    assert phase_2.footprint.total_occupied_length_ft == pytest.approx(128.0)
    assert phase_2.footprint.occupied_track_ids == (bridge.track_id,)

    # -----------------------------------------------------------------
    # Pre-turn validation checkpoint.
    #
    # The turntable should only be rotated after the consist is fully
    # contained on the bridge. This scenario asserts the valid condition
    # now, before re-alignment.
    #
    # TODO:
    # Once production enforcement exists, add a separate scenario test that
    # proves turntable alignment is rejected while the consist still spans
    # approach + bridge (or any other off-bridge overhang case).
    # -----------------------------------------------------------------
    assert phase_2.new_extent.rear_position.track_id == bridge.track_id
    assert phase_2.new_extent.front_position.track_id == bridge.track_id
    assert phase_2.footprint.occupied_track_ids == (bridge.track_id,)
    assert phase_2.footprint.total_occupied_length_ft == pytest.approx(128.0)
    assert consist_length <= turntable.bridge_length_ft

    # -----------------------------------------------------------------
    # Phase 3: Re-align turntable to stall_1 and move off the bridge.
    #
    # Move 40 ft:
    # - rear:  10 -> 50   on bridge
    # - front: 138 -> 178 => 28 ft onto stall_1
    #
    # Expected occupancy:
    #   bridge + stall_1
    # -----------------------------------------------------------------
    # IMPORTANT:
    # This verifies correct outbound turntable footprint behavior.
    # The bridge contribution MUST be:
    #   (bridge.length_ft - rear_offset_ft)
    # not rear_offset_ft.
    #
    # This was previously a bug where total length was undercounted.
    # old code: turntable.align_to(stall_1.track_id)
    turntable.align_to(stall_1.track_id, protected_extent=phase_2.new_extent)

    phase_3 = service.move_extent(
        extent=phase_2.new_extent,
        command=MoveCommand.FORWARD,
        distance_ft=40.0,
        turnout_windows_by_key={},
    )

    assert phase_3.actual_distance_ft == pytest.approx(40.0)
    assert phase_3.movement_limited is False
    assert phase_3.stop_reason is MovementBlockReason.NONE

    assert phase_3.new_extent.rear_position.track_id == bridge.track_id
    assert phase_3.new_extent.rear_position.offset_ft == pytest.approx(50.0)
    assert phase_3.new_extent.front_position.track_id == stall_1.track_id
    assert phase_3.new_extent.front_position.offset_ft == pytest.approx(28.0)
    assert phase_3.new_extent.travel_direction is TravelDirection.TOWARD_B

    assert phase_3.footprint.track_count == 2
    print(phase_3.footprint.occupied_track_ids)
    print(phase_3.footprint.track_count)
    print(phase_3.footprint.total_occupied_length_ft)

    assert phase_3.footprint.total_occupied_length_ft == pytest.approx(128.0)
    assert phase_3.footprint.occupied_track_ids == (
        bridge.track_id,
        stall_1.track_id,
    )


def test_move_onto_turntable_bridge_is_rejected_when_consist_exceeds_bridge_length() -> (
    None
):
    network, lead, approach, bridge, stall_1, turntable, connection = (
        build_turntable_insufficient_capacity_scenario_network()
    )
    service, footprint_service = build_service(
        network,
        turntable_connections=(connection,),
    )

    consist = build_locomotive_boxcar_consist()
    consist_length = consist.operational_length_ft

    assert consist_length == pytest.approx(128.0)
    assert turntable.bridge_length_ft == pytest.approx(100.0)
    assert consist_length > turntable.bridge_length_ft

    extent = make_extent(
        consist=consist,
        rear_track=lead,
        rear_offset_ft=20.0,
        front_track=lead,
        front_offset_ft=148.0,
        travel_direction=TravelDirection.TOWARD_B,
    )

    initial_footprint = footprint_service.footprint_for_extent(extent)
    assert initial_footprint.track_count == 1
    assert initial_footprint.total_occupied_length_ft == pytest.approx(128.0)
    assert initial_footprint.occupied_track_ids == (lead.track_id,)

    # Phase 1: lead -> approach
    phase_1 = service.move_extent(
        extent=extent,
        command=MoveCommand.FORWARD,
        distance_ft=80.0,
        turnout_windows_by_key={},
    )

    assert phase_1.actual_distance_ft == pytest.approx(80.0)
    assert phase_1.movement_limited is False
    assert phase_1.stop_reason is MovementBlockReason.NONE

    assert phase_1.new_extent.rear_position.track_id == lead.track_id
    assert phase_1.new_extent.rear_position.offset_ft == pytest.approx(100.0)
    assert phase_1.new_extent.front_position.track_id == approach.track_id
    assert phase_1.new_extent.front_position.offset_ft == pytest.approx(122.0)
    assert phase_1.new_extent.travel_direction is TravelDirection.TOWARD_A

    assert phase_1.footprint.track_count == 2
    assert phase_1.footprint.total_occupied_length_ft == pytest.approx(128.0)
    assert phase_1.footprint.occupied_track_ids == (
        lead.track_id,
        approach.track_id,
    )

    # Phase 2: align to approach, then attempt move onto bridge
    # old code before align_to correction: turntable.align_to(approach.track_id)
    # Align turntable to approach WITHOUT safety check
    # (initial alignment state)
    turntable.align_to(approach.track_id)

    # Now move onto the bridge
    phase_2 = service.move_extent(
        extent=phase_1.new_extent,
        command=MoveCommand.FORWARD,
        distance_ft=260.0,
        turnout_windows_by_key={},
    )

    assert phase_2.actual_distance_ft == pytest.approx(0.0)
    assert phase_2.movement_limited is True
    assert phase_2.stop_reason is MovementBlockReason.TURNTABLE_BRIDGE_LENGTH_EXCEEDED

    assert phase_2.new_extent == phase_1.new_extent
    assert phase_2.prior_extent == phase_1.new_extent

    assert phase_2.footprint.track_count == 2
    assert phase_2.footprint.total_occupied_length_ft == pytest.approx(128.0)
    assert phase_2.footprint.occupied_track_ids == (
        lead.track_id,
        approach.track_id,
    )
