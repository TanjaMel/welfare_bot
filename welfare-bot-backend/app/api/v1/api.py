from fastapi import APIRouter

from app.api.v1.endpoints import (
    care_contacts,
    checkins,
    conversations,
    health,
    notifications,
    risk_analysis,
    users,
)

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(users.router)
api_router.include_router(care_contacts.router)
api_router.include_router(checkins.router)
api_router.include_router(conversations.router)
api_router.include_router(risk_analysis.router)
api_router.include_router(notifications.router)