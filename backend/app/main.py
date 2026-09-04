from fastapi import Depends, FastAPI

from api.routes.data import router as data_router
from app.config import Settings, settings
from app.dependencies import get_settings

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
)

app.include_router(data_router)


@app.get("/health")
def health_check(current_settings: Settings = Depends(get_settings)):
    return {
        "status": "ok",
        "service": current_settings.app_name,
        "version": current_settings.app_version,
    }
