from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException
from database.db_connection import get_db
from database.schemas import ChatCreate
from functionality.current_user import get_current_user
from database.models import User, Group, ChatConversation, ChatSession, chat_session_group
from utils.logging_utils import logger

sessions_router = APIRouter(prefix="/Session")

@sessions_router.get("/")
def get_all_sessions(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    sessions = db.query(ChatSession).join(chat_session_group).join(Group).filter(
        Group.user_id == current_user.id,
        ChatSession.is_deleted == False
    ).all()

    if not sessions:
        logger.warning(f"No chat sessions found for User ID {current_user.id}.")
        raise HTTPException(status_code=404, detail="⚠️ No chat sessions found for this user.")
    
    logger.info(f"{len(sessions)} chat sessions retrieved for User ID {current_user.id}.")
    return sessions

@sessions_router.get("/{session_id}")
def get_session_by_id(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    session = db.query(ChatSession).join(chat_session_group).join(Group).filter(
        ChatSession.id == session_id,
        Group.user_id == current_user.id,
        ChatSession.is_deleted == False
    ).first()

    if not session:
        logger.warning(f"Chat session with ID {session_id} not found for User ID {current_user.id}.")
        raise HTTPException(status_code=404, detail="⚠️ Chat session not found for this user.")
    
    logger.info(f"Chat session with ID {session_id} retrieved for User ID {current_user.id}.")
    return session

@sessions_router.post("/create")
def create_chat_api(
    payload: ChatCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    unique_group_ids = list(set(payload.group_ids))
    logger.info(f"Creating chat session with groups: {unique_group_ids} for User ID {current_user.id}")

    groups = db.query(Group).filter(Group.id.in_(unique_group_ids), Group.user_id == current_user.id).all()

    if not groups:
        logger.warning(f"No valid groups found for User ID {current_user.id}")
        raise HTTPException(status_code=400, detail="No valid groups found for the user")

    chat_session = ChatSession(
        name=payload.name,
    )
    db.add(chat_session)
    db.commit()
    db.refresh(chat_session)

    chat_session.groups.extend(groups)
    db.commit()

    chat_conversation = ChatConversation(
        name=payload.name,
        chat_session_id=chat_session.id,
    )
    db.add(chat_conversation)
    db.commit()
    db.refresh(chat_conversation)

    logger.info(f"Chat session created with ID {chat_session.id}, Conversation ID {chat_conversation.id}")
    return {
        "chat_session_id": chat_session.id,
        "conversation_id": chat_conversation.id,
        "associated_group_ids": [g.id for g in groups]
    }

@sessions_router.delete("/delete")
def delete_session(session_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    session = db.query(ChatSession).join(chat_session_group).join(Group).filter(
        ChatSession.id == session_id,
        Group.user_id == current_user.id
    ).first()
    
    if not session:
        logger.error(f"Unauthorized access or session not found: {session_id} for User ID {current_user.id}")
        raise HTTPException(status_code=404, detail="Session not found or already deleted")
    
    session.is_deleted = True
    db.commit()
    logger.info(f"Session ID {session_id} marked as deleted for User ID {current_user.id}")
    return {"message": "Session deleted"}
