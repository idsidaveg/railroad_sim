from railroad_sim.domain.consist import Consist
from railroad_sim.domain.enums import (
    JunctionType,
    TrackEnd,
    TrackType,
    TravelDirection,
)
from railroad_sim.domain.junction import Junction, JunctionRoute, TrackEndpoint
from railroad_sim.domain.network.footprint_service import FootprintService
from railroad_sim.domain.network.position_types import ConsistExtent, NetworkPosition
from railroad_sim.domain.network.rail_network import RailNetwork
from railroad_sim.domain.network.turnout_evaluator import (
    TurnoutEvaluator,
    TurnoutWindow,
)
from tests.support.rolling_stock_builders import make_locomotive


def make_simple_network():
    from railroad_sim.domain.track import Track

    main_west = Track(name="Main West", track_type=TrackType.MAINLINE, length_ft=3000.0)
    main_middle = Track(
        name="Main Middle", track_type=TrackType.MAINLINE, length_ft=8000.0
    )
    siding = Track(name="Siding", track_type=TrackType.SIDING, length_ft=8000.0)

    network = RailNetwork(name="Turnout Evaluator Test")
    network.add_track(main_west)
    network.add_track(main_middle)
    network.add_track(siding)

    trunk = TrackEndpoint(track=main_west, end=TrackEnd.B)
    main = TrackEndpoint(track=main_middle, end=TrackEnd.A)
    siding_ep = TrackEndpoint(track=siding, end=TrackEnd.A)

    main_route = JunctionRoute(from_endpoint=trunk, to_endpoint=main)
    siding_route = JunctionRoute(from_endpoint=trunk, to_endpoint=siding_ep)

    junction = Junction(
        name="WEST_TURNOUT",
        junction_type=JunctionType.TURNOUT,
        endpoints={trunk, main, siding_ep},
        routes={main_route, siding_route},
        aligned_routes={main_route},
    )
    network.add_junction(junction)

    return network, {
        "main_west": main_west,
        "main_middle": main_middle,
        "siding": siding,
    }


def make_consist() -> Consist:
    loco = make_locomotive(reporting_mark="TSTX", road_number="1")
    return Consist(anchor=loco)


def test_extent_fouls_west_turnout():
    network, tracks = make_simple_network()
    consist = make_consist()

    extent = ConsistExtent(
        consist=consist,
        rear_position=NetworkPosition(
            track_id=tracks["main_west"].track_id,
            offset_ft=2900.0,
        ),
        front_position=NetworkPosition(
            track_id=tracks["main_middle"].track_id,
            offset_ft=200.0,
        ),
        travel_direction=TravelDirection.TOWARD_B,
    )

    evaluator = TurnoutEvaluator(
        footprint_service=FootprintService(network=network),
        track_key_by_id={str(track.track_id): key for key, track in tracks.items()},
    )

    windows = {
        "west": [
            TurnoutWindow(
                turnout_name="WEST_TURNOUT",
                track_key="main_west",
                start_ft=2850.0,
                end_ft=3000.0,
            ),
            TurnoutWindow(
                turnout_name="WEST_TURNOUT",
                track_key="main_middle",
                start_ft=0.0,
                end_ft=150.0,
            ),
            TurnoutWindow(
                turnout_name="WEST_TURNOUT",
                track_key="siding",
                start_ft=0.0,
                end_ft=150.0,
            ),
        ]
    }

    result = evaluator.evaluate_extent(extent=extent, turnout_windows_by_key=windows)

    assert result["WEST_TURNOUT"].is_fouled is True


def test_extent_clear_of_west_turnout():
    network, tracks = make_simple_network()
    consist = make_consist()

    extent = ConsistExtent(
        consist=consist,
        rear_position=NetworkPosition(
            track_id=tracks["main_middle"].track_id,
            offset_ft=500.0,
        ),
        front_position=NetworkPosition(
            track_id=tracks["main_middle"].track_id,
            offset_ft=1000.0,
        ),
        travel_direction=TravelDirection.TOWARD_B,
    )

    evaluator = TurnoutEvaluator(
        footprint_service=FootprintService(network=network),
        track_key_by_id={str(track.track_id): key for key, track in tracks.items()},
    )

    windows = {
        "west": [
            TurnoutWindow(
                turnout_name="WEST_TURNOUT",
                track_key="main_west",
                start_ft=2850.0,
                end_ft=3000.0,
            ),
            TurnoutWindow(
                turnout_name="WEST_TURNOUT",
                track_key="main_middle",
                start_ft=0.0,
                end_ft=150.0,
            ),
            TurnoutWindow(
                turnout_name="WEST_TURNOUT",
                track_key="siding",
                start_ft=0.0,
                end_ft=150.0,
            ),
        ]
    }

    result = evaluator.evaluate_extent(extent=extent, turnout_windows_by_key=windows)

    assert result["WEST_TURNOUT"].is_fouled is False
