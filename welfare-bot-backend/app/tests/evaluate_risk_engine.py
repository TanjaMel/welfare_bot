from __future__ import annotations

from collections import Counter

from app.services.risk_service import assess
from app.tests.risk_eval_cases import RISK_EVAL_CASES


def run_evaluation() -> None:
    total = len(RISK_EVAL_CASES)
    correct_risk = 0
    correct_category = 0

    predicted_risk_counter: Counter[str] = Counter()
    expected_risk_counter: Counter[str] = Counter()

    print("=" * 80)
    print("RISK ENGINE EVALUATION")
    print("=" * 80)

    for index, case in enumerate(RISK_EVAL_CASES, start=1):
        result = assess(
            current_message=case["text"],
            recent_user_messages=[],
            preferred_language=None,
            elderly=True,
        )

        predicted_risk = result["risk_level"]
        predicted_category = result["category"]

        expected_risk = case["expected_risk"]
        expected_category = case["expected_category"]

        expected_risk_counter[expected_risk] += 1
        predicted_risk_counter[predicted_risk] += 1

        is_risk_correct = predicted_risk == expected_risk
        is_category_correct = predicted_category == expected_category

        if is_risk_correct:
            correct_risk += 1

        if is_category_correct:
            correct_category += 1

        print(f"\nCase {index}")
        print(f"Text: {case['text']}")
        print(f"Expected risk:     {expected_risk}")
        print(f"Predicted risk:    {predicted_risk}")
        print(f"Expected category: {expected_category}")
        print(f"Predicted category:{predicted_category}")
        print(f"Signals:           {result['signals']}")
        print(f"Score:             {result['score']}")
        print(f"Risk correct:      {is_risk_correct}")
        print(f"Category correct:  {is_category_correct}")

    risk_accuracy = correct_risk / total if total else 0
    category_accuracy = correct_category / total if total else 0

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total cases:            {total}")
    print(f"Correct risk level:     {correct_risk}/{total}")
    print(f"Correct category:       {correct_category}/{total}")
    print(f"Risk accuracy:          {risk_accuracy:.2%}")
    print(f"Category accuracy:      {category_accuracy:.2%}")
    print(f"Expected distribution:  {dict(expected_risk_counter)}")
    print(f"Predicted distribution: {dict(predicted_risk_counter)}")
    print("=" * 80)


if __name__ == "__main__":
    run_evaluation()