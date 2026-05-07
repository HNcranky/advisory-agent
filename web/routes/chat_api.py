from pydantic import BaseModel
from fastapi import APIRouter

from services.chat.conversation_service import ConversationService

router = APIRouter(prefix="/api/sessions", tags=["chat"])

class ChatMessageCreate(BaseModel):
    content: str
    
def get_conversation_service():
    return ConversationService()

@router.post("/{session_token}/messages")
def post_message(session_token: str, payload: ChatMessageCreate):
    service = get_conversation_service()
    result = service.handle_user_message(session_token, payload.content)
    return result.model_dump()