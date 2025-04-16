from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database.schemas import ChatCreate, ChatUpdate
from service.chat_service import create_chat, update_chat, delete_chat, list_chats
from database.db_connection import get_db

chat_router = APIRouter(prefix="/chats")

@chat_router.post("/create")
def create_chat_api(payload: ChatCreate, db: Session = Depends(get_db)):
    return create_chat(db, payload.query, payload.group_name)

@chat_router.put("/{chat_name}")
def update_chat_api(chat_name: str, payload: ChatUpdate, db: Session = Depends(get_db)):
    return update_chat(db, chat_name, payload.name)

@chat_router.delete("/{chat_name}")
def delete_chat_api(chat_name: str, db: Session = Depends(get_db)):
    return delete_chat(db, chat_name)

@chat_router.get("/list/{user_id}")
def list_chats_api(user_id: int, db: Session = Depends(get_db)):
    return list_chats(db, user_id)
