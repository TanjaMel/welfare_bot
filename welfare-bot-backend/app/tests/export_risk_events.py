import csv
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models.risk_event import RiskEvent


def export_to_csv(path="risk_events.csv"):
    db: Session = SessionLocal()

    events = db.query(RiskEvent).all()

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "user_id", "risk_level", "score", "category", "created_at"])

        for e in events:
            writer.writerow([
                e.id,
                e.user_id,
                e.risk_level,
                e.risk_score,
                e.risk_category,
                e.created_at,
            ])

    print("Export done:", path)


if __name__ == "__main__":
    export_to_csv()