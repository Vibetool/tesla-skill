"""Fleet API clients (mock + real)."""
from tesla_skill.config import settings
from tesla_skill.fleet.base import FleetClient
from tesla_skill.fleet.mock import MockFleetClient


def get_client() -> FleetClient:
    """Factory: returns mock or real client based on USE_MOCK env."""
    if settings.use_mock:
        return MockFleetClient()
    # Lazy import — mock mode shouldn't require httpx network at import time
    from tesla_skill.fleet.real import RealFleetClient

    return RealFleetClient()


__all__ = ["FleetClient", "get_client"]
