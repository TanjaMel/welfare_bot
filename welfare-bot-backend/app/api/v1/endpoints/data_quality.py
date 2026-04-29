from __future__ import annotations
from datetime import date, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.services.data_quality import check_user_data_quality, run_population_quality_check, repair_outliers

router = APIRouter()

class MetricQualityOut(BaseModel):
    metric: str
    missing_rate: float
    outlier_count: int
    mean_value: Optional[float]
    quality_score: float

class GapOut(BaseModel):
    start_date: str
    end_date: str
    gap_days: int
    is_concerning: bool

class UserQualityResponse(BaseModel):
    user_id: int
    assessment_date: str
    coverage_rate: float
    overall_quality_score: float
    needs_attention: bool
    issues: list[str]
    suggestions: list[str]
    metric_quality: list[MetricQualityOut]
    gaps: list[GapOut]

class PopulationQualityResponse(BaseModel):
    assessment_date: str
    total_users: int
    users_with_data: int
    users_needing_attention: int
    avg_quality_score: float
    avg_coverage_rate: float
    most_missing_metric: str
    longest_gap_days: int
    user_reports: list[dict]

class RepairResponse(BaseModel):
    mode: str
    rows_affected: int
    total_values_fixed: int
    details: list[dict]

@router.get("/user/{user_id}", response_model=UserQualityResponse, summary="Data quality report for a single user")
def get_user_quality(user_id: int, assessment_date: Optional[date] = Query(default=None), lookback_days: int = Query(default=30, ge=7, le=90), db: Session = Depends(get_db)):
    result = check_user_data_quality(user_id=user_id, db=db, assessment_date=assessment_date, lookback_days=lookback_days)
    return UserQualityResponse(user_id=result.user_id, assessment_date=result.assessment_date, coverage_rate=result.coverage_rate, overall_quality_score=result.overall_quality_score, needs_attention=result.needs_attention, issues=result.issues, suggestions=result.suggestions, metric_quality=[MetricQualityOut(metric=mq.metric, missing_rate=mq.missing_rate, outlier_count=mq.outlier_count, mean_value=mq.mean_value, quality_score=mq.quality_score) for mq in result.metric_quality], gaps=[GapOut(start_date=g.start_date, end_date=g.end_date, gap_days=g.gap_days, is_concerning=g.is_concerning) for g in result.gaps])

@router.get("/population", response_model=PopulationQualityResponse, summary="Population-level data quality report")
def get_population_quality(assessment_date: Optional[date] = Query(default=None), lookback_days: int = Query(default=30, ge=7, le=90), db: Session = Depends(get_db)):
    result = run_population_quality_check(db=db, assessment_date=assessment_date, lookback_days=lookback_days)
    return PopulationQualityResponse(assessment_date=result.assessment_date, total_users=result.total_users, users_with_data=result.users_with_data, users_needing_attention=result.users_needing_attention, avg_quality_score=result.avg_quality_score, avg_coverage_rate=result.avg_coverage_rate, most_missing_metric=result.most_missing_metric, longest_gap_days=result.longest_gap_days, user_reports=result.user_reports)

@router.post("/repair/{user_id}", response_model=RepairResponse, summary="Detect and optionally repair outlier values")
def repair_user_data(user_id: int, dry_run: bool = Query(default=True), lookback_days: int = Query(default=30, ge=1, le=90), assessment_date: Optional[date] = Query(default=None), db: Session = Depends(get_db)):
    from app.db.models.wellbeing_daily_metrics import WellbeingDailyMetrics
    ref_date = assessment_date or date.today()
    start_date = ref_date - timedelta(days=lookback_days - 1)
    rows = db.query(WellbeingDailyMetrics).filter(WellbeingDailyMetrics.user_id == user_id, WellbeingDailyMetrics.date >= start_date, WellbeingDailyMetrics.date <= ref_date).all()
    result = repair_outliers(rows, db, dry_run=dry_run)
    return RepairResponse(**result)
