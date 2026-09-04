from fastapi import Depends, FastAPI

from app.config import Settings, settings
from app.dependencies import get_settings

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
)


@app.get("/health")
def health_check(current_settings: Settings = Depends(get_settings)):
    return {
        "status": "ok",
        "service": current_settings.app_name,
        "version": current_settings.app_version,
    }
