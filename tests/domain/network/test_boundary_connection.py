from uuid import UUID, uuid4

import pytest

from railroad_sim.domain.enums import TrackEnd, TrackType
from railroad_sim.domain.junction import TrackEndpoint
from railroad_sim.domain.network.boundary_connection import BoundaryConnection
from railroad_sim.domain.track import Track


def make_track(name: str) -> Track:
    return Track(
        name=name,
        track_type=TrackType.MAINLINE,
        length_ft=1000,
    )


def test_boundary_connection_creation_with_required_fields():
    local_track = make_track("Main 1")
    local_endpoint = TrackEndpoint(track=local_track, end=TrackEnd.B)

    remote_network_id = uuid4()
    remote_track_id = uuid4()

    connection = BoundaryConnection(
        local_endpoint=local_endpoint,
        remote_network_id=remote_network_id,
        remote_track_id=remote_track_id,
        remote_end=TrackEnd.A,
    )

    assert connection.local_endpoint == local_endpoint
    assert connection.remote_network_id == remote_network_id
    assert connection.remote_track_id == remote_track_id
    assert connection.remote_end == TrackEnd.A
    assert connection.name is None


def test_boundary_connection_generates_connection_id_by_default():
    local_track = make_track("Main 1")
    local_endpoint = TrackEndpoint(track=local_track, end=TrackEnd.B)

    connection = BoundaryConnection(
        local_endpoint=local_endpoint,
        remote_network_id=uuid4(),
        remote_track_id=uuid4(),
        remote_end=TrackEnd.A,
    )

    assert isinstance(connection.connection_id, UUID)


def test_boundary_connection_accepts_explicit_connection_id():
    local_track = make_track("Main 1")
    local_endpoint = TrackEndpoint(track=local_track, end=TrackEnd.B)
    explicit_id = uuid4()

    connection = BoundaryConnection(
        local_endpoint=local_endpoint,
        remote_network_id=uuid4(),
        remote_track_id=uuid4(),
        remote_end=TrackEnd.A,
        connection_id=explicit_id,
    )

    assert connection.connection_id == explicit_id


def test_boundary_connection_accepts_name():
    local_track = make_track("Main 1")
    local_endpoint = TrackEndpoint(track=local_track, end=TrackEnd.B)

    connection = BoundaryConnection(
        local_endpoint=local_endpoint,
        remote_network_id=uuid4(),
        remote_track_id=uuid4(),
        remote_end=TrackEnd.A,
        name="Pacific North to Canada",
    )

    assert connection.name == "Pacific North to Canada"


def test_boundary_connection_rejects_blank_name():
    local_track = make_track("Main 1")
    local_endpoint = TrackEndpoint(track=local_track, end=TrackEnd.B)

    with pytest.raises(
        ValueError,
        match="BoundaryConnection name must not be blank if provided.",
    ):
        BoundaryConnection(
            local_endpoint=local_endpoint,
            remote_network_id=uuid4(),
            remote_track_id=uuid4(),
            remote_end=TrackEnd.A,
            name="   ",
        )
