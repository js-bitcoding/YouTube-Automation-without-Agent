from sqlalchemy.orm import Session,joinedload
from fastapi import APIRouter, Depends ,HTTPException
from database.models import User, Group, ChatConversation, ChatSession, chat_session_group
from service.chat_ai_agent_service import generate_response_for_conversation
from database.db_connection import get_db
from functionality.current_user import get_current_user
from utils.logging_utils import logger

chat_router = APIRouter(prefix="/conversations")

@chat_router.get("/")
def get_all_conversations(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Retrieves all non-deleted conversations for the current user.

    Args:
        db (Session): SQLAlchemy DB session.
        current_user (User): The currently authenticated user.

    Returns:
        list: List of ChatConversation objects.
    """
    try:
        get_all_cov = db.query(ChatConversation).join(ChatSession).join(chat_session_group).join(Group).filter(
            Group.user_id == current_user.id,
            ChatConversation.is_deleted == False
        ).all()

        if not get_all_cov:
            logger.warning(f"No conversations found for User ID {current_user.id}")
            raise HTTPException(status_code=400, detail="No Conversation Found")

        logger.info(f"{len(get_all_cov)} conversations retrieved for User ID {current_user.id}")
        return get_all_cov
    except Exception as e:
        logger.exception(f"Error retrieving conversations for User ID {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@chat_router.post("/create/")
def create_conversation(
    session_id: int,
    name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Creates a new conversation under a session owned by the current user.

    Args:
        session_id (int): ID of the session to attach the conversation to.
        name (str): Name of the new conversation.
        db (Session): SQLAlchemy DB session.
        current_user (User): Authenticated user.

    Returns:
        ChatConversation: The newly created conversation object.
    """
    try:
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
    except Exception as e:
        logger.exception(f"Error creating conversation for Session ID {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@chat_router.put("/update/{conversation_id}/")
def update_conversation_name(
    conversation_id: int,
    name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Updates the name of a conversation owned by the current user.

    Args:
        conversation_id (int): ID of the conversation to update.
        name (str): New name for the conversation.
        db (Session): SQLAlchemy DB session.
        current_user (User): Authenticated user.

    Returns:
        dict: Confirmation message of the update.
    """
    try:
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
    except Exception as e:
        logger.exception(f"Error updating conversation ID {conversation_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@chat_router.get("/get/{conversation_id}/")
def get_conversation_by_id(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves details of a specific conversation, including its chats, for the current user.

    Args:
        conversation_id (int): ID of the conversation to retrieve.
        db (Session): SQLAlchemy DB session.
        current_user (User): Authenticated user.

    Returns:
        dict: Conversation details, including the name, timestamps, and associated chats.
    """
    try:
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
    except Exception as e:
        logger.exception(f"Error retrieving conversation ID {conversation_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@chat_router.delete("/delete/{conversation_id}/")
def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Soft-deletes a conversation by setting `is_deleted` to True for the current user.

    Args:
        conversation_id (int): ID of the conversation to delete.
        db (Session): SQLAlchemy DB session.
        current_user (User): Authenticated user.

    Returns:
        dict: Confirmation message of deletion.
    """
    try:
        convo = db.query(ChatConversation).join(ChatSession).join(chat_session_group).join(Group).filter(
            ChatConversation.id == conversation_id,
            Group.user_id == current_user.id
        ).first()

        if not convo:
            logger.error(f"Unauthorized access or conversation not found: {conversation_id} for User ID {current_user.id}")
            raise HTTPException(status_code=404, detail="Conversation not found")

        convo.is_deleted = True
        db.commit()
        logger.info(f"Conversation ID {conversation_id} marked as deleted by User ID {current_user.id}")
        return {"message": "Conversation deleted"}
    except Exception as e:
        logger.exception(f"Error deleting conversation ID {conversation_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@chat_router.post("/generate_group_response")
def generate_group_response(
    conversation_id: int,
    user_prompt: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generates a response based on the user's prompt and conversation context.

    Args:
        conversation_id (int): ID of the conversation for context.
        user_prompt (str): The user's query or prompt for the assistant.
        db (Session): SQLAlchemy DB session.
        current_user (User): Authenticated user.

    Returns:
        dict: The generated response from the assistant.
    """
    try:
        if not user_prompt or len(user_prompt.strip()) == 0:
            raise HTTPException(status_code=400, detail="User prompt cannot be empty")

        logger.info(f"Generating response for Conversation ID {conversation_id} with prompt: {user_prompt[:50]}... by User ID {current_user.id}")
        return generate_response_for_conversation(conversation_id, user_prompt, db, current_user)
    except Exception as e:
        logger.exception(f"Error generating response for Conversation ID {conversation_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")