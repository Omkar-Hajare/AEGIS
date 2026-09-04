import sqlalchemy as sa
from sqlalchemy.orm import Session

from database.models import TelemetryObservationModel
from telemetry.observation import Observation


class TelemetryRepository:
    """Repository for persisting and querying TelemetryObservation records."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def save_observation(self, observation: Observation) -> TelemetryObservationModel:
        """Persist a telemetry Observation snapshot to the database."""
        model = TelemetryObservationModel(
            timestamp=observation.timestamp,
            window_seconds=observation.window_seconds,
            request_rate=observation.request_rate,
            hit_rate=observation.hit_rate,
            miss_rate=observation.miss_rate,
            backend_latency_ms=observation.backend_latency_ms,
            total_requests=observation.total_requests,
            cache_hits=observation.cache_hits,
            cache_misses=observation.cache_misses,
            backend_calls=observation.backend_calls,
            current_window_access_counts=observation.current_window_access_counts,
            previous_window_access_counts=observation.previous_window_access_counts,
        )
        self.session.add(model)
        self.session.flush()
        return model

    def get_recent_observations(self, limit: int = 10) -> list[Observation]:
        """Retrieve recent observations ordered by timestamp descending."""
        stmt = (
            sa.select(TelemetryObservationModel)
            .order_by(TelemetryObservationModel.timestamp.desc())
            .limit(limit)
        )
        models = self.session.scalars(stmt).all()
        return [self._to_domain(m) for m in models]

    @staticmethod
    def _to_domain(model: TelemetryObservationModel) -> Observation:
        """Convert a database model to the domain Observation dataclass."""
        return Observation(
            request_rate=model.request_rate,
            hit_rate=model.hit_rate,
            miss_rate=model.miss_rate,
            backend_latency_ms=model.backend_latency_ms,
            window_seconds=model.window_seconds,
            total_requests=model.total_requests,
            cache_hits=model.cache_hits,
            cache_misses=model.cache_misses,
            backend_calls=model.backend_calls,
            current_window_access_counts=dict(model.current_window_access_counts or {}),
            previous_window_access_counts=dict(model.previous_window_access_counts or {}),
            timestamp=model.timestamp,
        )
