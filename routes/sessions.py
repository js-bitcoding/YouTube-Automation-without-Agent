from typing import List,Optional
from sqlalchemy.orm import Session
from sqlalchemy.orm import joinedload
from utils.logging_utils import logger
from database.db_connection import get_db
from functionality.current_user import get_current_user
from fastapi import APIRouter, Depends, HTTPException, Query
from database.models import User, Group, ChatConversation, ChatSession, chat_session_group,Instruction

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
        sessions = db.query(ChatSession).join(chat_session_group).join(Group).options(
            joinedload(ChatSession.conversations)  # Correct relationship name
        ).filter(
            Group.user_id == current_user.id,
            ChatSession.is_deleted == False
        ).all()

        if not sessions:
            logger.warning(f"No chat sessions found for User ID {current_user.id}.")
            raise HTTPException(status_code=404, detail="⚠️ No chat sessions found for this user.")
        
        logger.info(f"{len(sessions)} chat sessions retrieved for User ID {current_user.id}.")
        return [
    {
        "id": session.id,
        "name": session.name,
        "updated_at": session.updated_at,
        "associated_groups": [
    {
        "id": group.id,
        "name": group.name,
        **({"created_at": group.created_at} if hasattr(group, "created_at") else {}),
        "updated_at": group.updated_at
    }
    for group in session.groups
],

        "conversations": [
            {
                "id": convo.id,
                "name": convo.name,
                "created_at": convo.created_at
            }
            for convo in session.conversations if not convo.is_deleted
        ]
    }
    for session in sessions
]
    except HTTPException:
        raise 

    except Exception as e:
        logger.exception(f"Failed to retrieve chat sessions for User ID {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Unable to fetch sessions.")


@sessions_router.get("/{session_id}/")
def get_session_by_id(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves a specific chat session by its ID for the authenticated user.
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

        return {
            "session_id": session.id,
            "name": session.name,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "conversations": [
                {
                    "conversation_id": conv.id,
                    "conversation_name": conv.name
                } for conv in session.conversations
            ]
        }
    except HTTPException:
        raise 
    except Exception as e:
        logger.exception(f"Failed to retrieve chat session {session_id} for User ID {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Unable to fetch session.")



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

        valid_group_ids = {group.id for group in groups}
        invalid_group_ids = set(unique_group_ids) - valid_group_ids

        if invalid_group_ids:
            logger.warning(f"Invalid group IDs for User ID {current_user.id}: {invalid_group_ids}")
            raise HTTPException(
        status_code=400,
        detail=f"Invalid group IDs: {list(invalid_group_ids)}"
        )

        if not groups:
            logger.warning(f"No valid groups found for User ID {current_user.id}")
            raise HTTPException(status_code=400, detail="No valid groups found for the user")
        active_instruction = db.query(Instruction).filter(
        Instruction.is_activate == True,
        Instruction.is_deleted == False
        ).first()
        chat_session = ChatSession(
            name=name,
        )
        db.add(chat_session)
        db.commit()
        db.refresh(chat_session)

        chat_session.groups.extend(groups)
        db.commit()

        chat_conversation = ChatConversation(
            name="My Conversation",
            chat_session_id=chat_session.id,
            instruction_id=active_instruction.id if active_instruction else None

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
        raise e

    except Exception as e:
        logger.exception(f"Failed to create chat session for User ID {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to create session.")

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
        # Validate and fetch the session
        session = db.query(ChatSession).join(chat_session_group).join(Group).filter(
            ChatSession.id == session_id,
            Group.user_id == current_user.id
        ).first()

        if not session:
            logger.error(f"Unauthorized access or session not found: {session_id} for User ID {current_user.id}")
            raise HTTPException(status_code=404, detail="Session not found or access denied.")

        # Delete related conversations
        conversations = db.query(ChatConversation).filter(ChatConversation.chat_session_id == session_id).all()
        for convo in conversations:
            db.delete(convo)

        # Mark the session as deleted (or delete it hard if preferred)
        session.is_deleted = True
        db.commit()

        logger.info(f"Session ID {session_id} and its {len(conversations)} conversation(s) deleted for User ID {current_user.id}")
        return {"message": "Session and associated conversations successfully deleted."}

    except HTTPException:
        raise  # Re-raise known exceptions
    except Exception as e:
        logger.exception(f"Failed to delete session {session_id} and conversations for User ID {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error: Failed to delete session and conversations.")



@sessions_router.put("/update/{session_id}/")
def update_session_api(
    session_id: int,
    name: Optional[str] = Query(default=None),
    group_ids: Optional[List[int]] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Updates the name and/or group associations of a chat session.

    Args:
        session_id (int): ID of the chat session to update.
        name (Optional[str]): New name for the session (if provided).
        group_ids (Optional[List[int]]): New group IDs to associate (if provided).
        db (Session): SQLAlchemy DB session.
        current_user (User): The authenticated user.

    Returns:
        dict: Updated session info.

    Raises:
        HTTPException: On unauthorized access or invalid input.
    """
    try:
        session = db.query(ChatSession).join(chat_session_group).join(Group).filter(
            ChatSession.id == session_id,
            Group.user_id == current_user.id,
            ChatSession.is_deleted == False
        ).first()

        if not session:
            logger.warning(f"Session ID {session_id} not found for User ID {current_user.id}.")
            raise HTTPException(status_code=404, detail="Chat session not found.")

        updated = False

        # Update name if provided
        if name is not None:
            name = name.strip()
            if not name:
                raise HTTPException(status_code=422, detail="Chat session name cannot be empty.")
            session.name = name
            updated = True

        # Update groups if provided
        if group_ids is not None:
            if not all(isinstance(gid, int) for gid in group_ids):
                raise HTTPException(status_code=422, detail="All group IDs must be integers.")
            
            unique_group_ids = list(set(group_ids))
            groups = db.query(Group).filter(Group.id.in_(unique_group_ids), Group.user_id == current_user.id).all()
            valid_group_ids = {g.id for g in groups}
            invalid_group_ids = set(unique_group_ids) - valid_group_ids

            if invalid_group_ids:
                raise HTTPException(status_code=400, detail=f"Invalid group IDs: {list(invalid_group_ids)}")

            session.groups.clear()
            session.groups.extend(groups)
            updated = True

        if updated:
            db.commit()
            db.refresh(session)
            logger.info(f"Session ID {session_id} updated by User ID {current_user.id}.")
        else:
            logger.info(f"No update fields provided for session ID {session_id} by User ID {current_user.id}.")

        return {
            "id": session.id,
            "name": session.name,
            "updated_at": session.updated_at,
            "associated_group_ids": [g.id for g in session.groups],
            "conversations": [
                {
                    "id": convo.id,
                    "name": convo.name,
                    "created_at": convo.created_at
                }
                for convo in session.conversations if not convo.is_deleted
            ]
        }

    except HTTPException as e:
        logger.exception(f"HTTP error during update of session {session_id}: {e}")
        raise e

    except Exception as e:
        logger.exception(f"Failed to delete session {session_id} for User ID {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete session.")