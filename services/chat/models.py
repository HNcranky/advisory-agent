from typing import Any, Dict, Optional, List

from pydantic import BaseModel, Field


class ChatSessionRecord(BaseModel):
    id: int
    session_token: str
    status: str = "collecting_profile"
    profile_state_json: Dict[str, Any] = Field(default_factory=dict)
    latest_run_id: Optional[int] = None
    
class ChatMessageRecord(BaseModel):
    id: int
    session_token: str
    role: str
    kind: str = "chat"
    content: str
    
class ChatSessionSnapshot(BaseModel):
    session: Any
    messages: List[ChatMessageRecord] = Field(default_factory=list)