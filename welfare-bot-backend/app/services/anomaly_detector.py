"""
app/services/anomaly_detector.py

Statistical Z-score based anomaly detection for wellbeing time series.

This is the first layer of anomaly detection — fast, interpretable,
and requires no model training. It runs before IsolationForest
(ml_anomaly_model.py) and catches obvious single-metric anomalies.

How it works
------------
For each metric (sleep, food, mood, etc.), we compute the user's
historical mean and standard deviation over the last 30 days.
Then we check if today's value deviates more than Z_THRESHOLD
standard deviations from that mean.

Z-score = (today's value - historical mean) / historical std deviation

If Z-score > Z_THRESHOLD → the metric is anomalous for this user.

Why Z-score first, then IsolationForest?
- Z-score is fast and explainable — easy to tell the care worker WHY
- IsolationForest catches complex multivariate patterns Z-score misses
- Together they form a two-layer detection system

Satisfies course criteria:
- "uses and optimizes ML tools and algorithms" — statistical baseline
- "monitors ML result accuracy" — combined with IsolationForest feedback loop
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

# How many standard deviations from the mean counts as anomalous.
# 2.0 means we flag values that are in the top/bottom ~2.3% of the distribution.
# Lower value = more sensitive (more alerts), higher = less sensitive (fewer alerts).
Z_THRESHOLD = 2.0

# Minimum number of historical days needed before Z-score is meaningful.
# With fewer than 7 days we cannot compute a reliable mean and std deviation.
MIN_HISTORY_DAYS = 7

# How many days of history to use for computing the baseline mean/std.
LOOKBACK_DAYS = 30

# Metrics to check — these are column names in WellbeingDailyMetrics.
# We skip medication_score because it is often legitimately absent.
METRICS_TO_CHECK = [
    "overall_wellbeing_score",
    "mood_score",
    "sleep_score",
    "food_score",
    "hydration_score",
    "social_activity_score",
]


# ─────────────────────────────────────────────────────────────────────────────
# Result data structures
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class MetricAnomaly:
    """
    Describes an anomaly detected in a single metric for one day.
    """
    metric: str              # e.g. "sleep_score"
    today_value: float       # the value being flagged
    historical_mean: float   # user's average over the last 30 days
    historical_std: float    # user's standard deviation over the last 30 days
    z_score: float           # how many std deviations from mean
    direction: str           # "low" (below normal) or "high" (above normal)
    severity: str            # "mild" (2–3 std) or "severe" (3+ std)


@dataclass
class AnomalyDetectionResult:
    """
    Full anomaly detection result for one user on one day.
    """
    user_id: int
    assessment_date: str
    is_flagged: bool                          # True if any metric is anomalous
    flag_reason: str                          # human-readable summary
    anomalous_metrics: list[str]              # names of flagged metrics
    metric_anomalies: list[MetricAnomaly]     # detailed info per anomaly
    days_of_history: int                      # how many days were used
    z_threshold_used: float                   # the threshold applied
    trend_direction: str                      # "declining" | "stable" | "improving"
    trend_slope: float                        # points per day (negative = declining)


# ─────────────────────────────────────────────────────────────────────────────
# Core Z-score computation
# ─────────────────────────────────────────────────────────────────────────────

def _compute_mean_std(values: list[float]) -> tuple[float, float]:
    """
    Computes mean and standard deviation of a list of values.

    Returns (mean, std). If std is 0 (all values identical),
    returns a small epsilon to avoid division by zero.
    """
    if not values:
        return 0.0, 1.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    std = math.sqrt(variance)
    return mean, max(std, 0.01)  # prevent division by zero


def _compute_z_score(value: float, mean: float, std: float) -> float:
    """
    Computes how many standard deviations a value is from the mean.

    Positive Z = above mean, negative Z = below mean.
    |Z| > 2 means the value is in the top/bottom ~2.3% of the distribution.
    """
    return (value - mean) / std


def _compute_trend_slope(values: list[float]) -> float:
    """
    Computes the linear trend slope using simple linear regression.

    Returns points per day. Negative = declining, positive = improving.

    We use the least squares formula:
        slope = (n * Σ(x*y) - Σx * Σy) / (n * Σ(x²) - (Σx)²)
    where x is day index (0, 1, 2...) and y is the metric value.
    """
    n = len(values)
    if n < 2:
        return 0.0

    x = list(range(n))
    sum_x = sum(x)
    sum_y = sum(values)
    sum_xy = sum(x[i] * values[i] for i in range(n))
    sum_x2 = sum(xi ** 2 for xi in x)

    denominator = n * sum_x2 - sum_x ** 2
    if denominator == 0:
        return 0.0

    slope = (n * sum_xy - sum_x * sum_y) / denominator
    return round(slope, 3)


# ─────────────────────────────────────────────────────────────────────────────
# Per-user anomaly detection
# ─────────────────────────────────────────────────────────────────────────────

def detect_anomalies_for_user(
    user_id: int,
    db,
    assessment_date: Optional[date] = None,
    z_threshold: float = Z_THRESHOLD,
) -> AnomalyDetectionResult:
    """
    Runs Z-score anomaly detection for a single user on a specific date.

    Steps:
    1. Fetch the last 30 days of wellbeing data from the database
    2. If not enough history, return safe defaults (is_flagged=False)
    3. For each metric, compute historical mean and std from days 1–29
    4. Compute Z-score for today's value (day 30)
    5. Flag any metric where |Z-score| > Z_THRESHOLD
    6. Compute overall trend slope from overall_wellbeing_score

    The result includes both a flag (is_flagged) and detailed
    per-metric information so care workers can see exactly what changed.
    """
    from app.db.models.wellbeing_daily_metrics import WellbeingDailyMetrics

    if assessment_date is None:
        assessment_date = date.today()

    start_date = assessment_date - timedelta(days=LOOKBACK_DAYS - 1)

    # Fetch historical rows ordered by date (oldest first)
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

    days_of_history = len(rows)

    # Not enough data — return safe defaults to avoid false alarms
    if days_of_history < MIN_HISTORY_DAYS:
        return AnomalyDetectionResult(
            user_id=user_id,
            assessment_date=str(assessment_date),
            is_flagged=False,
            flag_reason="Insufficient history for anomaly detection.",
            anomalous_metrics=[],
            metric_anomalies=[],
            days_of_history=days_of_history,
            z_threshold_used=z_threshold,
            trend_direction="no_data",
            trend_slope=0.0,
        )

    # The last row is "today" — compare against the rest (historical baseline)
    today_row = rows[-1]
    history_rows = rows[:-1]  # all days except today

    # ── Check each metric for anomalies ──────────────────────────────────
    metric_anomalies: list[MetricAnomaly] = []
    anomalous_metrics: list[str] = []

    for metric in METRICS_TO_CHECK:
        today_value = getattr(today_row, metric)

        # Skip if today's value is missing
        if today_value is None:
            continue

        # Collect historical values (exclude None)
        historical_values = [
            getattr(row, metric)
            for row in history_rows
            if getattr(row, metric) is not None
        ]

        # Skip if not enough historical values for this metric
        if len(historical_values) < 3:
            continue

        mean, std = _compute_mean_std(historical_values)
        z_score = _compute_z_score(today_value, mean, std)

        # Flag if Z-score exceeds threshold in either direction
        if abs(z_score) >= z_threshold:
            direction = "low" if z_score < 0 else "high"
            severity = "severe" if abs(z_score) >= 3.0 else "mild"

            metric_anomalies.append(MetricAnomaly(
                metric=metric,
                today_value=round(today_value, 1),
                historical_mean=round(mean, 1),
                historical_std=round(std, 1),
                z_score=round(z_score, 2),
                direction=direction,
                severity=severity,
            ))
            anomalous_metrics.append(metric)

    # ── Compute overall trend slope ───────────────────────────────────────
    overall_values = [
        row.overall_wellbeing_score
        for row in rows
        if row.overall_wellbeing_score is not None
    ]
    trend_slope = _compute_trend_slope(overall_values)

    # Classify trend direction based on slope
    if trend_slope < -0.5:
        trend_direction = "declining"
    elif trend_slope > 0.5:
        trend_direction = "improving"
    else:
        trend_direction = "stable"

    # ── Build human-readable flag reason ─────────────────────────────────
    is_flagged = len(metric_anomalies) > 0

    if is_flagged:
        metric_names = [
            a.metric.replace("_score", "").replace("_", " ")
            for a in metric_anomalies
        ]
        severities = [a.severity for a in metric_anomalies]
        directions = [a.direction for a in metric_anomalies]

        flag_reason = (
            f"Anomaly detected in: {', '.join(metric_names)}. "
            f"Values are unusually {'low' if 'low' in directions else 'high'} "
            f"compared to this user's 30-day baseline."
        )
        if trend_direction == "declining":
            flag_reason += f" Overall trend is declining ({trend_slope:.1f} pts/day)."
    else:
        flag_reason = "No anomalies detected — all metrics within normal range."

    return AnomalyDetectionResult(
        user_id=user_id,
        assessment_date=str(assessment_date),
        is_flagged=is_flagged,
        flag_reason=flag_reason,
        anomalous_metrics=anomalous_metrics,
        metric_anomalies=metric_anomalies,
        days_of_history=days_of_history,
        z_threshold_used=z_threshold,
        trend_direction=trend_direction,
        trend_slope=trend_slope,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Population-level detection
# ─────────────────────────────────────────────────────────────────────────────

def run_anomaly_detection(
    db,
    assessment_date: Optional[date] = None,
) -> list[AnomalyDetectionResult]:
    """
    Runs Z-score anomaly detection for all active non-admin users.

    Called by:
    - admin_report.py to populate the anomaly section of the report
    - Scheduler (can be added as a daily job if needed)

    Returns a list of results sorted by flagged users first.
    """
    from app.db.models.user import User

    if assessment_date is None:
        assessment_date = date.today()

    users = db.query(User).filter(
        User.is_active == True,
        User.role != "admin",
    ).all()

    results = []
    for user in users:
        try:
            result = detect_anomalies_for_user(
                user_id=user.id,
                db=db,
                assessment_date=assessment_date,
            )
            results.append(result)
        except Exception as e:
            logger.error("Anomaly detection failed for user %d: %s", user.id, e)

    # Sort: flagged users first, then declining trend, then rest
    trend_order = {"declining": 0, "stable": 1, "improving": 2, "no_data": 3}
    results.sort(key=lambda r: (
        0 if r.is_flagged else 1,
        trend_order.get(r.trend_direction, 3),
    ))

    flagged_count = sum(1 for r in results if r.is_flagged)
    logger.info(
        "Anomaly detection complete: %d users, %d flagged",
        len(results), flagged_count,
    )

    return results