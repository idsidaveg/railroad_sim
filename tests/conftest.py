import pytest

from railroad_sim.domain.consist import Consist


@pytest.fixture(autouse=True)
def reset_consist_registry():
    Consist._reset_registry_for_tests()
    yield
    Consist._reset_registry_for_tests()
