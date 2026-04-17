from fastapi import APIRouter
from app.core.config import get_settings
router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/config")
def debug_config():
    settings = get_settings()

    return {
        "app_env": settings.app_env,
        "debug": settings.debug,
        "api_v1_prefix": settings.api_v1_prefix,
        "postgres_host": settings.postgres_host,
        "postgres_port": settings.postgres_port,
        "postgres_db": settings.postgres_db,
        "postgres_user": settings.postgres_user,
        "database_url": settings.database_url,
        "openai_model": settings.openai_model,
        "openai_api_key_present": bool(settings.openai_api_key),
    }