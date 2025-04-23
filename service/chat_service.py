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
    conversation = db.query(ChatConversation).filter(ChatConversation.id == conversation_id).first()
    if conversation:
        if name:
            conversation.name = name
        conversation.updated_at = datetime.datetime.utcnow()
        db.commit()
        db.refresh(conversation)
    return conversation

def delete_chat(db: Session, conversation_id: int):
    conversation = db.query(ChatConversation).filter(ChatConversation.id == conversation_id).first()
    if conversation:
        conversation.is_deleted = True
        conversation.updated_at = datetime.datetime.utcnow()
        db.commit()
    return conversation

def list_user_conversations(db: Session, user_id: int):
    return (
        db.query(ChatConversation)
        .join(ChatSession)
        .join(ChatSession.groups)
        .filter(Group.user_id == user_id, ChatConversation.is_deleted == False)
        .all()
    )
