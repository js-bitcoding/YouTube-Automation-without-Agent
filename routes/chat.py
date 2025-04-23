from sqlalchemy.orm import Session,joinedload
from fastapi import APIRouter, Depends ,HTTPException
from database.models import User, Group, ChatConversation, ChatSession, chat_session_group
from service.chat_ai_agent_service import generate_response_for_conversation
from database.db_connection import get_db
from functionality.current_user import get_current_user
from utils.logging_utils import logger

chat_router = APIRouter(prefix="/chats")

@chat_router.get("/conversations")
def get_all_conversations(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    get_all_cov = db.query(ChatConversation).join(ChatSession).join(chat_session_group).join(Group).filter(
        Group.user_id == current_user.id,
        ChatConversation.is_deleted == False
    ).all()

    if not get_all_cov:
        logger.warning(f"No conversations found for User ID {current_user.id}")
        raise HTTPException(status_code=400, detail="No Conversation Found")
    
    logger.info(f"{len(get_all_cov)} conversations retrieved for User ID {current_user.id}")
    return get_all_cov

@chat_router.post("/conversations")
def create_conversation(
    session_id: int,
    name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    session = db.query(ChatSession).join(chat_session_group).join(Group).filter(
        ChatSession.id == session_id,
        Group.user_id == current_user.id
    ).first()
    
    if not session:
        logger.error(f"Unauthorized access or session not found: {session_id} for User ID {current_user.id}")
        raise HTTPException(status_code=404, detail="Session not found or unauthorized access")

    if not name or len(name.strip()) == 0:
        raise HTTPException(status_code=400, detail="Conversation name is required and cannot be empty")
    
    conversation = ChatConversation(name=name, chat_session_id=session_id)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    logger.info(f"Conversation created with ID {conversation.id} for Session ID {session_id}")
    return conversation

@chat_router.put("/conversations/{conversation_id}")
def update_conversation_name(
    conversation_id: int,
    name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    convo = db.query(ChatConversation).join(ChatSession).join(chat_session_group).join(Group).filter(
        ChatConversation.id == conversation_id,
        Group.user_id == current_user.id
    ).first()

    if not convo:
        logger.error(f"Unauthorized access or conversation not found: {conversation_id} for User ID {current_user.id}")
        raise HTTPException(status_code=404, detail="Conversation not found or unauthorized access")
    
    if not name or len(name.strip()) == 0:
        raise HTTPException(status_code=400, detail="Conversation name cannot be empty")
    
    convo.name = name
    db.commit()

    logger.info(f"Conversation ID {conversation_id} renamed to '{name}' by User ID {current_user.id}")
    return {"message": "Conversation name updated"}

@chat_router.get("/conversations/{conversation_id}")
def get_conversation_by_id(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    convo = db.query(ChatConversation).options(
        joinedload(ChatConversation.chats)
    ).join(ChatSession).join(chat_session_group).join(Group).filter(
        ChatConversation.id == conversation_id,
        Group.user_id == current_user.id,
        ChatConversation.is_deleted == False
    ).first()

    if not convo:
        logger.error(f"Conversation not found or unauthorized: {conversation_id} for User ID {current_user.id}")
        raise HTTPException(status_code=404, detail="Conversation not found or unauthorized access")

    logger.info(f"Retrieved conversation ID {conversation_id} with {len(convo.chats)} chat(s) for User ID {current_user.id}")
    return {
        "conversation_id": convo.id,
        "name": convo.name,
        "created_at": convo.created_at,
        "updated_at": convo.updated_at,
        "chats": [
            {
                "chat_id": chat.id,
                "query": chat.query,
                "response": chat.response,
                "created_at": chat.created_at
            }
            for chat in convo.chats if not chat.is_deleted
        ]
    }

@chat_router.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    convo = db.query(ChatConversation).join(ChatSession).join(chat_session_group).join(Group).filter(
        ChatConversation.id == conversation_id,
        Group.user_id == current_user.id
    ).first()
    
    if not convo:
        logger.error(f"Unauthorized access or conversation not found: {conversation_id} for User ID {current_user.id}")
        raise HTTPException(status_code=404, detail="Conversation not found or Already deleted")
    
    convo.is_deleted = True
    db.commit()
    logger.info(f"Conversation ID {conversation_id} marked as deleted by User ID {current_user.id}")
    return {"message": "Conversation deleted"}

@chat_router.post("/generate_group_response")
def generate_group_response(
    conversation_id: int,
    user_prompt: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not user_prompt or len(user_prompt.strip()) == 0:
        raise HTTPException(status_code=400, detail="User prompt cannot be empty")
    
    logger.info(f"Generating response for Conversation ID {conversation_id} with prompt: {user_prompt[:50]}... by User ID {current_user.id}")
    return generate_response_for_conversation(conversation_id, user_prompt, db, current_user)
