from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from railroad_sim.domain.enums import JunctionType, TrackEnd

if TYPE_CHECKING:
    from railroad_sim.domain.track import Track


@dataclass(frozen=True, slots=True)
class TrackEndpoint:
    """Reference to one physical end of one track segment."""

    track: Track
    end: TrackEnd

    def __post_init__(self) -> None:
        if not self.track.name.strip():
            raise ValueError("TrackEndpoint requires a track with a non-blank name.")

    def __hash__(self) -> int:
        return hash((self.track.track_id, self.end))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TrackEndpoint):
            return NotImplemented
        return self.track.track_id == other.track.track_id and self.end == other.end


@dataclass(frozen=True, slots=True)
class JunctionRoute:
    """A legal route through a junction between two distinct endpoints."""

    from_endpoint: TrackEndpoint
    to_endpoint: TrackEndpoint

    def __post_init__(self) -> None:
        if self.from_endpoint == self.to_endpoint:
            raise ValueError("A junction route cannot connect an endpoint to itself.")

        if self.from_endpoint.track.track_id == self.to_endpoint.track.track_id:
            raise ValueError(
                "A junction route must connect two different tracks, not two ends of the same track."
            )

    def connects(self, endpoint_a: TrackEndpoint, endpoint_b: TrackEndpoint) -> bool:
        """Return True if this route connects the two endpoints in either order."""
        return (
            self.from_endpoint == endpoint_a and self.to_endpoint == endpoint_b
        ) or (self.from_endpoint == endpoint_b and self.to_endpoint == endpoint_a)

    def includes(self, endpoint: TrackEndpoint) -> bool:
        """Return True if the endpoint participates in this route."""
        return endpoint == self.from_endpoint or endpoint == self.to_endpoint

    def other_endpoint(self, endpoint: TrackEndpoint) -> TrackEndpoint:
        """Return the opposite endpoint for a route member."""
        if endpoint == self.from_endpoint:
            return self.to_endpoint
        if endpoint == self.to_endpoint:
            return self.from_endpoint
        raise ValueError("Endpoint is not part of this route.")


@dataclass(slots=True)
class Junction:
    """Connection topology between track endpoints.

    A Junction does not represent track length or occupancy. It represents how
    track ends connect and which routes through the connection are possible
    and currently aligned.
    """

    name: str
    junction_type: JunctionType
    endpoints: set[TrackEndpoint]
    routes: set[JunctionRoute]
    aligned_routes: set[JunctionRoute] = field(default_factory=set)
    junction_id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("junction name must not be blank")

        if len(self.endpoints) < 2:
            raise ValueError("A junction must connect at least two track endpoints.")

        self._validate_routes_use_known_endpoints()
        self._validate_aligned_routes_are_known()
        self._validate_routes_have_unique_endpoint_membership()

    def connects(self, endpoint: TrackEndpoint) -> bool:
        """Return True if the endpoint belongs to this junction."""
        return endpoint in self.endpoints

    def can_route(
        self,
        from_endpoint: TrackEndpoint,
        to_endpoint: TrackEndpoint,
    ) -> bool:
        """Return True if the junction defines a route between the endpoints."""
        return any(route.connects(from_endpoint, to_endpoint) for route in self.routes)

    def available_routes_from(self, endpoint: TrackEndpoint) -> list[JunctionRoute]:
        """Return all defined routes that include the given endpoint."""
        if endpoint not in self.endpoints:
            raise ValueError(f"Endpoint is not part of junction '{self.name}'.")

        return [route for route in self.routes if route.includes(endpoint)]

    def is_route_aligned(
        self,
        from_endpoint: TrackEndpoint,
        to_endpoint: TrackEndpoint,
    ) -> bool:
        """Return True if the route exists and is currently aligned."""
        return any(
            route.connects(from_endpoint, to_endpoint) for route in self.aligned_routes
        )

    def align_route(
        self,
        from_endpoint: TrackEndpoint,
        to_endpoint: TrackEndpoint,
    ) -> None:
        """Align exactly one route between the given endpoints.

        First-version rule:
        - only one aligned route is kept at a time
        - the requested route must already exist in self.routes
        """
        route = self._find_route(from_endpoint, to_endpoint)
        if route is None:
            raise ValueError(
                f"No route exists between the requested endpoints in junction '{self.name}'."
            )

        self.aligned_routes = {route}

    def clear_alignment(self) -> None:
        """Clear all aligned routes."""
        self.aligned_routes.clear()

    def aligned_routes_from(self, endpoint: TrackEndpoint) -> list[JunctionRoute]:
        """Return aligned routes that include the given endpoint."""
        if endpoint not in self.endpoints:
            raise ValueError(f"Endpoint is not part of junction '{self.name}'.")

        return [route for route in self.aligned_routes if route.includes(endpoint)]

    def connected_endpoints_for(self, endpoint: TrackEndpoint) -> list[TrackEndpoint]:
        """Return the endpoints reachable from the given endpoint by any route."""
        return [
            route.other_endpoint(endpoint)
            for route in self.available_routes_from(endpoint)
        ]

    def _find_route(
        self,
        from_endpoint: TrackEndpoint,
        to_endpoint: TrackEndpoint,
    ) -> JunctionRoute | None:
        for route in self.routes:
            if route.connects(from_endpoint, to_endpoint):
                return route
        return None

    def _validate_routes_use_known_endpoints(self) -> None:
        for route in self.routes:
            if route.from_endpoint not in self.endpoints:
                raise ValueError(
                    f"Route endpoint {route.from_endpoint} is not registered on junction '{self.name}'."
                )
            if route.to_endpoint not in self.endpoints:
                raise ValueError(
                    f"Route endpoint {route.to_endpoint} is not registered on junction '{self.name}'."
                )

    def _validate_aligned_routes_are_known(self) -> None:
        for route in self.aligned_routes:
            if route not in self.routes:
                raise ValueError(
                    f"Aligned route {route} is not part of junction '{self.name}'."
                )

    def _validate_routes_have_unique_endpoint_membership(self) -> None:
        seen: set[tuple[TrackEndpoint, TrackEndpoint]] = set()

        for route in self.routes:
            left = route.from_endpoint
            right = route.to_endpoint

            if self._endpoint_sort_key(left) <= self._endpoint_sort_key(right):
                ordered = (left, right)
            else:
                ordered = (right, left)

            if ordered in seen:
                raise ValueError(f"Duplicate route detected in junction '{self.name}'.")
            seen.add(ordered)

    @staticmethod
    def _endpoint_sort_key(endpoint: TrackEndpoint) -> tuple[str, str]:
        return (str(endpoint.track.track_id), endpoint.end.value)
