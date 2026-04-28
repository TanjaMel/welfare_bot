"""
app/api/v1/endpoints/admin_dashboard.py

Population-level analytics for care workers and admins.
Returns aggregated data across all users — never exposes individual
clinical scores directly, always with soft labels.

Mount in api.py:
    from app.api.v1.endpoints.admin_dashboard import router as admin_router
    api_router.include_router(admin_router, prefix="/admin", tags=["Admin Dashboard"])
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, case
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models.user import User
from app.db.models.conversation_message import ConversationMessage
from app.db.models.risk_analysis import RiskAnalysis
from app.db.models.wellbeing_daily_metrics import WellbeingDailyMetrics

router = APIRouter()


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class UserRiskRow(BaseModel):
    user_id: int
    name: str
    latest_risk_level: str
    latest_risk_score: int
    trend: str          # "improving" | "stable" | "worsening" | "no_data"
    last_active: Optional[str]
    days_since_contact: int
    alert: bool         # True if needs attention today

    class Config:
        from_attributes = True


class PopulationSummary(BaseModel):
    total_users: int
    active_today: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    no_data_count: int
    avg_wellbeing_score: Optional[float]
    users_needing_attention: int


class RiskHeatmapPoint(BaseModel):
    date: str
    critical: int
    high: int
    medium: int
    low: int


class AdminDashboardResponse(BaseModel):
    generated_at: str
    summary: PopulationSummary
    users: list[UserRiskRow]
    heatmap: list[RiskHeatmapPoint]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _risk_trend(recent_scores: list[int]) -> str:
    """Compute trend from a list of recent risk scores (oldest first)."""
    if len(recent_scores) < 2:
        return "no_data"
    first_half = recent_scores[:len(recent_scores) // 2]
    second_half = recent_scores[len(recent_scores) // 2:]
    avg_first = sum(first_half) / len(first_half)
    avg_second = sum(second_half) / len(second_half)
    if avg_second < avg_first - 1:
        return "improving"
    if avg_second > avg_first + 1:
        return "worsening"
    return "stable"


def _days_since(dt: Optional[datetime]) -> int:
    if dt is None:
        return 999
    if dt.tzinfo is not None:
        from datetime import timezone
        now = datetime.now(timezone.utc)
    else:
        now = datetime.utcnow()
        dt = dt.replace(tzinfo=None)
    return (now.replace(tzinfo=None) - dt.replace(tzinfo=None)).days


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/dashboard",
    response_model=AdminDashboardResponse,
    summary="Population-level analytics for care workers",
)
def get_admin_dashboard(
    days: int = Query(default=7, ge=1, le=30),
    db: Session = Depends(get_db),
):
    """
    Returns population-level wellbeing and risk analytics.
    Requires admin role — enforced at the frontend; add auth dependency
    when ready (see get_current_admin_user).
    """
    today = date.today()
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    window_start = today - timedelta(days=days)

    # All active users
    users = db.query(User).filter(User.is_active == True).all()
    user_ids = [u.id for u in users]
    user_map = {u.id: u for u in users}

    if not user_ids:
        empty_summary = PopulationSummary(
            total_users=0, active_today=0, critical_count=0,
            high_count=0, medium_count=0, low_count=0,
            no_data_count=0, avg_wellbeing_score=None,
            users_needing_attention=0,
        )
        return AdminDashboardResponse(
            generated_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            summary=empty_summary,
            users=[],
            heatmap=[],
        )

    # Latest risk analysis per user
    latest_risk_subq = (
        db.query(
            RiskAnalysis.user_id,
            func.max(RiskAnalysis.created_at).label("max_created"),
        )
        .filter(RiskAnalysis.user_id.in_(user_ids))
        .group_by(RiskAnalysis.user_id)
        .subquery()
    )

    latest_risks = (
        db.query(RiskAnalysis)
        .join(
            latest_risk_subq,
            (RiskAnalysis.user_id == latest_risk_subq.c.user_id)
            & (RiskAnalysis.created_at == latest_risk_subq.c.max_created),
        )
        .all()
    )
    latest_risk_map = {r.user_id: r for r in latest_risks}

    # Recent risk scores per user (for trend)
    recent_analyses = (
        db.query(RiskAnalysis)
        .filter(
            RiskAnalysis.user_id.in_(user_ids),
            RiskAnalysis.created_at >= window_start,
        )
        .order_by(RiskAnalysis.user_id, RiskAnalysis.created_at)
        .all()
    )
    scores_by_user: dict[int, list[int]] = {}
    for ra in recent_analyses:
        scores_by_user.setdefault(ra.user_id, []).append(ra.risk_score or 0)

    # Last message time per user
    last_msg_subq = (
        db.query(
            ConversationMessage.user_id,
            func.max(ConversationMessage.created_at).label("last_msg"),
        )
        .filter(ConversationMessage.user_id.in_(user_ids))
        .group_by(ConversationMessage.user_id)
        .all()
    )
    last_msg_map = {row.user_id: row.last_msg for row in last_msg_subq}

    # Users active today
    active_today_ids = set(
        db.query(ConversationMessage.user_id)
        .filter(
            ConversationMessage.user_id.in_(user_ids),
            ConversationMessage.created_at >= today_start,
        )
        .distinct()
        .scalars()
        .all()
    )

    # Average wellbeing score (from daily metrics, last 7 days)
    avg_score_result = (
        db.query(func.avg(WellbeingDailyMetrics.overall_wellbeing_score))
        .filter(
            WellbeingDailyMetrics.user_id.in_(user_ids),
            WellbeingDailyMetrics.date >= today - timedelta(days=7),
        )
        .scalar()
    )

    # Build user rows
    user_rows: list[UserRiskRow] = []
    risk_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "no_data": 0}

    for uid in user_ids:
        user = user_map[uid]
        latest = latest_risk_map.get(uid)
        recent_scores = scores_by_user.get(uid, [])
        last_msg = last_msg_map.get(uid)
        days_since = _days_since(last_msg)

        risk_level = latest.risk_level if latest else "no_data"
        risk_score = latest.risk_score if latest else 0
        trend = _risk_trend(recent_scores) if recent_scores else "no_data"

        # Alert if: critical/high risk OR no contact in 2+ days
        alert = risk_level in ("critical", "high") or days_since >= 2

        risk_counts[risk_level if risk_level in risk_counts else "no_data"] += 1

        name = f"{user.first_name} {user.last_name}".strip() or f"User {uid}"
        last_active_str = last_msg.strftime("%b %d, %H:%M") if last_msg else "Never"

        user_rows.append(UserRiskRow(
            user_id=uid,
            name=name,
            latest_risk_level=risk_level,
            latest_risk_score=risk_score,
            trend=trend,
            last_active=last_active_str,
            days_since_contact=days_since,
            alert=alert,
        ))

    # Sort: alerts first, then by risk level severity, then by days since contact
    level_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "no_data": 4}
    user_rows.sort(key=lambda r: (
        0 if r.alert else 1,
        level_order.get(r.latest_risk_level, 4),
        r.days_since_contact,
    ), reverse=False)

    # Heatmap — risk counts per day over window
    heatmap_rows = (
        db.query(
            func.date(RiskAnalysis.created_at).label("day"),
            RiskAnalysis.risk_level,
            func.count(RiskAnalysis.id).label("cnt"),
        )
        .filter(
            RiskAnalysis.user_id.in_(user_ids),
            RiskAnalysis.created_at >= window_start,
        )
        .group_by(func.date(RiskAnalysis.created_at), RiskAnalysis.risk_level)
        .all()
    )

    heatmap_by_date: dict[str, dict[str, int]] = {}
    for row in heatmap_rows:
        d = str(row.day)
        heatmap_by_date.setdefault(d, {"critical": 0, "high": 0, "medium": 0, "low": 0})
        if row.risk_level in heatmap_by_date[d]:
            heatmap_by_date[d][row.risk_level] += row.cnt

    heatmap = []
    for i in range(days):
        d = (window_start.date() + timedelta(days=i)).strftime("%Y-%m-%d")
        counts = heatmap_by_date.get(d, {})
        heatmap.append(RiskHeatmapPoint(
            date=(window_start.date() + timedelta(days=i)).strftime("%b %d"),
            critical=counts.get("critical", 0),
            high=counts.get("high", 0),
            medium=counts.get("medium", 0),
            low=counts.get("low", 0),
        ))

    summary = PopulationSummary(
        total_users=len(user_ids),
        active_today=len(active_today_ids),
        critical_count=risk_counts["critical"],
        high_count=risk_counts["high"],
        medium_count=risk_counts["medium"],
        low_count=risk_counts["low"],
        no_data_count=risk_counts["no_data"],
        avg_wellbeing_score=round(float(avg_score_result), 1) if avg_score_result else None,
        users_needing_attention=sum(1 for r in user_rows if r.alert),
    )

    return AdminDashboardResponse(
        generated_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        summary=summary,
        users=user_rows,
        heatmap=heatmap,
    )
