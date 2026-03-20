import pytest

from railroad_sim.domain.enums import (
    JunctionType,
    TrackCondition,
    TrackEnd,
    TrackTrafficRule,
    TrackType,
)
from railroad_sim.domain.junction import Junction, JunctionRoute, TrackEndpoint
from railroad_sim.domain.network.rail_network import RailNetwork
from railroad_sim.domain.network.yard_throat_builder import (
    build_single_ladder_throat,
    register_yard_throat,
)
from railroad_sim.domain.track import Track


def _build_track(name: str) -> Track:
    return Track(
        name=name,
        track_type=TrackType.YARD,
        length_ft=500.0,
        condition=TrackCondition.CLEAR,
        traffic_rule=TrackTrafficRule.BIDIRECTIONAL,
    )


def _build_turnout(
    name: str,
    from_track: Track,
    from_end: TrackEnd,
    to_track: Track,
    to_end: TrackEnd,
) -> Junction:
    from_ep = TrackEndpoint(track=from_track, end=from_end)
    to_ep = TrackEndpoint(track=to_track, end=to_end)

    route = JunctionRoute(from_endpoint=from_ep, to_endpoint=to_ep)

    return Junction(
        name=name,
        junction_type=JunctionType.TURNOUT,
        endpoints={from_ep, to_ep},
        routes={route},
        aligned_routes={route},
    )


def test_build_single_ladder_throat_basic_structure() -> None:
    mainline = _build_track("mainline")
    lead = _build_track("lead")
    ad = _build_track("ad_1")
    yard = _build_track("yard_1")
    aux = _build_track("caboose")

    entry = _build_turnout(
        "entry",
        mainline,
        TrackEnd.B,
        lead,
        TrackEnd.A,
    )

    ladder = _build_turnout(
        "ladder_1",
        lead,
        TrackEnd.B,
        ad,
        TrackEnd.A,
    )

    topology = build_single_ladder_throat(
        mainline_track=mainline,
        lead_track=lead,
        entry_junction=entry,
        ladder_junctions=(ladder,),
        ad_tracks=(ad,),
        yard_tracks=(yard,),
        auxiliary_tracks=(aux,),
    )

    assert topology.mainline_track is mainline
    assert topology.lead_track is lead

    assert topology.entry_junction is entry
    assert topology.ladder_junctions == (ladder,)

    assert topology.ad_tracks == (ad,)
    assert topology.yard_tracks == (yard,)
    assert topology.auxiliary_tracks == (aux,)

    assert topology.all_tracks == (mainline, lead, ad, yard, aux)
    assert topology.all_junctions == (entry, ladder)


def test_build_single_ladder_throat_requires_ladder() -> None:
    mainline = _build_track("mainline")
    lead = _build_track("lead")

    entry = _build_turnout(
        "entry",
        mainline,
        TrackEnd.B,
        lead,
        TrackEnd.A,
    )

    with pytest.raises(
        ValueError,
        match="ladder_junctions must contain at least one junction.",
    ):
        build_single_ladder_throat(
            mainline_track=mainline,
            lead_track=lead,
            entry_junction=entry,
            ladder_junctions=(),
        )


def test_build_single_ladder_throat_rejects_duplicate_mainline_and_lead_tracks() -> (
    None
):
    shared = _build_track("shared")
    other = _build_track("other")

    entry = _build_turnout(
        "entry",
        shared,
        TrackEnd.A,
        other,
        TrackEnd.A,
    )

    ladder = _build_turnout(
        "ladder_1",
        other,
        TrackEnd.B,
        shared,
        TrackEnd.B,
    )

    with pytest.raises(
        ValueError,
        match="mainline_track and lead_track must be different tracks.",
    ):
        build_single_ladder_throat(
            mainline_track=shared,
            lead_track=shared,
            entry_junction=entry,
            ladder_junctions=(ladder,),
        )


def test_build_single_ladder_throat_rejects_duplicate_tracks_in_collections() -> None:
    mainline = _build_track("mainline")
    lead = _build_track("lead")
    shared = _build_track("shared")

    entry = _build_turnout(
        "entry",
        mainline,
        TrackEnd.B,
        lead,
        TrackEnd.A,
    )

    ladder = _build_turnout(
        "ladder_1",
        lead,
        TrackEnd.B,
        shared,
        TrackEnd.A,
    )

    with pytest.raises(ValueError, match="Duplicate track detected in yard throat"):
        build_single_ladder_throat(
            mainline_track=mainline,
            lead_track=lead,
            entry_junction=entry,
            ladder_junctions=(ladder,),
            ad_tracks=(shared,),
            yard_tracks=(shared,),
        )


def test_build_single_ladder_throat_rejects_duplicate_junctions() -> None:
    mainline = _build_track("mainline")
    lead = _build_track("lead")
    ad = _build_track("ad_1")

    entry = _build_turnout(
        "entry",
        mainline,
        TrackEnd.B,
        lead,
        TrackEnd.A,
    )

    ladder = _build_turnout(
        "ladder_1",
        lead,
        TrackEnd.B,
        ad,
        TrackEnd.A,
    )

    with pytest.raises(ValueError, match="Duplicate junction detected in yard throat"):
        build_single_ladder_throat(
            mainline_track=mainline,
            lead_track=lead,
            entry_junction=entry,
            ladder_junctions=(ladder, ladder),
            ad_tracks=(ad,),
        )


def test_register_yard_throat_adds_tracks_then_junctions() -> None:
    network = RailNetwork(name="test_network")

    mainline = _build_track("mainline")
    lead = _build_track("lead")
    ad = _build_track("ad_1")

    entry = _build_turnout(
        "entry",
        mainline,
        TrackEnd.B,
        lead,
        TrackEnd.A,
    )

    ladder = _build_turnout(
        "ladder_1",
        lead,
        TrackEnd.B,
        ad,
        TrackEnd.A,
    )

    topology = build_single_ladder_throat(
        mainline_track=mainline,
        lead_track=lead,
        entry_junction=entry,
        ladder_junctions=(ladder,),
        ad_tracks=(ad,),
    )

    register_yard_throat(
        network=network,
        topology=topology,
    )

    assert mainline.track_id in network.tracks
    assert lead.track_id in network.tracks
    assert ad.track_id in network.tracks

    assert entry.junction_id in network.junctions
    assert ladder.junction_id in network.junctions


def test_register_yard_throat_is_idempotent() -> None:
    network = RailNetwork(name="test_network")

    mainline = _build_track("mainline")
    lead = _build_track("lead")
    ad = _build_track("ad_1")

    entry = _build_turnout(
        "entry",
        mainline,
        TrackEnd.B,
        lead,
        TrackEnd.A,
    )

    ladder = _build_turnout(
        "ladder_1",
        lead,
        TrackEnd.B,
        ad,
        TrackEnd.A,
    )

    topology = build_single_ladder_throat(
        mainline_track=mainline,
        lead_track=lead,
        entry_junction=entry,
        ladder_junctions=(ladder,),
        ad_tracks=(ad,),
    )

    register_yard_throat(network=network, topology=topology)
    register_yard_throat(network=network, topology=topology)

    assert len(network.tracks) == 3
    assert len(network.junctions) == 2
