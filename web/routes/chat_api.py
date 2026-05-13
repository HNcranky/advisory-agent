from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from services.chat.conversation_service import ConversationService
from services.chat.run_dispatcher import RunDispatcher
from services.chat.session_service import AnonymousSessionService

router = APIRouter(prefix="/api/sessions", tags=["chat"])

class ChatMessageCreate(BaseModel):
    content: str
    
def get_session_service():
    return AnonymousSessionService()
    
def get_conversation_service():
    return ConversationService()

def get_run_dispatcher():
    return RunDispatcher()

@router.post("", status_code=status.HTTP_201_CREATED)
def create_session():
    return get_session_service().start_session()

@router.get("/{session_token}")
def get_session(session_token: str):
    snapshot = get_session_service().get_session_snapshot(session_token)
    if not snapshot.session:
        raise HTTPException(status_code=404, detail="Session not found")
    return snapshot

@router.post("/{session_token}/messages")
def post_message(session_token: str, payload: ChatMessageCreate):
    service = get_conversation_service()
    result = service.handle_user_message(session_token, payload.content)
    if result.should_start_run:
        repo = service.repository
        run_id = repo.create_run(session_token, result.profile_state)
        get_run_dispatcher().submit(
            session_token=session_token,
            run_id=run_id,
            latest_user_message=payload.content,
            profile_state=result.profile_state,
        )
    return result.model_dump()