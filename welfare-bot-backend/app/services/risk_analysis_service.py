from __future__ import annotations

from typing import Any

from app.db.models.daily_checkin import DailyCheckIn
from app.services.risk_phrases import RISK_PHRASES


def detect_language(text: str, fallback: str = "en") -> str:
    text_lower = f" {text.lower()} "
    if any(word in text_lower for word in [" minä ", " olen ", " huimaa ", " yksinäinen ", " rintakipu "]):
        return "fi"
    if any(word in text_lower for word in [" jag ", " trött ", " ensam ", " bröstsmärta "]):
        return "sv"
    return fallback


def _collect_signals(text: str, language: str) -> tuple[list[str], list[str]]:
    phrases = RISK_PHRASES.get(language, RISK_PHRASES["en"])
    text_lower = text.lower()

    signals: list[str] = []
    reasons: list[str] = []

    mapping = {
        "urgent": "safety",
        "poor_sleep": "fatigue",
        "food": "nutrition_hydration",
        "water": "nutrition_hydration",
        "fatigue": "fatigue",
        "dizziness": "dizziness",
        "emotional": "emotional",
        "medication": "medication",
    }

    for group, words in phrases.items():
        for word in words:
            if word in text_lower:
                signals.append(group)
                reasons.append(f"Detected phrase: {word}")
                break

    categories = [mapping[s] for s in signals if s in mapping]
    return signals, categories


def _build_result(
    *,
    user_id: int,
    signals: list[str],
    categories: list[str],
    reason_lines: list[str],
) -> dict[str, Any]:
    score = 0
    category = "general"
    risk_level = "low"
    suggested_action = "Continue monitoring."
    follow_up_question = "How are you feeling now?"
    should_alert_family = False

    if "urgent" in signals:
        score = 10
        risk_level = "critical"
        category = "safety"
        suggested_action = "Seek urgent help immediately."
        follow_up_question = "Are you safe right now?"
        should_alert_family = True
    else:
        if "medication" in signals:
            score += 2
        if "food" in signals:
            score += 2
        if "water" in signals:
            score += 2
        if "poor_sleep" in signals:
            score += 2
        if "fatigue" in signals:
            score += 2
        if "dizziness" in signals:
            score += 3
        if "emotional" in signals:
            score += 2

        if "medication" in signals and ("dizziness" in signals or "fatigue" in signals):
            score += 2
        if ("food" in signals or "water" in signals) and ("dizziness" in signals or "fatigue" in signals):
            score += 2

        if score >= 7:
            risk_level = "high"
            suggested_action = "Check immediate support needs and consider contacting a trusted person."
            follow_up_question = "Is someone nearby who can check on you?"
        elif score >= 4:
            risk_level = "medium"
            suggested_action = "Follow up and monitor symptoms."
            follow_up_question = "Would you like to tell me a bit more?"
        else:
            risk_level = "low"
            suggested_action = "Provide supportive guidance."
            follow_up_question = "What would help you feel a little better?"

        if categories:
            category = categories[-1]

    return {
        "user_id": user_id,
        "category": category,
        "risk_level": risk_level,
        "risk_score": score,
        "reason": " | ".join(reason_lines) if reason_lines else None,
        "suggested_action": suggested_action,
        "follow_up_question": follow_up_question,
        "signals_json": signals,
        "reasons_json": reason_lines,
        "should_alert_family": should_alert_family,
        "model_version": "rule_engine_v1",
    }


def analyze_chat_message(user_id: int, message: str, language: str | None = None) -> dict[str, Any]:
    resolved_language = language or detect_language(message)
    signals, categories = _collect_signals(message, resolved_language)
    reason_lines = [f"Language: {resolved_language}"] + [f"Signal: {s}" for s in signals]

    return _build_result(
        user_id=user_id,
        signals=signals,
        categories=categories,
        reason_lines=reason_lines,
    )


def analyze_checkin_answers(checkin: DailyCheckIn, language: str = "en") -> dict[str, Any]:
    parts = [
        checkin.sleep_quality or "",
        checkin.food_intake or "",
        checkin.hydration or "",
        checkin.mood or "",
        checkin.notes or "",
    ]
    merged = " ".join(parts).strip()
    resolved_language = detect_language(merged, fallback=language)

    signals, categories = _collect_signals(merged, resolved_language)
    reason_lines = [f"Language: {resolved_language}"] + [f"Signal: {s}" for s in signals]

    return _build_result(
        user_id=checkin.user_id,
        signals=signals,
        categories=categories,
        reason_lines=reason_lines,
    )