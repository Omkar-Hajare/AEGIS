import sys
from pathlib import Path

from fastapi import Depends, FastAPI

# Ensure backend directory is in sys.path when imported as backend.app.main
_backend_dir = str(Path(__file__).resolve().parent.parent)
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from api.routes.adaptive import router as adaptive_router
from api.routes.data import router as data_router
from api.routes.telemetry import router as telemetry_router

from app.config import Settings, settings
from app.dependencies import get_settings

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
)

app.include_router(data_router)
app.include_router(telemetry_router)
app.include_router(adaptive_router)


@app.get("/")
def root():
    """Root entrypoint providing service status, docs link, and endpoint discovery."""
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "docs_url": "/docs",
        "endpoints": {
            "health": "/health",
            "runtime_decision": "/adaptive/runtime-decision",
            "decision": "/adaptive/decision",
            "telemetry_observation": "/telemetry/observation",
            "telemetry_workload": "/telemetry/workload",
            "telemetry_system": "/telemetry/system",
            "telemetry_reset": "/telemetry/window/reset",
            "product_data": "/data/product/{product_id}",
            "recommendation_data": "/data/recommendation/{user_id}",
        },
    }


@app.get("/health")
def health_check(current_settings: Settings = Depends(get_settings)):
    return {
        "status": "ok",
        "service": current_settings.app_name,
        "version": current_settings.app_version,
    }
