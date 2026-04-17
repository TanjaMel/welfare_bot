from pydantic import BaseModel, ConfigDict
from __future__ import annotations

class ConversationMessageCreate(BaseModel):
    user_id: int
    role: str
    content: str
    message_type: str = "free_chat"


class ConversationMessageRead(BaseModel):
    id: int
    user_id: int
    role: str
    content: str
    message_type: str
    created_at: str

    model_config = ConfigDict(from_attributes=True)