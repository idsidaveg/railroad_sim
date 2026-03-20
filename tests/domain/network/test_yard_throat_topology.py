from railroad_sim.domain.enums import (
    JunctionType,
    TrackCondition,
    TrackEnd,
    TrackTrafficRule,
    TrackType,
)
from railroad_sim.domain.junction import Junction, JunctionRoute, TrackEndpoint
from railroad_sim.domain.network.yard_throat_topology import YardThroatTopology
from railroad_sim.domain.track import Track


def test_yard_throat_topology_groups_tracks_and_junctions() -> None:
    mainline = Track(
        name="mainline",
        track_type=TrackType.MAINLINE,
        length_ft=1000.0,
        condition=TrackCondition.CLEAR,
        traffic_rule=TrackTrafficRule.BIDIRECTIONAL,
    )
    lead = Track(
        name="yard_lead",
        track_type=TrackType.YARD,
        length_ft=600.0,
        condition=TrackCondition.CLEAR,
        traffic_rule=TrackTrafficRule.BIDIRECTIONAL,
    )
    ad_1 = Track(
        name="ad_1",
        track_type=TrackType.YARD,
        length_ft=500.0,
        condition=TrackCondition.CLEAR,
        traffic_rule=TrackTrafficRule.BIDIRECTIONAL,
    )
    yard_1 = Track(
        name="yard_1",
        track_type=TrackType.YARD,
        length_ft=450.0,
        condition=TrackCondition.CLEAR,
        traffic_rule=TrackTrafficRule.BIDIRECTIONAL,
    )
    caboose_1 = Track(
        name="caboose_1",
        track_type=TrackType.YARD,
        length_ft=150.0,
        condition=TrackCondition.CLEAR,
        traffic_rule=TrackTrafficRule.BIDIRECTIONAL,
    )

    # Entry junction: mainline:B <-> yard_lead:A
    mainline_b = TrackEndpoint(track=mainline, end=TrackEnd.B)
    lead_a = TrackEndpoint(track=lead, end=TrackEnd.A)
    entry_route = JunctionRoute(from_endpoint=mainline_b, to_endpoint=lead_a)
    entry_junction = Junction(
        name="entry_junction",
        junction_type=JunctionType.TURNOUT,
        endpoints={mainline_b, lead_a},
        routes={entry_route},
        aligned_routes={entry_route},
    )

    # Ladder junction: yard_lead:B <-> ad_1:A
    lead_b = TrackEndpoint(track=lead, end=TrackEnd.B)
    ad_1_a = TrackEndpoint(track=ad_1, end=TrackEnd.A)
    ladder_route = JunctionRoute(from_endpoint=lead_b, to_endpoint=ad_1_a)
    ladder_junction = Junction(
        name="ladder_junction_1",
        junction_type=JunctionType.TURNOUT,
        endpoints={lead_b, ad_1_a},
        routes={ladder_route},
        aligned_routes={ladder_route},
    )

    topology = YardThroatTopology(
        mainline_track=mainline,
        lead_track=lead,
        entry_junction=entry_junction,
        ladder_junctions=(ladder_junction,),
        ad_tracks=(ad_1,),
        yard_tracks=(yard_1,),
        auxiliary_tracks=(caboose_1,),
        all_tracks=(mainline, lead, ad_1, yard_1, caboose_1),
        all_junctions=(entry_junction, ladder_junction),
    )

    assert topology.mainline_track is mainline
    assert topology.lead_track is lead

    assert topology.entry_junction is entry_junction
    assert topology.entry_junction.connects(mainline_b)
    assert topology.entry_junction.connects(lead_a)
    assert topology.entry_junction.can_route(mainline_b, lead_a)
    assert topology.entry_junction.is_route_aligned(mainline_b, lead_a)

    assert topology.ladder_junctions == (ladder_junction,)
    assert topology.ladder_junctions[0].connects(lead_b)
    assert topology.ladder_junctions[0].connects(ad_1_a)
    assert topology.ladder_junctions[0].can_route(lead_b, ad_1_a)
    assert topology.ladder_junctions[0].is_route_aligned(lead_b, ad_1_a)

    assert topology.ad_tracks == (ad_1,)
    assert topology.yard_tracks == (yard_1,)
    assert topology.auxiliary_tracks == (caboose_1,)
    assert topology.all_tracks == (mainline, lead, ad_1, yard_1, caboose_1)
    assert topology.all_junctions == (entry_junction, ladder_junction)
