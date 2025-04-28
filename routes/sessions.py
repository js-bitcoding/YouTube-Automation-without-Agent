from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List
from database.db_connection import get_db
from functionality.current_user import get_current_user
from database.models import User, Group, ChatConversation, ChatSession, chat_session_group
from utils.logging_utils import logger

sessions_router = APIRouter(prefix="/Session")

@sessions_router.get("/")
def get_all_sessions(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Retrieves all chat sessions for the authenticated user.

    Args:
        db (Session): SQLAlchemy DB session.
        current_user (User): The authenticated user making the request.

    Returns:
        List[ChatSession]: A list of chat sessions associated with the user.

    Raises:
        HTTPException:
            - If no chat sessions are found for the user.
    """
    try:
        sessions = db.query(ChatSession).join(chat_session_group).join(Group).filter(
            Group.user_id == current_user.id,
            ChatSession.is_deleted == False
        ).all()

        if not sessions:
            logger.warning(f"No chat sessions found for User ID {current_user.id}.")
            raise HTTPException(status_code=404, detail="⚠️ No chat sessions found for this user.")
        
        logger.info(f"{len(sessions)} chat sessions retrieved for User ID {current_user.id}.")
        return sessions

    except Exception as e:
        logger.exception(f"Failed to retrieve chat sessions for User ID {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error: Unable to fetch sessions.")


@sessions_router.get("/{session_id}/")
def get_session_by_id(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves a specific chat session by its ID for the authenticated user.

    Args:
        session_id (int): The ID of the chat session to retrieve.
        db (Session): SQLAlchemy DB session.
        current_user (User): The authenticated user making the request.

    Returns:
        ChatSession: The chat session associated with the specified ID.

    Raises:
        HTTPException:
            - If the chat session is not found or does not belong to the user.
    """
    try:
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

    except Exception as e:
        logger.exception(f"Failed to retrieve chat session {session_id} for User ID {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error: Unable to fetch session.")



@sessions_router.post("/create/")
def create_session_api(
    name: str = Query(...),
    group_ids: List[int] = Query(default=[]),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Creates a new chat session and its associated conversation for the authenticated user, 
    linking it to the specified groups.

    Args:
        payload (ChatCreate): The data for creating a new chat session, including group IDs.
        db (Session): SQLAlchemy DB session.
        current_user (User): The authenticated user creating the chat session.

    Returns:
        dict: A dictionary containing the chat session ID, conversation ID, and associated group IDs.

    Raises:
        HTTPException:
            - If no valid groups are found for the authenticated user.
    """
    try:
        if not name.strip():
            logger.error(f"User ID {current_user.id} tried to create a session with an empty name.")
            raise HTTPException(status_code=422, detail="Chat session name cannot be empty")
        
        if not group_ids:
            logger.error(f"User ID {current_user.id} did not provide any group IDs.")
            raise HTTPException(status_code=422, detail="At least one group ID must be provided")

        if not all(isinstance(gid, int) for gid in group_ids):
            logger.error(f"User ID {current_user.id} provided invalid group IDs: {group_ids}")
            raise HTTPException(status_code=422, detail="All group IDs must be integers")
        
        unique_group_ids = list(set(group_ids))
        logger.info(f"Creating chat session with groups: {unique_group_ids} for User ID {current_user.id}")

        groups = db.query(Group).filter(Group.id.in_(unique_group_ids), Group.user_id == current_user.id).all()

        if not groups:
            logger.warning(f"No valid groups found for User ID {current_user.id}")
            raise HTTPException(status_code=400, detail="No valid groups found for the user")

        chat_session = ChatSession(
            name=name,
        )
        db.add(chat_session)
        db.commit()
        db.refresh(chat_session)

        chat_session.groups.extend(groups)
        db.commit()

        chat_conversation = ChatConversation(
            name=name,
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

    except HTTPException as e:
        logger.exception(f"Failed to Create session : {e}")

    except Exception as e:
        logger.exception(f"Failed to create chat session for User ID {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error: Failed to create session.")


@sessions_router.delete("/delete/")
def delete_session(session_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Marks a chat session as deleted for the authenticated user.

    Args:
        session_id (int): The ID of the chat session to be deleted.
        db (Session): SQLAlchemy DB session.
        current_user (User): The authenticated user requesting the deletion.

    Returns:
        dict: A dictionary with a success message confirming the session deletion.

    Raises:
        HTTPException:
            - If the session is not found or the user is unauthorized to delete the session.
    """
    try:
        session = db.query(ChatSession).join(chat_session_group).join(Group).filter(
            ChatSession.id == session_id,
            Group.user_id == current_user.id
        ).first()

        if not session:
            logger.error(f"Unauthorized access or session not found: {session_id} for User ID {current_user.id}")
            raise HTTPException(status_code=404, detail="Session not found")
        
        session.is_deleted = True
        db.commit()
        logger.info(f"Session ID {session_id} marked as deleted for User ID {current_user.id}")
        return {"message": "Session deleted"}

    except Exception as e:
        logger.exception(f"Failed to delete session {session_id} for User ID {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error: Failed to delete session.")