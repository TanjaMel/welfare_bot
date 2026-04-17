from __future__ import annotations

RISK_EVAL_CASES = [
    {
        "text": "I feel fine today",
        "expected_risk": "low",
        "expected_category": "general_wellbeing",
    },
    {
        "text": "I feel lonely today",
        "expected_risk": "medium",
        "expected_category": "emotional",
    },
    {
        "text": "I slept badly and feel tired",
        "expected_risk": "medium",
        "expected_category": "general_wellbeing",
    },
    {
        "text": "I did not eat today",
        "expected_risk": "medium",
        "expected_category": "nutrition_hydration",
    },
    {
        "text": "I did not drink water today",
        "expected_risk": "medium",
        "expected_category": "nutrition_hydration",
    },
    {
        "text": "I feel dizzy",
        "expected_risk": "high",
        "expected_category": "dizziness",
    },
    {
        "text": "I fell and now I feel pain",
        "expected_risk": "high",
        "expected_category": "fall",
    },
    {
        "text": "I have chest pain",
        "expected_risk": "critical",
        "expected_category": "cardiac",
    },
    {
        "text": "I feel lonely and tired today",
        "expected_risk": "high",
        "expected_category": "emotional",
    },
    {
        "text": "I did not eat, did not drink, and I feel weak",
        "expected_risk": "high",
        "expected_category": "nutrition_hydration",
    },
    {
        "text": "En ole syönyt tänään ja minua huimaa",
        "expected_risk": "high",
        "expected_category": "dizziness",
    },
    {
        "text": "Jag känner mig ensam och trött",
        "expected_risk": "high",
        "expected_category": "emotional",
    },
    {
        "text": "Minulla on rintakipu",
        "expected_risk": "critical",
        "expected_category": "cardiac",
    },
    {
        "text": "Jag föll och nu har jag ont",
        "expected_risk": "high",
        "expected_category": "fall",
    },
    {
        "text": "I am a bit tired but otherwise okay",
        "expected_risk": "medium",
        "expected_category": "fatigue",
    },
]