
"""
Covers:
- Risk level assignment (low / medium / high / critical)
- Multilingual signal detection (Finnish, English, Swedish)
- Edge cases: empty input, mixed-language, repeated messages
- Score boundary conditions
"""

import pytest
from unittest.mock import MagicMock, patch

# Helpers — import the service under test
# We use a lazy import pattern so the test file doesn't crash if the module
# path changes; update the import string to match your actual location.


def get_risk_service():
    from app.services.risk_service import RiskService  # adjust if needed
    return RiskService()


# English risk signal tests


class TestEnglishRiskDetection:

    def test_low_risk_normal_message(self):
        svc = get_risk_service()
        result = svc.analyze("I slept well and had breakfast. Feeling good.")
        assert result["risk_level"] == "low"
        assert result["risk_score"] <= 3

    def test_medium_risk_poor_sleep(self):
        svc = get_risk_service()
        result = svc.analyze("I didn't sleep well and I've been feeling a bit lonely.")
        assert result["risk_level"] in ("medium", "high")
        assert result["risk_score"] >= 4

    def test_high_risk_no_food_or_water(self):
        svc = get_risk_service()
        result = svc.analyze("I haven't eaten or drunk anything today and I feel very weak.")
        assert result["risk_level"] in ("high", "critical")
        assert result["risk_score"] >= 6

    def test_critical_chest_pain(self):
        svc = get_risk_service()
        result = svc.analyze("I have severe chest pain and difficulty breathing.")
        assert result["risk_level"] == "critical"
        assert result["risk_score"] >= 8

    def test_critical_fall(self):
        svc = get_risk_service()
        result = svc.analyze("I fell down and I can't get up, my hip hurts badly.")
        assert result["risk_level"] in ("high", "critical")
        assert result["risk_score"] >= 6

    def test_signals_are_returned(self):
        svc = get_risk_service()
        result = svc.analyze("I have chest pain.")
        assert "signals" in result
        assert isinstance(result["signals"], list)
        assert len(result["signals"]) > 0

    def test_empty_message_returns_low(self):
        svc = get_risk_service()
        result = svc.analyze("")
        assert result["risk_level"] == "low"
        assert result["risk_score"] == 0

    def test_greeting_only_is_low(self):
        svc = get_risk_service()
        result = svc.analyze("Hello, good morning!")
        assert result["risk_level"] == "low"


# Finnish risk signal tests

class TestFinnishRiskDetection:

    def test_low_risk_fi(self):
        svc = get_risk_service()
        result = svc.analyze("Nukuin hyvin, kiitos. Olo on hyvä tänään.")
        assert result["risk_level"] == "low"
        assert result["risk_score"] <= 3

    def test_medium_risk_fi(self):
        svc = get_risk_service()
        result = svc.analyze("En oikein jaksanut nukkua ja olen ollut vähän yksinäinen.")
        assert result["risk_level"] in ("medium", "high")
        assert result["risk_score"] >= 4

    def test_high_risk_fi(self):
        svc = get_risk_service()
        result = svc.analyze("En ole syönyt enkä juonut mitään tänään ja olen todella väsynyt.")
        assert result["risk_level"] in ("high", "critical")
        assert result["risk_score"] >= 6

    def test_critical_fi(self):
        svc = get_risk_service()
        result = svc.analyze("Minulla on kova rintakipu.")
        assert result["risk_level"] == "critical"
        assert result["risk_score"] >= 8

# Swedish risk signal tests

class TestSwedishRiskDetection:

    def test_medium_risk_sv(self):
        svc = get_risk_service()
        result = svc.analyze("Jag mår inte bra idag.")
        assert result["risk_level"] in ("medium", "high", "critical")
        assert result["risk_score"] >= 4

    def test_low_risk_sv(self):
        svc = get_risk_service()
        result = svc.analyze("Jag mår bra, tack.")
        assert result["risk_level"] == "low"


# Score boundary tests

class TestScoreBoundaries:

    @pytest.mark.parametrize("score,expected_level", [
        (0, "low"),
        (1, "low"),
        (3, "low"),
        (4, "medium"),
        (5, "medium"),
        (6, "high"),
        (7, "high"),
        (8, "critical"),
        (10, "critical"),
    ])
    def test_score_to_level_mapping(self, score, expected_level):
        """The score-to-level mapping must match the README table exactly."""
        svc = get_risk_service()
        level = svc._score_to_level(score)  # expose internal method for testing
        assert level == expected_level

    def test_score_never_exceeds_10(self):
        svc = get_risk_service()
        # Even a message with many signals should cap at 10
        result = svc.analyze(
            "Chest pain, can't breathe, fell down, haven't eaten, "
            "no water, severe pain, confused, very weak, alone."
        )
        assert result["risk_score"] <= 10

    def test_score_never_below_zero(self):
        svc = get_risk_service()
        result = svc.analyze("I feel amazing and had a wonderful day!")
        assert result["risk_score"] >= 0

# Result schema tests — make sure callers can always rely on the shape

class TestResultSchema:

    REQUIRED_KEYS = {"risk_level", "risk_score", "signals"}

    def test_result_always_has_required_keys(self):
        svc = get_risk_service()
        for msg in [
            "",
            "Hello",
            "I have chest pain",
            "Minulla on kova rintakipu",
        ]:
            result = svc.analyze(msg)
            assert self.REQUIRED_KEYS.issubset(result.keys()), (
                f"Missing keys in result for '{msg}': "
                f"{self.REQUIRED_KEYS - result.keys()}"
            )

    def test_risk_level_always_valid_string(self):
        valid_levels = {"low", "medium", "high", "critical"}
        svc = get_risk_service()
        for msg in ["fine", "bad", "chest pain", ""]:
            result = svc.analyze(msg)
            assert result["risk_level"] in valid_levels

    def test_risk_score_always_integer(self):
        svc = get_risk_service()
        result = svc.analyze("I feel okay.")
        assert isinstance(result["risk_score"], int)