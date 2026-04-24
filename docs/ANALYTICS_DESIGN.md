# Wellbeing Analytics System — Design Document

## Why an aggregation layer

Raw queries for trend data would join 3 tables, apply date filters, aggregate
risk scores, and compute weighted composites on every request. For a system
where the frontend polls after each message, this creates N×3 table scans per
active user per day. The aggregation layer computes once and reads once.

Performance comparison:
- Raw query: 3 table joins + GROUP BY + window functions = ~50–200ms per request
- Aggregated: single indexed lookup on (user_id, date) = ~2–5ms

---

## Scoring formulas

### Component scores (all 0–100)

| Score | Source | Formula |
|---|---|---|
| sleep_score | daily_checkins.sleep_quality | (rating - 1) / 4 × 100 |
| food_score | daily_checkins.ate_* | meals_eaten / meals_tracked × 100 |
| hydration_score | daily_checkins.drank_enough_water | True=100, False=20 |
| medication_score | daily_checkins.took_medication | True=100, False=0 |
| mood_score | daily_checkins.mood_rating OR risk signals | (rating - 1) / 4 × 100 |
| social_score | conversation_messages count | min(80, count × 16) |

### Overall wellbeing score

```
checkin_composite = weighted_avg(mood×0.25, sleep×0.25, food×0.20, hydration×0.15, medication×0.10, social×0.05)
risk_contribution = max(0, 100 - avg_risk_score × 10)
overall = checkin_composite × 0.70 + risk_contribution × 0.30
```

### Missing data handling

- Component with no data → excluded from weighted average, weight redistributed
- No checkin at all → use risk signal only, mark data_completeness = 0.0
- data_completeness field tells the UI how reliable the score is

### Status thresholds

| Score | Status | User sees |
|---|---|---|
| ≥ 70 | stable | "You seem to be doing well today." |
| 50–69 | needs_attention | "Today looks a little quieter than usual." |
| 30–49 | concerning | "It seems like today has been harder." |
| < 30 | critical | "We noticed some signs that today may be difficult." |

---

## Indexing strategy

```sql
-- Primary access pattern: user's history ordered by date
CREATE INDEX ix_wellbeing_user_date ON wellbeing_daily_metrics(user_id, date);

-- Uniqueness + fast upsert
CREATE UNIQUE INDEX uq_wellbeing_user_date ON wellbeing_daily_metrics(user_id, date);
```

No index needed on status or scores — these are never filtered directly.
The composite index on (user_id, date) covers all three endpoints.

---

## Triggering aggregation

### MVP (recommended): FastAPI BackgroundTasks

After each message is sent, trigger a background recompute:

```python
# In conversations.py send_message endpoint
background_tasks.add_task(aggregate_daily_wellbeing, payload.user_id, date.today(), db)
```

This is zero-infrastructure — no Celery, no Redis, no cron. The task runs
after the response is returned to the user. Idempotent — safe to call multiple
times per day.

### Production: APScheduler inside FastAPI

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

@scheduler.scheduled_job("cron", hour=23, minute=55)
async def nightly_aggregation():
    # Aggregate all active users from today
    ...

scheduler.start()
```

Runs at 23:55 every night, computes final daily scores after all conversations
are done.

### Future: Celery beat (when scaling to multiple instances)

Required when running multiple Railway replicas — APScheduler would run on
every instance. Celery beat runs once. Add when you have >100 active users.

---

## Family dashboard extension

The same wellbeing_daily_metrics table supports family access with minimal changes:

1. Add a `care_contacts` permission check — care contact can only read their linked user's data
2. Expose a separate endpoint `GET /wellbeing/family/{care_contact_id}/users` that lists permitted users
3. Return the same soft messages — family sees the same human-readable output, not raw scores
4. Add a `notify_on_status_change` flag to care_contacts — trigger email when status changes from stable to concerning

No schema changes needed. The aggregation layer already has everything required.

---

## Files to create in the project

```
welfare-bot-backend/app/
├── db/models/
│   └── wellbeing_daily_metrics.py     ← SQLAlchemy model
├── services/
│   └── aggregation_pipeline.py        ← Scoring + upsert logic
├── api/v1/endpoints/
│   └── wellbeing.py                   ← FastAPI endpoints
└── alembic/versions/
    └── a1b2c3d4e5f6_wellbeing.py      ← Migration
```

Add to api.py:
```python
from app.api.v1.endpoints import wellbeing
api_router.include_router(wellbeing.router, prefix="/wellbeing", tags=["wellbeing"])
```