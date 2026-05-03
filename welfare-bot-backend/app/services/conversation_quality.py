"""
app/services/conversation_quality.py

LLM-based conversation quality scoring.
After each session, evaluates:
- Did the bot gather all 6 key metrics? (sleep, food, hydration, pain, mood, safety)
- Was the user engaged? (short vs long responses)
- Did the bot ask only one question at a time?
- Was the conversation natural and warm?

Score 0-100 stored per session for longitudinal tracking.
"""
from __future__ import annotations

import logging
import json
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


QUALITY_SYSTEM_PROMPT = """You are evaluating the quality of a wellbeing check-in conversation between a care bot and an elderly user.

Score the conversation from 0 to 100 based on:
1. Coverage (0-25): Did the bot ask about sleep, food, hydration, pain, mood and safety?
2. Engagement (0-25): Were the user's responses substantive (not just yes/no)?
3. Conversation flow (0-25): Did the bot ask only one question at a time? Was it natural?
4. Warmth (0-25): Was the bot warm, patient and appropriate for an elderly user?

Return ONLY a JSON object with this exact format:
{
  "total_score": 75,
  "coverage_score": 20,
  "engagement_score": 18,
  "flow_score": 22,
  "warmth_score": 15,
  "metrics_covered": ["sleep", "food", "mood"],
  "metrics_missing": ["hydration", "pain", "safety"],
  "strengths": "Bot was warm and asked good follow-up questions.",
  "improvements": "Did not ask about pain or safety. Some responses were too long."
}"""


class ConversationQualityResult:
    def __init__(
        self,
        user_id: int,
        total_score: int,
        coverage_score: int,
        engagement_score: int,
        flow_score: int,
        warmth_score: int,
        metrics_covered: list[str],
        metrics_missing: list[str],
        strengths: str,
        improvements: str,
        message_count: int,
    ):
        self.user_id = user_id
        self.total_score = total_score
        self.coverage_score = coverage_score
        self.engagement_score = engagement_score
        self.flow_score = flow_score
        self.warmth_score = warmth_score
        self.metrics_covered = metrics_covered
        self.metrics_missing = metrics_missing
        self.strengths = strengths
        self.improvements = improvements
        self.message_count = message_count


def score_conversation(
    user_id: int,
    messages: list[dict],
) -> Optional[ConversationQualityResult]:
    """
    Score a conversation using GPT-4o-mini.
    messages: list of {"role": "user"|"assistant", "content": "..."}
    """
    if len(messages) < 4:
        logger.debug("Too few messages to score conversation for user %d", user_id)
        return None

    try:
        from app.integrations.openai_client import client

        # Format conversation for evaluation
        conversation_text = "\n".join(
            f"{m['role'].upper()}: {m['content']}"
            for m in messages
        )

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": QUALITY_SYSTEM_PROMPT},
                {"role": "user", "content": f"Evaluate this conversation:\n\n{conversation_text}"},
            ],
            max_tokens=400,
            temperature=0.1,
        )

        raw = response.choices[0].message.content.strip()

        # Strip markdown code blocks if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        data = json.loads(raw)

        return ConversationQualityResult(
            user_id=user_id,
            total_score=int(data.get("total_score", 0)),
            coverage_score=int(data.get("coverage_score", 0)),
            engagement_score=int(data.get("engagement_score", 0)),
            flow_score=int(data.get("flow_score", 0)),
            warmth_score=int(data.get("warmth_score", 0)),
            metrics_covered=data.get("metrics_covered", []),
            metrics_missing=data.get("metrics_missing", []),
            strengths=data.get("strengths", ""),
            improvements=data.get("improvements", ""),
            message_count=len(messages),
        )

    except Exception as e:
        logger.error("Conversation quality scoring failed for user %d: %s", user_id, e)
        return None


def score_todays_conversations(db) -> list[ConversationQualityResult]:
    """
    Score today's completed conversations for all users.
    Called by scheduler at end of day.
    """
    from datetime import timezone
    from app.db.models.user import User
    from app.db.models.conversation_message import ConversationMessage

    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    ).replace(tzinfo=None)

    users = db.query(User).filter(
        User.is_active == True,
        User.role != "admin",
    ).all()

    results = []
    for user in users:
        messages = (
            db.query(ConversationMessage)
            .filter(
                ConversationMessage.user_id == user.id,
                ConversationMessage.created_at >= today_start,
            )
            .order_by(ConversationMessage.created_at)
            .all()
        )

        if len(messages) < 4:
            continue

        msg_dicts = [{"role": m.role, "content": m.content} for m in messages]
        result = score_conversation(user_id=user.id, messages=msg_dicts)

        if result:
            results.append(result)
            logger.info(
                "Conversation quality for user %d: %d/100",
                user.id, result.total_score,
            )

    return results