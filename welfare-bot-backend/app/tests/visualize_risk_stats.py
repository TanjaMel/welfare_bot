from __future__ import annotations

from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt

from app.services.risk_service import assess
from app.tests.risk_eval_cases import RISK_EVAL_CASES


OUTPUT_DIR = Path("docs/charts")


def ensure_output_dir() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def build_stats() -> tuple[Counter[str], Counter[str]]:
    risk_counter: Counter[str] = Counter()
    category_counter: Counter[str] = Counter()

    for case in RISK_EVAL_CASES:
        result = assess(
            current_message=case["text"],
            recent_user_messages=[],
            preferred_language=None,
            elderly=True,
        )
        risk_counter[result["risk_level"]] += 1
        category_counter[result["category"]] += 1

    return risk_counter, category_counter


def save_bar_chart(counter: Counter[str], title: str, filename: str) -> None:
    labels = list(counter.keys())
    values = list(counter.values())

    plt.figure(figsize=(8, 5))
    plt.bar(labels, values)
    plt.title(title)
    plt.xlabel("Category")
    plt.ylabel("Count")
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / filename, dpi=150)
    plt.close()


def main() -> None:
    ensure_output_dir()
    risk_counter, category_counter = build_stats()

    save_bar_chart(
        risk_counter,
        title="Predicted risk levels",
        filename="predicted_risk_levels.png",
    )

    save_bar_chart(
        category_counter,
        title="Predicted risk categories",
        filename="predicted_risk_categories.png",
    )

    print("Charts saved to:")
    print(OUTPUT_DIR / "predicted_risk_levels.png")
    print(OUTPUT_DIR / "predicted_risk_categories.png")


if __name__ == "__main__":
    main()