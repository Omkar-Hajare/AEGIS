"""Standard and example platform cost profiles for the Adaptive Cache System.

Provides preconfigured, platform-aware economic profiles for common backend and
cache architectures:
- Default generic profile (preserves baseline defaults)
- PostgreSQL relational database profile
- MySQL relational database profile
- External third-party HTTP API profile

Note:
    All cost figures and profile configurations are simulated, configurable
    economic models intended for algorithmic evaluation, test scenarios, and
    demonstrations. They do NOT represent actual or contractual cloud/vendor
    pricing.
"""

from __future__ import annotations

from backend.cost.cost_profile import CostModelValidationError, CostProfile

DEFAULT_PROFILE: CostProfile = CostProfile(
    name="default",
    backend_cost_per_request=0.0,
    backend_cost_per_ms=1.0,
    cache_memory_cost_per_gb_hour=0.10,
    metadata={
        "description": "Standard baseline profile matching legacy cost defaults",
        "simulated": True,
    },
)

POSTGRESQL_PROFILE: CostProfile = CostProfile(
    name="postgresql",
    backend_cost_per_request=0.002,
    backend_cost_per_ms=0.50,
    cache_memory_cost_per_gb_hour=0.12,
    metadata={
        "description": (
            "Simulated profile for relational PostgreSQL database backend "
            "(connection pool / query dispatch overhead + disk I/O latency)"
        ),
        "platform_type": "relational_database",
        "simulated": True,
    },
)

MYSQL_PROFILE: CostProfile = CostProfile(
    name="mysql",
    backend_cost_per_request=0.0015,
    backend_cost_per_ms=0.60,
    cache_memory_cost_per_gb_hour=0.10,
    metadata={
        "description": (
            "Simulated profile for MySQL database backend "
            "(query parse/execution overhead + row retrieval latency)"
        ),
        "platform_type": "relational_database",
        "simulated": True,
    },
)

EXTERNAL_API_PROFILE: CostProfile = CostProfile(
    name="external_api",
    backend_cost_per_request=0.020,
    backend_cost_per_ms=2.00,
    cache_memory_cost_per_gb_hour=0.15,
    metadata={
        "description": (
            "Simulated profile for metered, rate-limited third-party HTTP API "
            "(per-call billing + network transit/gateway latency)"
        ),
        "platform_type": "external_api",
        "simulated": True,
    },
)

PROFILES: dict[str, CostProfile] = {
    DEFAULT_PROFILE.name: DEFAULT_PROFILE,
    POSTGRESQL_PROFILE.name: POSTGRESQL_PROFILE,
    MYSQL_PROFILE.name: MYSQL_PROFILE,
    EXTERNAL_API_PROFILE.name: EXTERNAL_API_PROFILE,
}


def get_profile(name: str) -> CostProfile:
    """Retrieve a registered CostProfile by name.

    Args:
        name: Name of the cost profile (case-insensitive string).

    Returns:
        The registered CostProfile instance.

    Raises:
        CostModelValidationError: If name is invalid or profile is not found.
    """
    if isinstance(name, bool) or not isinstance(name, str):
        raise CostModelValidationError(
            f"profile name must be a string, got {type(name).__name__}"
        )
    key = name.strip().lower()
    if not key:
        raise CostModelValidationError("profile name must not be empty or whitespace")

    if key in PROFILES:
        return PROFILES[key]

    available = sorted(PROFILES.keys())
    raise CostModelValidationError(
        f"Unknown cost profile {name!r}. Available profiles: {available}"
    )
