from __future__ import annotations

from sqlalchemy import String

def looks_like_finnish(text: str) -> bool:
    hints = [
        " on ", " että ", " sinä", " olet", " vointi", " turvassa",
        " voitko", " tärkeää", " juoda", " syödä",
    ]
    lowered = f" {text.lower()} "
    return sum(h in lowered for h in hints) >= 2


def looks_like_swedish(text: str) -> bool:
    hints = [
        " är ", " och ", " du ", " trygg", " kan du",
        " viktigt", " dricka", " äta", " mår",
    ]
    lowered = f" {text.lower()} "
    return sum(h in lowered for h in hints) >= 2


def looks_like_english(text: str) -> bool:
    hints = [
        " the ", " and ", " are ", " you ", " important",
        " safe ", " drink ", " eat ", " feel ",
    ]
    lowered = f" {text.lower()} "
    return sum(h in lowered for h in hints) >= 2


def is_mixed_language(text: str, target_language: str) -> bool:
    target_language = (target_language or "en").lower()

    en = looks_like_english(text)
    fi = looks_like_finnish(text)
    sv = looks_like_swedish(text)

    if target_language == "fi":
        return en or sv
    if target_language == "sv":
        return en or fi
    return fi or sv


def fallback_message_for_language(language: str, risk_level: str, follow_up_question: str) -> str:
    language = (language or "en").lower()

    if language == "fi":
        if risk_level == "critical":
            return "Tilanteesi voi vaatia kiireellistä apua. Hakeudu heti hoitoon tai soita hätänumeroon."
        return f"Ymmärrän. Haluan vastata mahdollisimman selkeästi ja rauhallisesti. {follow_up_question}"

    if language == "sv":
        if risk_level == "critical":
            return "Din situation kan kräva omedelbar hjälp. Sök vård direkt eller ring nödnumret."
        return f"Jag förstår. Jag vill svara lugnt och tydligt. {follow_up_question}"

    if risk_level == "critical":
        return "Your situation may require urgent help. Please seek immediate medical support or call emergency services now."
    return f"I understand. I want to respond as clearly and calmly as possible. {follow_up_question}"