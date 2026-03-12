from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4

from railroad_sim.domain.junction import Junction, TrackEndpoint
from railroad_sim.domain.network.boundary_connection import BoundaryConnection
from railroad_sim.domain.track import Track


@dataclass(slots=True)
class RailNetwork:
    """
    Represents one connected railroad infrastructure network.

    Owns tracks, junctions, and external boundary connections.
    """

    name: str

    tracks: dict[UUID, Track] = field(default_factory=dict)
    junctions: dict[UUID, Junction] = field(default_factory=dict)
    boundary_connections: dict[UUID, BoundaryConnection] = field(default_factory=dict)

    network_id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("RailNetwork name must not be blank.")

    # ------------------------------------------------
    # Track Management
    # ------------------------------------------------

    def add_track(self, track: Track) -> None:
        if track.track_id in self.tracks:
            raise ValueError(
                f"Track with id {track.track_id} already exists in network '{self.name}'."
            )

        self.tracks[track.track_id] = track

    def get_track(self, track_id: UUID) -> Track:
        try:
            return self.tracks[track_id]
        except KeyError:
            raise ValueError(f"Track id {track_id} not found in network '{self.name}'.")

    # ------------------------------------------------
    # Junction Management
    # ------------------------------------------------

    def add_junction(self, junction: Junction) -> None:
        if junction.junction_id in self.junctions:
            raise ValueError(
                f"Junction with id {junction.junction_id} already exists in network '{self.name}'."
            )

        for endpoint in junction.endpoints:
            if endpoint.track.track_id not in self.tracks:
                raise ValueError(
                    f"Junction '{junction.name}' references track "
                    f"{endpoint.track.track_id} which is not registered "
                    f"in network '{self.name}'."
                )

        self.junctions[junction.junction_id] = junction

    def get_junction(self, junction_id: UUID) -> Junction:
        try:
            return self.junctions[junction_id]
        except KeyError:
            raise ValueError(
                f"Junction id {junction_id} not found in network '{self.name}'."
            )

    def junctions_for_track(self, track_id: UUID) -> list[Junction]:
        """Return all junctions that include the given track."""
        if track_id not in self.tracks:
            raise ValueError(f"Track id {track_id} not found in network '{self.name}'.")

        return [
            junction
            for junction in self.junctions.values()
            if any(
                endpoint.track.track_id == track_id for endpoint in junction.endpoints
            )
        ]

    def junctions_for_endpoint(self, endpoint: TrackEndpoint) -> list[Junction]:
        """Return all junctions that include the given endpoint."""
        if endpoint.track.track_id not in self.tracks:
            raise ValueError(
                f"Endpoint track {endpoint.track.track_id} is not registered in network '{self.name}'."
            )

        return [
            junction
            for junction in self.junctions.values()
            if endpoint in junction.endpoints
        ]

    def connected_tracks(self, track_id: UUID) -> list[Track]:
        """Return distinct tracks directly reachable through junction routes."""
        if track_id not in self.tracks:
            raise ValueError(f"Track id {track_id} not found in network '{self.name}'.")

        connected: dict[UUID, Track] = {}

        for junction in self.junctions_for_track(track_id):
            for route in junction.routes:
                from_track = route.from_endpoint.track
                to_track = route.to_endpoint.track

                if from_track.track_id == track_id and to_track.track_id != track_id:
                    connected[to_track.track_id] = to_track
                elif to_track.track_id == track_id and from_track.track_id != track_id:
                    connected[from_track.track_id] = from_track

        return list(connected.values())

    # ------------------------------------------------
    # Boundary Connections
    # ------------------------------------------------

    def add_boundary_connection(self, connection: BoundaryConnection) -> None:
        if connection.connection_id in self.boundary_connections:
            raise ValueError(
                f"BoundaryConnection {connection.connection_id} already exists."
            )

        local_track_id = connection.local_endpoint.track.track_id

        if local_track_id not in self.tracks:
            raise ValueError(
                f"Boundary connection references track {local_track_id} "
                f"which is not registered in network '{self.name}'."
            )

        self.boundary_connections[connection.connection_id] = connection

    # ------------------------------------------------
    # Queries
    # ------------------------------------------------

    def boundary_connections_for_track(
        self, track_id: UUID
    ) -> list[BoundaryConnection]:
        """Return boundary connections associated with a given track."""
        return [
            conn
            for conn in self.boundary_connections.values()
            if conn.local_endpoint.track.track_id == track_id
        ]

    def boundary_connections_for_endpoint(
        self,
        endpoint: TrackEndpoint,
    ) -> list[BoundaryConnection]:
        """Return boundary connections associated with a specific endpoint."""
        return [
            conn
            for conn in self.boundary_connections.values()
            if conn.local_endpoint == endpoint
        ]

    def topology_summary(self) -> str:
        """Return a human-readable summary of the network topology."""

        lines: list[str] = []

        lines.append(f"RailNetwork: {self.name}")
        lines.append("")

        # ----------------------------
        # Tracks
        # ----------------------------

        lines.append("Tracks")
        lines.append("------")

        for track in self.tracks.values():
            lines.append(f"{track.name} (A,B)")

        lines.append("")

        # ----------------------------
        # Junctions
        # ----------------------------

        lines.append("Junctions")
        lines.append("---------")

        for junction in self.junctions.values():
            lines.append(junction.name)

            for route in junction.routes:
                left = route.from_endpoint
                right = route.to_endpoint

                lines.append(
                    f"  {left.track.name}:{left.end.value}  <->  "
                    f"{right.track.name}:{right.end.value}"
                )

            lines.append("")

        # ----------------------------
        # Connectivity
        # ----------------------------

        lines.append("Connectivity")
        lines.append("------------")

        for track in self.tracks.values():
            connected = self.connected_tracks(track.track_id)

            for other in connected:
                lines.append(f"{track.name} -> {other.name}")

        return "\n".join(lines)

    def graph_edges(self) -> list[tuple[str, str, str]]:
        """Return directed graph edges for debugging.

        Each tuple is:
            (from_node, to_node, label)

        Where:
        - from_node and to_node are endpoint strings like 'Main 1:B'
        - label identifies the source of the edge, such as a junction or boundary
        """
        edges: list[tuple[str, str, str]] = []

        for junction in self.junctions.values():
            for route in junction.routes:
                left = route.from_endpoint
                right = route.to_endpoint

                left_node = self._endpoint_label(left)
                right_node = self._endpoint_label(right)
                label = f"junction:{junction.name}"

                edges.append((left_node, right_node, label))
                edges.append((right_node, left_node, label))

        for connection in self.boundary_connections.values():
            local_node = self._endpoint_label(connection.local_endpoint)
            remote_node = (
                f"remote:{connection.remote_network_id}/"
                f"{connection.remote_track_id}:"
                f"{connection.remote_end.value}"
            )

            edges.append((local_node, remote_node, "boundary"))

        return edges

    def graph_debugger_summary(self) -> str:
        """Return a detailed endpoint-level graph summary for debugging."""
        lines: list[str] = []

        lines.append(f"RailNetwork Graph: {self.name}")
        lines.append("")

        lines.append("Endpoints")
        lines.append("---------")

        endpoint_labels: set[str] = set()

        for track in self.tracks.values():
            endpoint_labels.add(f"{track.name}:A")
            endpoint_labels.add(f"{track.name}:B")

        for label in sorted(endpoint_labels):
            lines.append(label)

        lines.append("")

        lines.append("Edges")
        lines.append("-----")

        edges = self.graph_edges()
        junction_edges = [edge for edge in edges if edge[2].startswith("junction:")]
        boundary_edges = [edge for edge in edges if edge[2] == "boundary"]

        for from_node, to_node, label in sorted(junction_edges):
            lines.append(f"{from_node} -> {to_node} [{label}]")

        lines.append("")

        lines.append("Boundary Edges")
        lines.append("--------------")

        if boundary_edges:
            for from_node, to_node, label in sorted(boundary_edges):
                lines.append(f"{from_node} -> {to_node} [{label}]")
        else:
            lines.append("(none)")

        return "\n".join(lines)

    @staticmethod
    def _endpoint_label(endpoint: TrackEndpoint) -> str:
        """Return a short human-readable label for a track endpoint."""
        return f"{endpoint.track.name}:{endpoint.end.value}"
