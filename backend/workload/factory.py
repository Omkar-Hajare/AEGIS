from app.config import Settings
from app.config import settings as default_settings

from workload.adapter import BackendAdapter
from workload.amazon_like import AmazonLikeAdapter
from workload.simulated import SimulatedBackendAdapter


def get_backend_adapter(settings: Settings | None = None) -> BackendAdapter:
    """Instantiate and return a BackendAdapter based on the configured DATA_BACKEND."""
    cfg = settings or default_settings
    backend = cfg.data_backend.lower().strip()

    if backend == "simulated":
        return SimulatedBackendAdapter()
    elif backend == "amazon_like":
        return AmazonLikeAdapter()
    else:
        raise ValueError(f"Unsupported data backend: '{cfg.data_backend}'")
