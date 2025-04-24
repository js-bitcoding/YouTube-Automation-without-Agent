import datetime
from typing import Optional
from sqlalchemy.orm import Session
from database.models import ChatConversation, ChatSession,Group

def create_chat(
    name: str,
    db: Session,
    user_id: int,
    group_ids: list[int]
):
    """
    Create a new chat session and its associated conversation, linking it to the specified groups.

    Args:
        name (str): The name of the chat session.
        db (Session): The SQLAlchemy database session.
        user_id (int): The ID of the user creating the chat session.
        group_ids (list[int]): A list of group IDs to be associated with the new chat session.

    Returns:
        ChatConversation: The newly created chat conversation object.

    Raises:
        HTTPException: If there are any issues with group retrieval or database operations.
    """
    session = ChatSession(name=name)
    session.created_at = datetime.datetime.utcnow()
    session.updated_at = datetime.datetime.utcnow()
    db.add(session)
    db.commit()
    db.refresh(session)

    groups = db.query(Group).filter(Group.id.in_(group_ids)).all()
    session.groups.extend(groups)
    db.commit()

    conversation = ChatConversation(
        name=name,
        chat_session_id=session.id,
        created_at=datetime.datetime.utcnow(),
        updated_at=datetime.datetime.utcnow()
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    return conversation

def update_chat(db: Session, conversation_id: int, name: Optional[str] = None):
    """
    Update the name of a chat conversation and refresh its updated timestamp.

    Args:
        db (Session): The SQLAlchemy database session.
        conversation_id (int): The ID of the conversation to update.
        name (Optional[str], optional): The new name for the chat conversation. Defaults to None.

    Returns:
        ChatConversation: The updated chat conversation object. If no conversation is found, returns None.

    Raises:
        HTTPException: If no conversation is found with the given conversation_id.
    """
    conversation = db.query(ChatConversation).filter(ChatConversation.id == conversation_id).first()
    if conversation:
        if name:
            conversation.name = name
        conversation.updated_at = datetime.datetime.utcnow()
        db.commit()
        db.refresh(conversation)
    return conversation

def delete_chat(db: Session, conversation_id: int):
    """
    Mark a chat conversation as deleted by setting its 'is_deleted' flag to True and updating the timestamp.

    Args:
        db (Session): The SQLAlchemy database session.
        conversation_id (int): The ID of the conversation to delete.

    Returns:
        ChatConversation: The updated chat conversation object with the 'is_deleted' flag set to True.
                           If no conversation is found with the given ID, returns None.
    
    Raises:
        HTTPException: If the conversation with the provided conversation_id does not exist.
    """
    conversation = db.query(ChatConversation).filter(ChatConversation.id == conversation_id).first()
    if conversation:
        conversation.is_deleted = True
        conversation.updated_at = datetime.datetime.utcnow()
        db.commit()
    return conversation

def list_user_conversations(db: Session, user_id: int):
    """
    Retrieve all non-deleted chat conversations for a given user, based on their group memberships.

    Args:
        db (Session): The SQLAlchemy database session.
        user_id (int): The ID of the user whose conversations are to be fetched.

    Returns:
        List[ChatConversation]: A list of ChatConversation objects associated with the user.
                                The list only includes conversations that are not marked as deleted.
    
    Raises:
        HTTPException: If no conversations are found for the user, an empty list will be returned.
    """
    return (
        db.query(ChatConversation)
        .join(ChatSession)
        .join(ChatSession.groups)
        .filter(Group.user_id == user_id, ChatConversation.is_deleted == False)
        .all()
    )
