from fastapi import APIRouter
from app.api.v1.endpoints import (
    auth,
    users,
    care_contacts,
    checkins,
    conversations,
    risk_analysis,
    notifications,
    voice,
)

api_router = APIRouter()

api_router.include_router(auth.router,          prefix="/auth",          tags=["auth"])
api_router.include_router(users.router,         prefix="/users",         tags=["users"])
api_router.include_router(care_contacts.router, prefix="/care-contacts", tags=["care-contacts"])
api_router.include_router(checkins.router,      prefix="/checkins",      tags=["checkins"])
api_router.include_router(conversations.router, prefix="/conversations",  tags=["conversations"])
api_router.include_router(risk_analysis.router, prefix="/risk-analysis",  tags=["risk-analysis"])
api_router.include_router(notifications.router, prefix="/notifications",  tags=["notifications"])
api_router.include_router(voice.router,         prefix="/voice",         tags=["voice"])