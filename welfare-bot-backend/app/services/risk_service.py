from __future__ import annotations

from collections import Counter
from typing import Any

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
        ],
        "weight": 3,
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
    found: list[str] = []

    for signal_name, config in SIGNAL_RULES.items():
        if any(pattern in lowered for pattern in config["patterns"]):
            found.append(signal_name)

    return found


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


def assess(
    current_message: str,
    recent_user_messages: list[str] | None = None,
    preferred_language: str | None = None,
    elderly: bool = True,
    frailty_adjustment: int = 0,
) -> dict[str, Any]:
    recent_user_messages = recent_user_messages or []
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
        combo_bonus = len(current_signals) - 1
        score += combo_bonus
        reasons.append("Multiple concerning signals were detected in the same message.")

    if elderly:
        score += 2
        reasons.append(_localize(language, "reason_elderly"))

    if frailty_adjustment > 0:
        score += frailty_adjustment
        reasons.append("Additional frailty adjustment applied.")

    if any(signal in CRITICAL_SIGNALS for signal in current_signals):
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

    if risk_level == "low":
        suggested_action = _localize(language, "action_low")
        follow_up_question = _localize(language, "follow_up_low")
    elif risk_level == "medium":
        suggested_action = _localize(language, "action_medium")
        follow_up_question = _localize(language, "follow_up_medium")
    elif risk_level == "high":
        suggested_action = _localize(language, "action_high")
        follow_up_question = _localize(language, "follow_up_high")
    else:
        suggested_action = _localize(language, "action_critical")
        follow_up_question = _localize(language, "follow_up_critical")

    should_alert_family = risk_level in {"high", "critical"} or (
        risk_level == "medium" and recent_signal_counter.total() >= 2
    )

    return {
        "score": score,
        "risk_level": risk_level,
        "category": category,
        "signals": current_signals,
        "reasons": reasons,
        "suggested_action": suggested_action,
        "follow_up_question": follow_up_question,
        "should_alert_family": should_alert_family,
        "language": language,
    }