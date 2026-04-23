from __future__ import annotations

import pandas as pd
import streamlit as st
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.services.analytics_service import get_user_analytics_summary


st.set_page_config(
    page_title="Welfare Bot Analytics",
    layout="wide",
)


def load_user_analytics(user_id: int) -> dict:
    db: Session = SessionLocal()
    try:
        return get_user_analytics_summary(db, user_id)
    finally:
        db.close()


def trend_to_df(analytics: dict) -> pd.DataFrame:
    return pd.DataFrame(analytics.get("trend", []))


def risk_levels_to_df(analytics: dict) -> pd.DataFrame:
    data = analytics.get("distributions", {}).get("risk_levels", {})
    return pd.DataFrame([{"risk_level": k, "count": v} for k, v in data.items()])


def risk_categories_to_df(analytics: dict) -> pd.DataFrame:
    data = analytics.get("distributions", {}).get("risk_categories", {})
    return pd.DataFrame([{"category": k, "count": v} for k, v in data.items()])


def messages_by_language_to_df(analytics: dict) -> pd.DataFrame:
    data = analytics.get("segmentation", {}).get("messages_by_language", {})
    return pd.DataFrame([{"language": k, "count": v} for k, v in data.items()])


def time_of_day_to_df(analytics: dict) -> pd.DataFrame:
    data = analytics.get("segmentation", {}).get("time_of_day", {})
    return pd.DataFrame([{"segment": k, "count": v} for k, v in data.items()])


def weekday_weekend_to_df(analytics: dict) -> pd.DataFrame:
    data = analytics.get("segmentation", {}).get("weekday_vs_weekend", {})
    return pd.DataFrame([{"period": k, "count": v} for k, v in data.items()])


def top_categories_to_df(analytics: dict) -> pd.DataFrame:
    return pd.DataFrame(analytics.get("top_categories", []))


st.title("Welfare Bot Analytics Dashboard")
st.caption("Python-based analytics dashboard for wellbeing risk monitoring")

user_id = st.number_input("User ID", min_value=1, step=1, value=1)

if st.button("Load analytics"):
    try:
        analytics = load_user_analytics(user_id)

        st.subheader("Weekly summary")

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Risk increasing", "Yes" if analytics.get("risk_increasing") else "No")
        col2.metric("Consecutive high-risk days", analytics.get("consecutive_high_risk_days", 0))
        col3.metric("Loneliness streak", analytics.get("repeated_loneliness_streak", 0))
        col4.metric("Nutrition/hydration streak", analytics.get("nutrition_hydration_streak", 0))

        st.subheader("Risk score trend")
        trend_df = trend_to_df(analytics)
        if not trend_df.empty:
            st.line_chart(trend_df.set_index("date")["avg_score"])
            st.dataframe(trend_df, width="stretch")
        else:
            st.info("No trend data yet.")

        st.subheader("Risk level distribution")
        risk_levels_df = risk_levels_to_df(analytics)
        if not risk_levels_df.empty:
            st.bar_chart(risk_levels_df.set_index("risk_level")["count"])
            st.dataframe(risk_levels_df, width="stretch")
        else:
            st.info("No risk level data yet.")

        st.subheader("Risk category distribution")
        risk_categories_df = risk_categories_to_df(analytics)
        if not risk_categories_df.empty:
            st.bar_chart(risk_categories_df.set_index("category")["count"])
            st.dataframe(risk_categories_df, width="stretch")
        else:
            st.info("No risk category data yet.")

        col_a, col_b = st.columns(2)

        with col_a:
            st.subheader("Messages by language")
            language_df = messages_by_language_to_df(analytics)
            if not language_df.empty:
                st.bar_chart(language_df.set_index("language")["count"])
                st.dataframe(language_df, width="stretch")
            else:
                st.info("No language data yet.")

        with col_b:
            st.subheader("Messages by time of day")
            time_df = time_of_day_to_df(analytics)
            if not time_df.empty:
                st.bar_chart(time_df.set_index("segment")["count"])
                st.dataframe(time_df, width="stretch")
            else:
                st.info("No segmentation data yet.")

        st.subheader("Weekday vs weekend")
        weekday_df = weekday_weekend_to_df(analytics)
        if not weekday_df.empty:
            st.bar_chart(weekday_df.set_index("period")["count"])
            st.dataframe(weekday_df, width="stretch")
        else:
            st.info("No weekday/weekend data yet.")

        st.subheader("Top repeated categories")
        top_categories_df = top_categories_to_df(analytics)
        if not top_categories_df.empty:
            st.dataframe(top_categories_df, width="stretch")
        else:
            st.info("No repeated category data yet.")

        st.subheader("Raw analytics JSON")
        st.json(analytics)

    except Exception as e:
        st.error(f"Failed to load analytics: {e}")