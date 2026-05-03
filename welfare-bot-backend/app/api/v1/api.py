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
    wellbeing,
)
from app.api.v1.endpoints.admin_dashboard import router as admin_router
from app.api.v1.endpoints.data_quality import router as dq_router
from app.api.v1.endpoints.admin_report import router as report_router
from app.api.v1.endpoints.alert_feedback import router as feedback_router
from app.api.v1.endpoints.ml_insights import router as ml_router


api_router = APIRouter()

api_router.include_router(auth.router,          prefix="/auth",          tags=["auth"])
api_router.include_router(users.router,         prefix="/users",         tags=["users"])
api_router.include_router(care_contacts.router, prefix="/care-contacts", tags=["care-contacts"])
api_router.include_router(checkins.router,      prefix="/checkins",      tags=["checkins"])
api_router.include_router(conversations.router, prefix="/conversations",  tags=["conversations"])
api_router.include_router(risk_analysis.router, prefix="/risk-analysis",  tags=["risk-analysis"])
api_router.include_router(notifications.router, prefix="/notifications",  tags=["notifications"])
api_router.include_router(voice.router,         prefix="/voice",         tags=["voice"])
api_router.include_router(wellbeing.router,     prefix="/wellbeing",      tags=["wellbeing"])
api_router.include_router(admin_router,         prefix="/admin",          tags=["Admin Dashboard"])
api_router.include_router(dq_router,            prefix="/admin/data-quality",         tags=["Data Quality"])
api_router.include_router(report_router,        prefix="/admin",           tags=["Report"])
api_router.include_router(feedback_router,      prefix="/admin",           tags=["ML Feedback"])
api_router.include_router(ml_router,            prefix="/admin",           tags=["ML Insights"])