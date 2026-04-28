"""
app/services/risk_service_class.py

Adds a RiskService class that wraps whatever functions already exist in
risk_service.py — so tests can import RiskService without touching the
original file.

Place this file at: welfare-bot-backend/app/services/risk_service_class.py

Then add one line to the BOTTOM of your existing risk_service.py:

    from app.services.risk_service_class import RiskService  # noqa: F401
"""

from __future__ import annotations
import re
from typing import Any


# ---------------------------------------------------------------------------
# Signal dictionaries — EN / FI / SV
# Scores follow the README table:  low 0-3 | medium 4-5 | high 6-7 | critical 8-10
# ---------------------------------------------------------------------------

SIGNALS: dict[str, dict[str, int]] = {
    # --- Critical (8-10) ---
    "chest pain":          8, "rintakipu": 8, "bröstsmärta": 8,
    "chest ache":          8,
    "difficulty breathing": 9, "hengitysvaikeus": 9, "andningssvårigheter": 9,
    "can't breathe":       9, "ei pysty hengittämään": 9,
    "unconscious":        10, "tajuton": 10, "medvetslös": 10,
    "collapsed":           9,

    # --- High (6-7) ---
    "fell down":           6, "kaaduin": 6, "föll": 6,
    "fallen":              6, "fall":    6,
    "can't get up":        7, "en pysty nousemaan": 7,
    "severe pain":         7, "kova kipu": 7, "svår smärta": 7,
    "haven't eaten":       6, "en ole syönyt": 6, "har inte ätit": 6,
    "no food":             6, "ei ruokaa": 6,
    "haven't drunk":       6, "en ole juonut": 6, "har inte druckit": 6,
    "no water":            6, "ei vettä": 6,
    "very weak":           6, "todella väsynyt": 6, "mycket svag": 6,
    "hip hurts":           6,

    # --- Medium (4-5) ---
    "didn't sleep":        4, "en nukkunut": 4, "sov inte": 4,
    "couldn't sleep":      4, "en jaksanut nukkua": 4,
    "poor sleep":          4, "huono uni": 4, "dålig sömn": 4,
    "lonely":              4, "yksinäinen": 4, "ensam": 4,
    "loneliness":          4, "yksinäisyys": 4,
    "not well":            4, "mår inte bra": 4,
    "tired":               3, "väsynyt": 3, "trött": 3,
    "fatigue":             4,
    "mild pain":           4,
    "not eating well":     4,

    # --- Low (1-3) — notable but not alarming ---
    "a bit":               1, "vähän": 1, "lite": 1,
}


class RiskService:
    """
    Stateless risk assessment service.

    Usage:
        svc = RiskService()
        result = svc.analyze("I have chest pain.")
        # {"risk_level": "critical", "risk_score": 8, "signals": ["chest pain"]}
    """

    def analyze(self, message: str) -> dict[str, Any]:
        """
        Analyse a single message and return risk level, score, and signals.
        Delegates to the existing module-level analyze_risk() if present,
        otherwise runs its own lightweight implementation.
        """
        # --- Try to reuse existing module function first ---
        try:
            from app.services.risk_service import analyze_risk  # type: ignore
            return analyze_risk(message)
        except ImportError:
            pass

        # --- Fallback: built-in implementation ---
        return self._analyze_internally(message)

    def _analyze_internally(self, message: str) -> dict[str, Any]:
        if not message or not message.strip():
            return {"risk_level": "low", "risk_score": 0, "signals": []}

        text = message.lower()
        found_signals: list[str] = []
        max_score = 0

        for phrase, score in SIGNALS.items():
            if phrase in text:
                found_signals.append(phrase)
                if score > max_score:
                    max_score = score

        # Clamp to [0, 10]
        final_score = min(max(max_score, 0), 10)
        return {
            "risk_level": self._score_to_level(final_score),
            "risk_score": final_score,
            "signals": found_signals,
        }

    def _score_to_level(self, score: int) -> str:
        """Map a numeric score to a risk level string (matches README table)."""
        # Try existing module function first
        try:
            from app.services.risk_service import score_to_level  # type: ignore
            return score_to_level(score)
        except ImportError:
            pass

        if score >= 8:
            return "critical"
        if score >= 6:
            return "high"
        if score >= 4:
            return "medium"
        return "low"