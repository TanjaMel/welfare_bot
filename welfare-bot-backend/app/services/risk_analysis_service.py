from app.schemas.checkin import DailyCheckInCreate
from app.services.risk_phrases import (
    ALL_EMOTIONAL_PHRASES,
    ALL_FOOD_PHRASES,
    ALL_HEALTH_PHRASES,
    ALL_MEDICATION_PHRASES,
    ALL_SLEEP_PHRASES,
    ALL_URGENT_PHRASES,
    contains_any,
)


def analyze_checkin_answers(payload: DailyCheckInCreate) -> dict:
    sleep_answer = (payload.sleep_answer or "").lower().strip()
    food_answer = (payload.food_answer or "").lower().strip()
    medication_answer = (payload.medication_answer or "").lower().strip()
    mood_answer = (payload.mood_answer or "").lower().strip()
    extra_notes = (payload.extra_notes or "").lower().strip()

    combined = " ".join([
        sleep_answer,
        food_answer,
        medication_answer,
        mood_answer,
        extra_notes,
    ])

    if contains_any(combined, ALL_URGENT_PHRASES):
        return {
            "category": "fall_or_injury",
            "risk_level": "urgent",
            "needs_family_notification": True,
            "reason": "Urgent situation detected from the daily check-in.",
            "suggested_action": "urgent_alert",
            "model_version": "multilingual-rule-v2",
        }

    medication_problem = contains_any(combined, ALL_MEDICATION_PHRASES)
    food_problem = contains_any(combined, ALL_FOOD_PHRASES)
    sleep_problem = contains_any(combined, ALL_SLEEP_PHRASES)
    emotional_problem = contains_any(combined, ALL_EMOTIONAL_PHRASES)
    health_problem = contains_any(combined, ALL_HEALTH_PHRASES)

    if medication_problem and health_problem:
        return {
            "category": "medication_issue",
            "risk_level": "high",
            "needs_family_notification": True,
            "reason": "Missed medication combined with physical symptoms.",
            "suggested_action": "notify_family",
            "model_version": "multilingual-rule-v2",
        }

    if food_problem and health_problem:
        return {
            "category": "missed_meal",
            "risk_level": "high",
            "needs_family_notification": True,
            "reason": "Skipped meals combined with physical discomfort.",
            "suggested_action": "notify_family",
            "model_version": "multilingual-rule-v2",
        }

    if medication_problem:
        return {
            "category": "medication_issue",
            "risk_level": "medium",
            "needs_family_notification": True,
            "reason": "Possible missed medication.",
            "suggested_action": "notify_family",
            "model_version": "multilingual-rule-v2",
        }

    if food_problem:
        return {
            "category": "missed_meal",
            "risk_level": "medium",
            "needs_family_notification": True,
            "reason": "Possible skipped meals.",
            "suggested_action": "notify_family",
            "model_version": "multilingual-rule-v2",
        }

    if sleep_problem and emotional_problem:
        return {
            "category": "poor_sleep",
            "risk_level": "medium",
            "needs_family_notification": False,
            "reason": "Poor sleep combined with emotional distress.",
            "suggested_action": "follow_up_question",
            "model_version": "multilingual-rule-v2",
        }

    if sleep_problem:
        return {
            "category": "poor_sleep",
            "risk_level": "low",
            "needs_family_notification": False,
            "reason": "User reports poor sleep.",
            "suggested_action": "follow_up_question",
            "model_version": "multilingual-rule-v2",
        }

    if emotional_problem:
        return {
            "category": "emotional_support",
            "risk_level": "low",
            "needs_family_notification": False,
            "reason": "User may need emotional support.",
            "suggested_action": "follow_up_question",
            "model_version": "multilingual-rule-v2",
        }

    if health_problem:
        return {
            "category": "health_issue",
            "risk_level": "medium",
            "needs_family_notification": True,
            "reason": "User reports physical discomfort.",
            "suggested_action": "notify_family",
            "model_version": "multilingual-rule-v2",
        }

    return {
        "category": "normal",
        "risk_level": "low",
        "needs_family_notification": False,
        "reason": "No immediate risk detected from the daily check-in.",
        "suggested_action": "none",
        "model_version": "multilingual-rule-v2",
    }


def analyze_chat_message(message_text: str) -> dict:
    text = (message_text or "").lower().strip()

    if contains_any(text, ALL_URGENT_PHRASES):
        return {
            "category": "fall_or_injury",
            "risk_level": "urgent",
            "needs_family_notification": True,
            "reason": "Urgent situation detected in chat message.",
            "suggested_action": "urgent_alert",
            "model_version": "multilingual-rule-v2",
        }

    medication_problem = contains_any(text, ALL_MEDICATION_PHRASES)
    food_problem = contains_any(text, ALL_FOOD_PHRASES)
    sleep_problem = contains_any(text, ALL_SLEEP_PHRASES)
    emotional_problem = contains_any(text, ALL_EMOTIONAL_PHRASES)
    health_problem = contains_any(text, ALL_HEALTH_PHRASES)

    if medication_problem and health_problem:
        return {
            "category": "medication_issue",
            "risk_level": "high",
            "needs_family_notification": True,
            "reason": "Message suggests missed medication and physical symptoms.",
            "suggested_action": "notify_family",
            "model_version": "multilingual-rule-v2",
        }

    if medication_problem:
        return {
            "category": "medication_issue",
            "risk_level": "medium",
            "needs_family_notification": True,
            "reason": "Possible missed medication detected in message.",
            "suggested_action": "notify_family",
            "model_version": "multilingual-rule-v2",
        }

    if food_problem:
        return {
            "category": "missed_meal",
            "risk_level": "medium",
            "needs_family_notification": True,
            "reason": "Possible skipped meals detected in message.",
            "suggested_action": "notify_family",
            "model_version": "multilingual-rule-v2",
        }

    if sleep_problem and emotional_problem:
        return {
            "category": "poor_sleep",
            "risk_level": "medium",
            "needs_family_notification": False,
            "reason": "Poor sleep combined with emotional distress in message.",
            "suggested_action": "follow_up_question",
            "model_version": "multilingual-rule-v2",
        }

    if emotional_problem:
        return {
            "category": "emotional_support",
            "risk_level": "low",
            "needs_family_notification": False,
            "reason": "Message suggests emotional support may be needed.",
            "suggested_action": "follow_up_question",
            "model_version": "multilingual-rule-v2",
        }

    if health_problem:
        return {
            "category": "health_issue",
            "risk_level": "medium",
            "needs_family_notification": True,
            "reason": "Message suggests physical discomfort or health issue.",
            "suggested_action": "notify_family",
            "model_version": "multilingual-rule-v2",
        }

    return {
        "category": "normal",
        "risk_level": "low",
        "needs_family_notification": False,
        "reason": "No immediate risk detected in chat message.",
        "suggested_action": "none",
        "model_version": "multilingual-rule-v2",
    }


def build_notification_message(
    first_name: str,
    last_name: str,
    category: str,
    risk_level: str,
    reason: str,
) -> str:
    full_name = f"{first_name} {last_name}".strip()
    return (
        f"Alert for family contact: {full_name} has a situation marked as "
        f"{category} with risk level {risk_level}. Reason: {reason}"
    )