from sqlalchemy.orm import Session
from database.models import Chat

def create_chat(name: str, db: Session, user_id: int, group_id: int = None):
    chat = Chat(
        name=name,
        user_id=user_id,
        group_id=group_id
    )
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return chat

def update_chat(db: Session, chat_id: int, name: str):
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if chat:
        chat.name = name or chat.name
        db.commit()
        db.refresh(chat)
    return chat

def delete_chat(db: Session, chat_id: int):
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if chat:
        db.delete(chat)
        db.commit()
    return chat

def list_chats(db: Session, user_id: int):
    return db.query(Chat).filter(Chat.user_id == user_id).all()
