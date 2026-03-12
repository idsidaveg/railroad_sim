import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from railroad_sim.domain.enums import JunctionType, TrackEnd, TrackType
from railroad_sim.domain.junction import Junction, JunctionRoute, TrackEndpoint
from railroad_sim.domain.network.rail_network import RailNetwork
from railroad_sim.domain.track import Track


def build_debug_network():
    network = RailNetwork(name="Pacific North")

    track_a = Track(name="Main 1", track_type=TrackType.MAINLINE, length_ft=1000)
    track_b = Track(name="Main 2", track_type=TrackType.MAINLINE, length_ft=1000)

    network.add_track(track_a)
    network.add_track(track_b)

    endpoint_a = TrackEndpoint(track=track_a, end=TrackEnd.B)
    endpoint_b = TrackEndpoint(track=track_b, end=TrackEnd.A)

    route = JunctionRoute(from_endpoint=endpoint_a, to_endpoint=endpoint_b)

    junction = Junction(
        name="JCT-1",
        junction_type=JunctionType.CONNECTION,
        endpoints={endpoint_a, endpoint_b},
        routes={route},
    )

    network.add_junction(junction)

    return network


if __name__ == "__main__":
    network = build_debug_network()

    print(network.topology_summary())
    print()
    print(network.graph_debugger_summary())
