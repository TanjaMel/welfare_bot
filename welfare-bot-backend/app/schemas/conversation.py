from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ConversationMessageRead(BaseModel):
    id: int
    user_id: int
    role: str
    content: str
    message_type: str = "free_chat"
    created_at: datetime | None = None
    risk_level: str | None = None
    risk_score: int | None = None
    risk_category: str | None = None

    class Config:
        from_attributes = True


class SendMessageRequest(BaseModel):
    user_id: int
    message: str                    # ← "message" not "content"
    language: str | None = None     # en / fi / sv, optional


class SendMessageResponse(BaseModel):
    reply: str                      # ← plain reply string
    risk_analysis: dict | None = None
    notifications: list[dict] = []
    mode: str = "non_stream"