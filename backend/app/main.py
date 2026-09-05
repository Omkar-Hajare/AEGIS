import sys
import time
from pathlib import Path

from fastapi import Depends, FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

# Ensure backend directory is in sys.path when imported as backend.app.main
_backend_dir = str(Path(__file__).resolve().parent.parent)
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from api.routes.adaptive import router as adaptive_router
from api.routes.data import cache_manager, router as data_router
from api.routes.telemetry import router as telemetry_router
from metrics.prometheus import (
    BACKEND_LATENCY,
    REQUEST_COUNT,
    REQUEST_LATENCY,
    sync_from_telemetry,
)
from telemetry.collector import telemetry_collector


app = FastAPI(
    title="Adaptive Cache System",
    version="0.1.0",
)


@app.middleware("http")
async def prometheus_middleware(request: Request, call_next):
    """Record HTTP request count and latency for Prometheus."""
    start_time = time.perf_counter()

    response = await call_next(request)

    duration = time.perf_counter() - start_time

    route = request.scope.get("route")
    endpoint = route.path if route else request.url.path

    if endpoint != "/metrics":
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=endpoint,
            status=response.status_code,
        ).inc()

        REQUEST_LATENCY.labels(
            method=request.method,
            endpoint=endpoint,
        ).observe(duration)

    return response


@app.get("/metrics", include_in_schema=False)
async def metrics():
    """Expose Prometheus metrics."""
    sync_from_telemetry(telemetry_collector, cache_manager)
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "Adaptive Cache System",
        "version": "0.1.0",
    }


app.include_router(data_router)
app.include_router(adaptive_router)
app.include_router(telemetry_router)