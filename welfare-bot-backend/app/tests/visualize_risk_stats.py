import matplotlib.pyplot as plt
from collections import Counter
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models.risk_event import RiskEvent


def plot_risk_level_distribution(events):
    levels = [e.risk_level for e in events]
    counts = Counter(levels)

    plt.figure()
    plt.bar(counts.keys(), counts.values())
    plt.title("Risk Level Distribution")
    plt.xlabel("Risk Level")
    plt.ylabel("Count")
    plt.show()


def plot_risk_category_distribution(events):
    cats = [e.risk_category for e in events]
    counts = Counter(cats)

    plt.figure()
    plt.bar(counts.keys(), counts.values())
    plt.xticks(rotation=45)
    plt.title("Risk Category Distribution")
    plt.show()


def plot_risk_score_trend(events):
    events = sorted(events, key=lambda x: x.created_at)

    dates = [e.created_at for e in events]
    scores = [e.risk_score for e in events]

    plt.figure()
    plt.plot(dates, scores)
    plt.title("Risk Score Over Time")
    plt.xticks(rotation=45)
    plt.show()


def main():
    db: Session = SessionLocal()

    events = db.query(RiskEvent).all()

    plot_risk_level_distribution(events)
    plot_risk_category_distribution(events)
    plot_risk_score_trend(events)


if __name__ == "__main__":
    main()