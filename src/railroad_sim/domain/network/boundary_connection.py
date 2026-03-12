from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4

from railroad_sim.domain.enums import TrackEnd
from railroad_sim.domain.junction import TrackEndpoint


@dataclass(slots=True)
class BoundaryConnection:
    """
    Represents a connection between this RailNetwork and another RailNetwork.

    The remote side is referenced only by IDs so that the remote network
    does not need to be loaded in memory.
    """

    local_endpoint: TrackEndpoint

    remote_network_id: UUID
    remote_track_id: UUID
    remote_end: TrackEnd

    name: str | None = None
    connection_id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if self.name is not None and not self.name.strip():
            raise ValueError("BoundaryConnection name must not be blank if provided.")
