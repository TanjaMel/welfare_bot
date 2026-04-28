"""
Conversation memory for welfare bot.

Two responsibilities:
1. summarize_session()  — called after a session ends (20 messages or bot closing).
   Asks GPT-4o-mini to produce a structured JSON summary of the conversation and
   saves it to user.memory_summary.

2. get_memory_context()  — called at the start of _generate_reply().
   Returns a short system-prompt snippet the bot can use to personalise its
   response based on what it knows from previous sessions.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_SUMMARY_MODEL = os.getenv("LLM_MEMORY_MODEL", "gpt-4o-mini")
_MEMORY_ENABLED = bool(os.getenv("OPENAI_API_KEY"))

# Summary schema 


_SUMMARY_SYSTEM_PROMPT = """You are a clinical assistant summarising a welfare check-in
conversation with an elderly person. Extract key information and return ONLY a JSON
object — no prose, no markdown — with exactly these fields:

{
  "mood_trend": "improving" | "stable" | "declining" | "unknown",
  "key_concerns": [<list of up to 5 short strings, e.g. "poor sleep", "hip pain">],
  "physical_symptoms": [<list of short strings>],
  "social_situation": <one sentence or null>,
  "risk_trajectory": "improving" | "stable" | "worsening" | "unknown",
  "notable_changes": <one sentence describing anything new vs last session, or null>,
  "follow_up_priorities": [<up to 3 short strings the bot should ask about next session>],
  "session_risk_level": "low" | "medium" | "high" | "critical"
}

Be concise. This summary will be injected into the next conversation so the bot
can refer back to previous sessions naturally. Do not include the user's name or
any identifying information beyond what is clinically relevant."""


def summarize_session(
    user_id: int,
    messages: list[dict[str, str]],
    db,
    previous_summary: str | None = None,
) -> bool:
    """
    Summarise the current session and save to user.memory_summary.

    Args:
        user_id: The user whose session is being summarised.
        messages: List of {"role": "user"|"assistant", "content": "..."} dicts
                  for the current session.
        db: SQLAlchemy session.
        previous_summary: The user's existing memory_summary JSON string (if any).

    Returns:
        True if summary was saved successfully, False otherwise.
    """
    if not _MEMORY_ENABLED:
        logger.debug("Memory summarization skipped — no OPENAI_API_KEY")
        return False

    if not messages:
        return False

    user_messages = [m for m in messages if m["role"] == "user"]
    if len(user_messages) < 2:
        # Too few messages to summarise meaningfully
        return False

    try:
        from openai import OpenAI
        from app.db.models.user import User

        client = OpenAI(timeout=15)

        # Build the conversation transcript
        transcript = "\n".join(
            f"{m['role'].upper()}: {m['content']}" for m in messages[-30:]
        )

        context = ""
        if previous_summary:
            try:
                prev = json.loads(previous_summary)
                context = (
                    f"\n\nPrevious session summary for context:\n"
                    f"- Mood trend: {prev.get('mood_trend', 'unknown')}\n"
                    f"- Key concerns: {', '.join(prev.get('key_concerns', []))}\n"
                    f"- Risk trajectory: {prev.get('risk_trajectory', 'unknown')}"
                )
            except (json.JSONDecodeError, TypeError):
                pass

        user_prompt = (
            f"Summarise this welfare check-in conversation.{context}\n\n"
            f"Conversation transcript:\n{transcript}"
        )

        response = client.chat.completions.create(
            model=_SUMMARY_MODEL,
            max_tokens=400,
            temperature=0.1,
            messages=[
                {"role": "system", "content": _SUMMARY_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )

        raw = response.choices[0].message.content or ""

        # Strip markdown fences
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()

        summary_data = json.loads(text)

        # Validate minimum required fields
        required = {"mood_trend", "key_concerns", "session_risk_level"}
        if not required.issubset(summary_data.keys()):
            logger.warning("Memory summary missing required fields: %s", summary_data)
            return False

        # Save to user
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return False

        user.memory_summary = json.dumps(summary_data, ensure_ascii=False)
        user.memory_summary_updated_at = datetime.now(timezone.utc)
        user.memory_summary_message_count = len(user_messages)
        db.commit()

        logger.info(
            "Memory summary saved for user %d — mood: %s, risk: %s",
            user_id,
            summary_data.get("mood_trend"),
            summary_data.get("session_risk_level"),
        )
        return True

    except Exception as e:
        logger.warning("Memory summarization failed for user %d: %s", user_id, e)
        return False

# Memory injection — builds the system prompt context block

def get_memory_context(user_id: int, db, language: str = "en") -> str:
    """
    Return a short string to prepend to the system prompt, summarising
    what the bot knows about this user from previous sessions.

    Returns empty string if no memory exists or memory is disabled.
    """
    if not _MEMORY_ENABLED:
        return ""

    try:
        from app.db.models.user import User

        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.memory_summary:
            return ""

        data: dict[str, Any] = json.loads(user.memory_summary)

        updated_at = user.memory_summary_updated_at
        days_ago = ""
        if updated_at:
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=timezone.utc)
            delta = datetime.now(timezone.utc) - updated_at
            if delta.days == 0:
                days_ago = "earlier today"
            elif delta.days == 1:
                days_ago = "yesterday"
            else:
                days_ago = f"{delta.days} days ago"

        mood = data.get("mood_trend", "unknown")
        concerns = data.get("key_concerns", [])
        symptoms = data.get("physical_symptoms", [])
        priorities = data.get("follow_up_priorities", [])
        trajectory = data.get("risk_trajectory", "unknown")
        notable = data.get("notable_changes")

        # Build context block based on language
        if language == "fi":
            parts = [f"[Muistio edellisestä keskustelusta ({days_ago})]"]
            if mood != "unknown":
                mood_fi = {
                    "improving": "paraneva", "stable": "vakaa",
                    "declining": "heikkenevä", "unknown": "tuntematon"
                }.get(mood, mood)
                parts.append(f"Mielialan suunta: {mood_fi}")
            if concerns:
                parts.append(f"Aiemmat huolenaiheet: {', '.join(concerns[:3])}")
            if symptoms:
                parts.append(f"Fyysiset oireet: {', '.join(symptoms[:3])}")
            if trajectory == "worsening":
                parts.append("HUOM: Hyvinvointi on ollut heikkenevä — ole erityisen tarkkaavainen.")
            if priorities:
                parts.append(f"Kysy luonnollisesti: {', '.join(priorities[:2])}")
            if notable:
                parts.append(f"Muutos edelliseen: {notable}")

        elif language == "sv":
            parts = [f"[Minnesanteckning från föregående samtal ({days_ago})]"]
            if mood != "unknown":
                mood_sv = {
                    "improving": "förbättrande", "stable": "stabil",
                    "declining": "försämrande", "unknown": "okänd"
                }.get(mood, mood)
                parts.append(f"Humörtendens: {mood_sv}")
            if concerns:
                parts.append(f"Tidigare bekymmer: {', '.join(concerns[:3])}")
            if symptoms:
                parts.append(f"Fysiska symtom: {', '.join(symptoms[:3])}")
            if trajectory == "worsening":
                parts.append("OBS: Välbefinnandet har försämrats — var extra uppmärksam.")
            if priorities:
                parts.append(f"Fråga naturligt om: {', '.join(priorities[:2])}")
            if notable:
                parts.append(f"Förändring sedan sist: {notable}")

        else:  # English
            parts = [f"[Memory from previous session ({days_ago})]"]
            if mood != "unknown":
                parts.append(f"Mood trend: {mood}")
            if concerns:
                parts.append(f"Previous concerns: {', '.join(concerns[:3])}")
            if symptoms:
                parts.append(f"Physical symptoms: {', '.join(symptoms[:3])}")
            if trajectory == "worsening":
                parts.append("NOTE: Wellbeing has been worsening — be especially attentive.")
            if priorities:
                parts.append(f"Naturally follow up on: {', '.join(priorities[:2])}")
            if notable:
                parts.append(f"Change since last session: {notable}")

        return "\n".join(parts)

    except Exception as e:
        logger.warning("Failed to load memory context for user %d: %s", user_id, e)
        return ""

# Trigger helper — decides when to summarise


def should_summarize(total_messages_today: int, is_closing: bool = False) -> bool:
    """
    Returns True if the current session should be summarised now.
    Summarise when: hitting the daily limit OR the bot is sending a closing message.
    """
    return is_closing or total_messages_today >= 20