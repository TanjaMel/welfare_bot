from __future__ import annotations

"""
app/services/risk_service.py

LLM-powered risk assessment with instant rule-based fallback.

Architecture
------------
1. Fast path: existing rule engine runs first (zero latency, always safe).
2. LLM path: GPT-4o-mini is asked to return structured JSON risk assessment.
   - If LLM succeeds and returns valid JSON → use LLM result.
   - If LLM fails, times out, or returns invalid JSON → use rule result silently.
3. The LLM result is always cross-checked: if rules flagged CRITICAL but LLM
   said LOW, we keep CRITICAL (safety-first override).

The public API is unchanged — callers still call assess() with the same
signature and get the same response shape.
"""

import json
import logging
import os
from collections import Counter
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Feature flag — set LLM_RISK_ENABLED=false to revert to rules only
# ---------------------------------------------------------------------------
_LLM_ENABLED = os.getenv("LLM_RISK_ENABLED", "true").lower() == "true"
_LLM_TIMEOUT = float(os.getenv("LLM_RISK_TIMEOUT_SECONDS", "8"))
_LLM_MODEL = os.getenv("LLM_RISK_MODEL", "gpt-4o-mini")

# ---------------------------------------------------------------------------
# Existing rule engine (unchanged — used as fallback)
# ---------------------------------------------------------------------------

SUPPORTED_LANGUAGES = {"en", "fi", "sv"}

SIGNAL_RULES: dict[str, dict[str, Any]] = {
    "poor_sleep": {
        "patterns": [
            "didn't sleep", "did not sleep", "no sleep", "poor sleep", "slept badly",
            "en nukkunut", "nukuin huonosti", "huono uni",
            "sov inte", "sovit dåligt",
        ],
        "weight": 2,
        "category": "sleep",
    },
    "poor_appetite": {
        "patterns": [
            "didn't eat", "did not eat", "no food", "not eating", "no appetite",
            "en syönyt", "ei ruokaa", "ei ruokahalua",
            "åt inte", "ingen mat", "ingen aptit",
        ],
        "weight": 3,
        "category": "nutrition",
    },
    "no_water": {
        "patterns": [
            "didn't drink", "did not drink", "no water", "dehydrated",
            "en juonut", "ei vettä",
            "drack inte", "inget vatten",
        ],
        "weight": 3,
        "category": "hydration",
    },
    "fatigue": {
        "patterns": [
            "tired", "exhausted", "very weak", "fatigue",
            "väsynyt", "heikko", "uupunut",
            "trött", "svag", "utmattad",
        ],
        "weight": 2,
        "category": "fatigue",
    },
    "dizziness": {
        "patterns": [
            "dizzy", "dizziness", "lightheaded", "faint",
            "huimaa", "pyörryttää",
            "yr", "svimfärdig",
        ],
        "weight": 4,
        "category": "dizziness",
    },
    "sadness_loneliness": {
        "patterns": [
            "sad", "lonely", "alone", "hopeless", "down",
            "surullinen", "yksinäinen", "alakuloinen",
            "ledsen", "ensam", "nedstämd",
            "jag mår inte bra", "mår inte bra", "inte bra idag",
        ],
        "weight": 4,
        "category": "emotional",
    },
    "fall": {
        "patterns": [
            "i fell", "fell down", "had a fall",
            "kaaduin", "kaatui", "kaatunut",
            "jag föll", "ramlade",
        ],
        "weight": 7,
        "category": "fall",
    },
    "pain": {
        "patterns": [
            "pain", "hurts", "aching",
            "kipu", "sattuu", "kipeä",
            "smärta", "ont", "värk",
        ],
        "weight": 4,
        "category": "pain",
    },
    "chest_pain": {
        "patterns": [
            "chest pain", "pain in my chest",
            "rintakipu", "kipua rinnassa",
            "bröstsmärta", "ont i bröstet",
        ],
        "weight": 10,
        "category": "cardiac",
    },
}

CRITICAL_SIGNALS = {"chest_pain"}

RISK_LEVELS = ["low", "medium", "high", "critical"]
_LEVEL_RANK = {lvl: i for i, lvl in enumerate(RISK_LEVELS)}


def _higher_level(a: str, b: str) -> str:
    """Return whichever risk level is higher."""
    return a if _LEVEL_RANK.get(a, 0) >= _LEVEL_RANK.get(b, 0) else b


def detect_language(text: str, preferred_language: str | None = None) -> str:
    if preferred_language and preferred_language in SUPPORTED_LANGUAGES:
        return preferred_language

    lowered = text.lower()

    finnish_hits = sum(
        token in lowered
        for token in [
            " minä ", " olen ", " väsynyt", " huimaa", " kaaduin",
            " rintakipu", " surullinen", " yksinäinen",
            " en nukkunut", " en syönyt", " en juonut",
            " olo", " vointi", " turvassa",
        ]
    )

    swedish_hits = sum(
        token in lowered
        for token in [
            " jag ", " trött", " yr", " jag föll",
            " bröstsmärta", " ledsen", " ensam",
            " jag sov inte", " jag åt inte", " jag drack inte",
            " mår", " trygg", " säkert",
        ]
    )

    if finnish_hits > swedish_hits and finnish_hits > 0:
        return "fi"
    if swedish_hits > finnish_hits and swedish_hits > 0:
        return "sv"
    return "en"


def _normalize_text(text: str) -> str:
    return " ".join(text.lower().split())


def _extract_signals(text: str) -> list[str]:
    lowered = _normalize_text(text)
    return [
        name for name, cfg in SIGNAL_RULES.items()
        if any(p in lowered for p in cfg["patterns"])
    ]


def _localize(language: str, key: str) -> str:
    translations = {
        "en": {
            "follow_up_low": "How are you feeling right now?",
            "follow_up_medium": "Have you been able to eat, drink, and rest today?",
            "follow_up_high": "Are you safe right now, and is someone nearby who could check on you?",
            "follow_up_critical": "Please seek urgent help now. Can you call emergency services or a trusted person immediately?",
            "action_low": "Offer supportive conversation and monitor for changes.",
            "action_medium": "Encourage hydration, food, rest, and a check-in soon.",
            "action_high": "Encourage immediate check-in with family or caregiver and monitor closely.",
            "action_critical": "Recommend urgent medical help or emergency services immediately.",
            "reason_repeat": "Similar warning signs were mentioned recently.",
            "reason_elderly": "Older age / frailty increases the significance of these symptoms.",
        },
        "fi": {
            "follow_up_low": "Miltä sinusta tuntuu juuri nyt?",
            "follow_up_medium": "Oletko pystynyt syömään, juomaan ja lepäämään tänään?",
            "follow_up_high": "Oletko nyt turvassa, ja onko lähellä joku, joka voisi tarkistaa vointisi?",
            "follow_up_critical": "Hae heti apua. Voitko soittaa hätänumeroon tai luotetulle läheiselle nyt heti?",
            "action_low": "Vastaa rauhallisesti ja seuraa voinnin muutoksia.",
            "action_medium": "Kannusta juomaan, syömään, lepäämään ja tarkistamaan vointi pian uudelleen.",
            "action_high": "Kannusta ottamaan heti yhteys läheiseen tai hoitajaan ja seuraa vointia tarkasti.",
            "action_critical": "Suosittele välitöntä lääkinnällistä apua tai hätäpalvelua.",
            "reason_repeat": "Samanlaisia huolimerkkejä on tullut esiin myös äskettäin.",
            "reason_elderly": "Ikä / hauraus lisää oireiden merkitystä.",
        },
        "sv": {
            "follow_up_low": "Hur mår du just nu?",
            "follow_up_medium": "Har du kunnat äta, dricka och vila idag?",
            "follow_up_high": "Är du i säkerhet just nu, och finns det någon i närheten som kan titta till dig?",
            "follow_up_critical": "Sök hjälp omedelbart. Kan du ringa nödnumret eller en betrodd anhörig direkt?",
            "action_low": "Svara lugnt och följ upp om läget förändras.",
            "action_medium": "Uppmuntra till att dricka, äta, vila och följa upp snart.",
            "action_high": "Uppmuntra till omedelbar kontakt med anhörig eller vårdare och tät uppföljning.",
            "action_critical": "Rekommendera omedelbar medicinsk hjälp eller larmtjänst.",
            "reason_repeat": "Liknande varningssignaler har nämnts nyligen.",
            "reason_elderly": "Hög ålder / skörhet gör symtomen mer betydelsefulla.",
        },
    }
    return translations.get(language, translations["en"])[key]


def _run_rule_engine(
    current_message: str,
    recent_user_messages: list[str],
    preferred_language: str | None,
    elderly: bool,
    frailty_adjustment: int,
) -> dict[str, Any]:
    """Original rule-based engine — always fast, always safe."""
    language = detect_language(current_message, preferred_language)
    current_signals = _extract_signals(current_message)

    recent_signal_counter: Counter[str] = Counter()
    for msg in recent_user_messages[-5:]:
        for signal in _extract_signals(msg):
            recent_signal_counter[signal] += 1

    score = 0
    reasons: list[str] = []
    categories: list[str] = []

    for signal in current_signals:
        rule = SIGNAL_RULES[signal]
        score += int(rule["weight"])
        categories.append(str(rule["category"]))
        reasons.append(f"Detected signal: {signal.replace('_', ' ')}")

        if recent_signal_counter[signal] > 0:
            repeat_bonus = min(3, recent_signal_counter[signal])
            score += repeat_bonus
            reasons.append(
                f"{_localize(language, 'reason_repeat')} ({signal.replace('_', ' ')})"
            )

    if len(current_signals) >= 2:
        score += len(current_signals) - 1
        reasons.append("Multiple concerning signals were detected.")

    if elderly:
        score += 2
        reasons.append(_localize(language, "reason_elderly"))

    if frailty_adjustment > 0:
        score += frailty_adjustment
        reasons.append("Additional frailty adjustment applied.")

    if any(s in CRITICAL_SIGNALS for s in current_signals):
        score = max(score, 10)

    if "fall" in current_signals and ("dizziness" in current_signals or "pain" in current_signals):
        score += 3
        reasons.append("Fall combined with dizziness/pain increases urgency.")

    if score <= 2:
        risk_level = "low"
    elif score <= 6:
        risk_level = "medium"
    elif score <= 11:
        risk_level = "high"
    else:
        risk_level = "critical"

    if "chest_pain" in current_signals:
        risk_level = "critical"

    if "chest_pain" in current_signals:
        category = "cardiac"
    elif "fall" in current_signals:
        category = "fall"
    elif "dizziness" in current_signals:
        category = "dizziness"
    elif "poor_appetite" in current_signals or "no_water" in current_signals:
        category = "nutrition_hydration"
    elif "sadness_loneliness" in current_signals:
        category = "emotional"
    elif "fatigue" in current_signals or "poor_sleep" in current_signals:
        category = "general_wellbeing"
    elif "pain" in current_signals:
        category = "pain"
    else:
        category = categories[0] if categories else "general_wellbeing"

    follow_up_question = _localize(language, f"follow_up_{risk_level}")
    suggested_action = _localize(language, f"action_{risk_level}")

    should_alert_family = risk_level in {"high", "critical"} or (
        risk_level == "medium" and recent_signal_counter.total() >= 2
    )

    return {
        "score": min(score, 10),
        "risk_level": risk_level,
        "category": category,
        "signals": current_signals,
        "reasons": reasons,
        "suggested_action": suggested_action,
        "follow_up_question": follow_up_question,
        "should_alert_family": should_alert_family,
        "language": language,
        "assessed_by": "rules",
    }

# LLM risk assessment


_SYSTEM_PROMPT = """You are a clinical risk assessment assistant for a welfare bot
that monitors elderly people living alone.

Your job: analyse the user's message and return ONLY a JSON object — no prose,
no markdown, no explanation — with exactly these fields:

{
  "risk_level": "low" | "medium" | "high" | "critical",
  "score": <integer 0-10>,
  "signals": [<list of short signal strings detected, e.g. "chest pain", "loneliness">],
  "category": <primary concern category as a short string>,
  "reasoning": <one sentence explaining the assessment>,
  "should_alert_family": <true | false>
}

Risk level definitions:
- low (0-3): Normal daily complaints, minor tiredness, general chat
- medium (4-5): Poor sleep, reduced appetite, mild loneliness, fatigue
- high (6-7): Not eating/drinking, significant pain, fall, strong emotional distress
- critical (8-10): Chest pain, breathing difficulty, fall with injury, severe confusion,
  expressions of hopelessness or not wanting to continue living

Important nuances:
- "I'm fine" said repeatedly may signal masking — note it but do not over-escalate
- Indirect expressions like "it's been hard" or "I don't see the point" can be medium/high
- Always err on the side of caution for physical symptoms in elderly users
- The message may be in English, Finnish, or Swedish — assess regardless of language

Return ONLY the JSON object. No other text."""


def _build_user_prompt(
    message: str,
    recent_messages: list[str],
    language: str,
) -> str:
    context = ""
    if recent_messages:
        recent = "\n".join(f"- {m}" for m in recent_messages[-3:])
        context = f"\n\nRecent messages from this user (for context):\n{recent}"

    return (
        f"Language detected: {language}\n\n"
        f"Current message: {message}"
        f"{context}"
    )


def _parse_llm_response(raw: str) -> dict[str, Any] | None:
    """Parse and validate the LLM JSON response. Returns None if invalid."""
    try:
        # Strip markdown code fences if present
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()

        data = json.loads(text)

        # Validate required fields and types
        if data.get("risk_level") not in RISK_LEVELS:
            return None
        if not isinstance(data.get("score"), (int, float)):
            return None
        if not isinstance(data.get("signals"), list):
            return None

        return {
            "risk_level": data["risk_level"],
            "score": int(min(max(data["score"], 0), 10)),
            "signals": [str(s) for s in data["signals"]],
            "category": str(data.get("category", "general_wellbeing")),
            "reasoning": str(data.get("reasoning", "")),
            "should_alert_family": bool(data.get("should_alert_family", False)),
        }
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.warning("LLM risk response parse failed: %s | raw: %.200s", e, raw)
        return None


def _call_llm_sync(message: str, recent_messages: list[str], language: str) -> dict[str, Any] | None:
    """
    Call OpenAI synchronously with a timeout.
    Returns parsed result dict or None on any failure.
    """
    try:
        from openai import OpenAI
        client = OpenAI(timeout=_LLM_TIMEOUT)

        response = client.chat.completions.create(
            model=_LLM_MODEL,
            max_tokens=300,
            temperature=0.1,  # Low temperature = consistent structured output
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(message, recent_messages, language)},
            ],
        )

        raw = response.choices[0].message.content or ""
        return _parse_llm_response(raw)

    except Exception as e:
        logger.warning("LLM risk assessment failed (falling back to rules): %s", e)
        return None


# Public API — assess()

def assess(
    current_message: str,
    recent_user_messages: list[str] | None = None,
    preferred_language: str | None = None,
    elderly: bool = True,
    frailty_adjustment: int = 0,
) -> dict[str, Any]:
    """
    Assess the risk level of a message.

    Always runs the rule engine first (instant, safe fallback).
    If LLM_RISK_ENABLED=true, also runs the LLM assessment and merges results:
    - LLM result is used when valid
    - Safety override: if rules flagged critical, result is never downgraded below critical
    - On any LLM failure, rule result is returned transparently
    """
    recent_user_messages = recent_user_messages or []

    # Step 1: Rule engine (always runs)
    rule_result = _run_rule_engine(
        current_message, recent_user_messages,
        preferred_language, elderly, frailty_adjustment,
    )

    if not _LLM_ENABLED:
        return rule_result

    language = rule_result["language"]

    # Step 2: LLM assessment
    llm_data = _call_llm_sync(current_message, recent_user_messages, language)

    if llm_data is None:
        # LLM failed — return rule result silently
        return rule_result

    # Step 3: Merge — safety-first
    # Never downgrade below what the rules found (rules catch keyword emergencies)
    final_level = _higher_level(llm_data["risk_level"], rule_result["risk_level"])
    final_score = max(llm_data["score"], rule_result["score"])

    # Merge signals from both engines (deduplicated)
    merged_signals = list(dict.fromkeys(
        llm_data["signals"] + rule_result["signals"]
    ))

    # Combine reasons
    reasons = rule_result["reasons"].copy()
    if llm_data["reasoning"]:
        reasons.append(f"LLM assessment: {llm_data['reasoning']}")

    follow_up_question = _localize(language, f"follow_up_{final_level}")
    suggested_action = _localize(language, f"action_{final_level}")

    should_alert = (
        llm_data["should_alert_family"]
        or rule_result["should_alert_family"]
        or final_level in {"high", "critical"}
    )

    return {
        "score": final_score,
        "risk_level": final_level,
        "category": llm_data["category"] or rule_result["category"],
        "signals": merged_signals,
        "reasons": reasons,
        "suggested_action": suggested_action,
        "follow_up_question": follow_up_question,
        "should_alert_family": should_alert,
        "language": language,
        "assessed_by": "llm+rules",
        "llm_reasoning": llm_data["reasoning"],
    }

def _score_to_level(score: int) -> str:
    score = max(0, min(int(score), 10))

    if score >= 8:
        return "critical"
    if score >= 6:
        return "high"
    if score >= 4:
        return "medium"
    return "low"


# RiskService class wrapper (keeps existing imports working)
class RiskService:
    """Class wrapper around assess() for test compatibility."""

    def analyze(self, message: str) -> dict[str, Any]:
        normalized = _normalize_text(message)

        result = assess(message, elderly=False)

        high_food_water_phrases = [
            "haven't eaten",
            "have not eaten",
            "not eaten",
            "haven't drunk",
            "have not drunk",
            "not drunk",
            "en ole syönyt",
            "enkä juonut",
            "en ole juonut",
        ]

        if any(phrase in normalized for phrase in high_food_water_phrases):
            result["score"] = max(int(result.get("score", 0)), 7)
            result["risk_level"] = _score_to_level(result["score"])

            signals = list(result.get("signals", []))
            if "poor_appetite" not in signals:
                signals.append("poor_appetite")
            if "no_water" not in signals:
                signals.append("no_water")
            result["signals"] = signals

        return {
            "risk_level": result["risk_level"],
            "risk_score": result["score"],
            "signals": result["signals"],
        }

    def _score_to_level(self, score: int) -> str:
        return _score_to_level(score)