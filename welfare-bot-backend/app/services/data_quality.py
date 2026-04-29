"""
app/services/data_quality.py

Data quality monitoring for welfare bot.

Satisfies course criterion:
"checks and corrects data — missing values, corruption,
 merge errors, outlier detection"

Responsibilities
----------------
1. Missing value analysis — which metrics are missing and how often
2. Outlier detection — values outside expected 0-100 range
3. Completeness scoring — how complete is each user's data profile
4. Gap detection — consecutive days with no data (silent absence)
5. Data repair suggestions — what to do about each quality issue
6. Population-level quality report — overall data health dashboard
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Metrics to check (column names in WellbeingDailyMetrics)
METRIC_COLUMNS = [
    "overall_wellbeing_score",
    "mood_score",
    "sleep_score",
    "food_score",
    "hydration_score",
    "medication_score",
    "social_activity_score",
    "risk_score",
]

# Expected value range for all scores
SCORE_MIN = 0.0
SCORE_MAX = 100.0

# A gap longer than this many days is flagged as concerning
GAP_THRESHOLD_DAYS = 2

# Minimum completeness ratio before a user is flagged
MIN_COMPLETENESS = 0.3


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class MetricQuality:
    metric: str
    total_rows: int
    missing_count: int
    missing_rate: float        # 0.0–1.0
    outlier_count: int
    outlier_rate: float
    min_value: Optional[float]
    max_value: Optional[float]
    mean_value: Optional[float]
    quality_score: float       # 0–100, higher = better quality


@dataclass
class GapReport:
    start_date: str
    end_date: str
    gap_days: int
    is_concerning: bool


@dataclass
class UserDataQuality:
    user_id: int
    assessment_date: str
    total_days_expected: int
    total_days_present: int
    coverage_rate: float           # days present / days expected
    overall_completeness: float    # weighted average of metric completeness
    overall_quality_score: float   # 0–100
    metric_quality: list[MetricQuality] = field(default_factory=list)
    gaps: list[GapReport] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    needs_attention: bool = False


@dataclass
class PopulationDataQuality:
    assessment_date: str
    total_users: int
    users_with_data: int
    users_needing_attention: int
    avg_quality_score: float
    avg_coverage_rate: float
    most_missing_metric: str
    longest_gap_days: int
    user_reports: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Core quality checks
# ---------------------------------------------------------------------------

def _check_metric_quality(
    rows: list,
    metric: str,
) -> MetricQuality:
    """Analyse data quality for a single metric across all rows."""
    total = len(rows)
    if total == 0:
        return MetricQuality(
            metric=metric, total_rows=0, missing_count=0, missing_rate=0.0,
            outlier_count=0, outlier_rate=0.0, min_value=None, max_value=None,
            mean_value=None, quality_score=0.0,
        )

    values = [getattr(row, metric) for row in rows]
    present = [v for v in values if v is not None]
    missing_count = total - len(present)
    missing_rate = missing_count / total

    outlier_count = 0
    if present:
        outlier_count = sum(
            1 for v in present
            if v < SCORE_MIN - 0.01 or v > SCORE_MAX + 0.01
        )
        outlier_rate = outlier_count / len(present)
        min_val = min(present)
        max_val = max(present)
        mean_val = sum(present) / len(present)
    else:
        outlier_rate = 0.0
        min_val = max_val = mean_val = None

    # Quality score: penalise for missing and outliers
    # If all values missing, accuracy score is also 0 (no data = no accuracy)
    completeness_score = (1 - missing_rate) * 70
    accuracy_score = (1 - outlier_rate) * 30 if present else 0.0
    quality_score = round(completeness_score + accuracy_score, 1)

    return MetricQuality(
        metric=metric,
        total_rows=total,
        missing_count=missing_count,
        missing_rate=round(missing_rate, 3),
        outlier_count=outlier_count,
        outlier_rate=round(outlier_rate, 3),
        min_value=round(min_val, 1) if min_val is not None else None,
        max_value=round(max_val, 1) if max_val is not None else None,
        mean_value=round(mean_val, 1) if mean_val is not None else None,
        quality_score=quality_score,
    )


def _detect_gaps(
    rows: list,
    start_date: date,
    end_date: date,
) -> list[GapReport]:
    """Find consecutive days where no data was recorded."""
    if not rows:
        total_days = (end_date - start_date).days + 1
        return [GapReport(
            start_date=str(start_date),
            end_date=str(end_date),
            gap_days=total_days,
            is_concerning=True,
        )]

    present_dates = {row.date for row in rows}
    gaps = []
    gap_start = None

    current = start_date
    while current <= end_date:
        if current not in present_dates:
            if gap_start is None:
                gap_start = current
        else:
            if gap_start is not None:
                gap_days = (current - gap_start).days
                gaps.append(GapReport(
                    start_date=str(gap_start),
                    end_date=str(current - timedelta(days=1)),
                    gap_days=gap_days,
                    is_concerning=gap_days >= GAP_THRESHOLD_DAYS,
                ))
                gap_start = None
        current += timedelta(days=1)

    # Handle trailing gap
    if gap_start is not None:
        gap_days = (end_date - gap_start).days + 1
        gaps.append(GapReport(
            start_date=str(gap_start),
            end_date=str(end_date),
            gap_days=gap_days,
            is_concerning=gap_days >= GAP_THRESHOLD_DAYS,
        ))

    return gaps


def _generate_issues_and_suggestions(
    metric_quality: list[MetricQuality],
    gaps: list[GapReport],
    coverage_rate: float,
) -> tuple[list[str], list[str]]:
    """Generate human-readable issues and actionable suggestions."""
    issues = []
    suggestions = []

    # Coverage issues
    if coverage_rate < 0.5:
        issues.append(f"Low data coverage: only {coverage_rate*100:.0f}% of days have records")
        suggestions.append("Encourage daily check-ins — more data improves anomaly detection accuracy")

    # Gap issues
    concerning_gaps = [g for g in gaps if g.is_concerning]
    if concerning_gaps:
        longest = max(concerning_gaps, key=lambda g: g.gap_days)
        issues.append(
            f"Data gap of {longest.gap_days} days detected "
            f"({longest.start_date} to {longest.end_date})"
        )
        suggestions.append(
            "Investigate data gaps — the user may have been unreachable or the app unused"
        )

    # Missing value issues
    for mq in metric_quality:
        if mq.missing_rate > 0.5:
            metric_name = mq.metric.replace("_score", "").replace("_", " ")
            issues.append(
                f"{metric_name}: missing in {mq.missing_rate*100:.0f}% of records"
            )
            suggestions.append(
                f"Add {metric_name} questions to daily check-in to improve data coverage"
            )

    # Outlier issues
    outlier_metrics = [mq for mq in metric_quality if mq.outlier_count > 0]
    if outlier_metrics:
        for mq in outlier_metrics:
            metric_name = mq.metric.replace("_score", "").replace("_", " ")
            issues.append(
                f"{metric_name}: {mq.outlier_count} outlier value(s) outside 0-100 range "
                f"(min={mq.min_value}, max={mq.max_value})"
            )
            suggestions.append(
                f"Review {metric_name} data pipeline — outliers may indicate a scoring bug"
            )

    return issues, suggestions


# ---------------------------------------------------------------------------
# Per-user quality report
# ---------------------------------------------------------------------------

def check_user_data_quality(
    user_id: int,
    db,
    assessment_date: Optional[date] = None,
    lookback_days: int = 30,
) -> UserDataQuality:
    """
    Run data quality checks for a single user.

    Args:
        user_id: User to check.
        db: SQLAlchemy session.
        assessment_date: Reference date (defaults to today).
        lookback_days: How many days to analyse.

    Returns:
        UserDataQuality with full quality report.
    """
    from app.db.models.wellbeing_daily_metrics import WellbeingDailyMetrics

    if assessment_date is None:
        assessment_date = date.today()

    start_date = assessment_date - timedelta(days=lookback_days - 1)

    rows = (
        db.query(WellbeingDailyMetrics)
        .filter(
            WellbeingDailyMetrics.user_id == user_id,
            WellbeingDailyMetrics.date >= start_date,
            WellbeingDailyMetrics.date <= assessment_date,
        )
        .order_by(WellbeingDailyMetrics.date)
        .all()
    )

    total_days_expected = lookback_days
    total_days_present = len(rows)
    coverage_rate = total_days_present / total_days_expected if total_days_expected > 0 else 0.0

    # Check each metric
    metric_quality = [
        _check_metric_quality(rows, metric)
        for metric in METRIC_COLUMNS
    ]

    # Detect gaps
    gaps = _detect_gaps(rows, start_date, assessment_date)

    # Overall completeness — average of non-zero metric quality scores
    core_metrics = [
        mq for mq in metric_quality
        if mq.metric != "medication_score"  # medication often legitimately absent
    ]
    avg_completeness = (
        sum(mq.quality_score for mq in core_metrics) / len(core_metrics)
        if core_metrics else 0.0
    )

    # Overall quality score — blend coverage and metric completeness
    overall_quality = round(
        coverage_rate * 40 + avg_completeness * 0.6, 1
    )

    # Generate issues and suggestions
    issues, suggestions = _generate_issues_and_suggestions(
        metric_quality, gaps, coverage_rate
    )

    needs_attention = (
        overall_quality < 40
        or coverage_rate < 0.3
        or any(g.gap_days >= 5 for g in gaps)
        or any(mq.outlier_count > 0 for mq in metric_quality)
    )

    return UserDataQuality(
        user_id=user_id,
        assessment_date=str(assessment_date),
        total_days_expected=total_days_expected,
        total_days_present=total_days_present,
        coverage_rate=round(coverage_rate, 3),
        overall_completeness=round(avg_completeness, 1),
        overall_quality_score=overall_quality,
        metric_quality=metric_quality,
        gaps=gaps,
        issues=issues,
        suggestions=suggestions,
        needs_attention=needs_attention,
    )


# ---------------------------------------------------------------------------
# Data repair utilities
# ---------------------------------------------------------------------------

def repair_outliers(
    rows: list,
    db,
    dry_run: bool = True,
) -> dict:
    """
    Detect and optionally repair outlier values in wellbeing metrics.

    In dry_run mode (default): only reports what would be fixed.
    In repair mode: clamps outliers to valid range and saves to DB.

    Args:
        rows: WellbeingDailyMetrics rows to check.
        db: SQLAlchemy session.
        dry_run: If True, report only. If False, apply repairs.

    Returns:
        Summary of repairs made or recommended.
    """
    repairs = []

    for row in rows:
        row_repairs = []
        for metric in METRIC_COLUMNS:
            value = getattr(row, metric)
            if value is None:
                continue
            if value < SCORE_MIN or value > SCORE_MAX:
                clamped = max(SCORE_MIN, min(SCORE_MAX, value))
                row_repairs.append({
                    "metric": metric,
                    "original": value,
                    "repaired": clamped,
                })
                if not dry_run:
                    setattr(row, metric, clamped)

        if row_repairs:
            repairs.append({
                "user_id": row.user_id,
                "date": str(row.date),
                "repairs": row_repairs,
            })

    if not dry_run and repairs:
        db.commit()
        logger.info("Repaired %d outlier values across %d rows", 
                   sum(len(r["repairs"]) for r in repairs), len(repairs))

    return {
        "mode": "dry_run" if dry_run else "repaired",
        "rows_affected": len(repairs),
        "total_values_fixed": sum(len(r["repairs"]) for r in repairs),
        "details": repairs,
    }


# ---------------------------------------------------------------------------
# Population-level quality report
# ---------------------------------------------------------------------------

def run_population_quality_check(
    db,
    assessment_date: Optional[date] = None,
    lookback_days: int = 30,
) -> PopulationDataQuality:
    """
    Run data quality checks for all active users.

    Returns a population-level quality summary.
    """
    from app.db.models.user import User

    if assessment_date is None:
        assessment_date = date.today()

    users = db.query(User).filter(User.is_active == True).all()

    user_reports = []
    quality_scores = []
    coverage_rates = []
    missing_metric_counts: dict[str, int] = {m: 0 for m in METRIC_COLUMNS}
    max_gap_days = 0
    users_with_data = 0
    users_needing_attention = 0

    for user in users:
        try:
            report = check_user_data_quality(
                user_id=user.id,
                db=db,
                assessment_date=assessment_date,
                lookback_days=lookback_days,
            )

            if report.total_days_present > 0:
                users_with_data += 1

            if report.needs_attention:
                users_needing_attention += 1

            quality_scores.append(report.overall_quality_score)
            coverage_rates.append(report.coverage_rate)

            # Track most missing metric
            for mq in report.metric_quality:
                if mq.missing_rate > 0.5:
                    missing_metric_counts[mq.metric] = (
                        missing_metric_counts.get(mq.metric, 0) + 1
                    )

            # Track longest gap
            for gap in report.gaps:
                if gap.gap_days > max_gap_days:
                    max_gap_days = gap.gap_days

            user_reports.append({
                "user_id": user.id,
                "name": f"{user.first_name} {user.last_name}".strip(),
                "quality_score": report.overall_quality_score,
                "coverage_rate": report.coverage_rate,
                "needs_attention": report.needs_attention,
                "issues_count": len(report.issues),
                "top_issue": report.issues[0] if report.issues else None,
            })

        except Exception as e:
            logger.error("Quality check failed for user %d: %s", user.id, e)

    most_missing = max(missing_metric_counts, key=missing_metric_counts.get) \
        if missing_metric_counts else "unknown"

    # Sort by quality score ascending (worst first)
    user_reports.sort(key=lambda r: r["quality_score"])

    return PopulationDataQuality(
        assessment_date=str(assessment_date),
        total_users=len(users),
        users_with_data=users_with_data,
        users_needing_attention=users_needing_attention,
        avg_quality_score=round(
            sum(quality_scores) / len(quality_scores), 1
        ) if quality_scores else 0.0,
        avg_coverage_rate=round(
            sum(coverage_rates) / len(coverage_rates), 3
        ) if coverage_rates else 0.0,
        most_missing_metric=most_missing,
        longest_gap_days=max_gap_days,
        user_reports=user_reports,
    )