import datetime
from sqlalchemy.orm import Session,joinedload
from database.db_connection import get_db
from langchain_community.llms import Ollama
from database.schemas import ChatCreate, ChatUpdate
from fastapi import APIRouter, Depends ,HTTPException
from functionality.current_user import get_current_user
from service.chat_service import create_chat, update_chat, delete_chat, list_user_conversations
from service.chat_ai_agent_service import generate_response_for_conversation
from database.models import User,Group,ChatConversation,ChatSession,ChatHistory,chat_session_group

chat_router = APIRouter(prefix="/chats")

@chat_router.get("/sessions")
def get_all_sessions(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    sessions = db.query(ChatSession).join(chat_session_group).join(Group).filter(
        Group.user_id == current_user.id,
        ChatSession.is_deleted == False
    ).all()
    if not sessions:
        raise HTTPException(status_code=404, detail="⚠️ No chat sessions found for this user.")
    return sessions


@chat_router.post("/sessions")
def create_chat_api(
    payload: ChatCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Deduplicate group_ids
    unique_group_ids = list(set(payload.group_ids))

    # Fetch groups that belong to the current user
    groups = db.query(Group).filter(Group.id.in_(unique_group_ids), Group.user_id == current_user.id).all()

    if not groups:
        raise HTTPException(status_code=400, detail="No valid groups found for the user")

    # Create ChatSession (shared across groups)
    chat_session = ChatSession(
        name=payload.name,
    )
    db.add(chat_session)
    db.commit()
    db.refresh(chat_session)

    # Associate ChatSession with groups
    chat_session.groups.extend(groups)
    db.commit()

    # Create ChatConversation for the session
    chat_conversation = ChatConversation(
        name=payload.name,
        chat_session_id=chat_session.id,
    )
    db.add(chat_conversation)
    db.commit()
    db.refresh(chat_conversation)

    return {
        "chat_session_id": chat_session.id,
        "conversation_id": chat_conversation.id,
        "associated_group_ids": [g.id for g in groups]
    }

@chat_router.delete("/sessions/{session_id}")
def delete_session(session_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    session = db.query(ChatSession).join(chat_session_group).join(Group).filter(
        ChatSession.id == session_id,
        Group.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or unauthorized access")
    
    session.is_deleted = True
    db.commit()
    return {"message": "Session deleted"}



@chat_router.get("/conversations")
def get_all_conversations(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    get_all_cov = db.query(ChatConversation).join(ChatSession).join(chat_session_group).join(Group).filter(
        Group.user_id == current_user.id,
        ChatConversation.is_deleted == False
    ).all()

    if not get_all_cov:
        raise HTTPException(status_code=400, detail="No Conversation Found")
    
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
        raise HTTPException(status_code=404, detail="Session not found or unauthorized access")

    conversation = ChatConversation(name=name, chat_session_id=session_id)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
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
        raise HTTPException(status_code=404, detail="Conversation not found or unauthorized access")
    
    convo.name = name
    db.commit()
    return {"message": "Conversation name updated"}



@chat_router.get("/conversations/{conversation_id}")
def get_conversation_by_id(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Query with eager loading of chat histories
    convo = db.query(ChatConversation).options(
        joinedload(ChatConversation.chats)  # Load chat histories
    ).join(ChatSession).join(chat_session_group).join(Group).filter(
        ChatConversation.id == conversation_id,
        Group.user_id == current_user.id,
        ChatConversation.is_deleted == False
    ).first()

    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found or unauthorized access")

    # Format the result to include conversation + chat histories
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
        raise HTTPException(status_code=404, detail="Conversation not found or unauthorized access")
    
    convo.is_deleted = True
    db.commit()
    return {"message": "Conversation deleted"}

# @chat_router.get("/chats")
# def get_user_chats(
#     db: Session = Depends(get_db),
#     current_user: User = Depends(get_current_user)
# ):
#     chats = db.query(
#         ChatHistory.id.label("chat_id"),
#         ChatHistory.chat_conversation_id
#     ).filter(
#         ChatHistory.user_id == current_user.id,
#         ChatHistory.is_deleted == False
#     ).order_by(ChatHistory.created_at.asc()).all()

#     if not chats:
#         raise HTTPException(status_code=404, detail="Chat not found or unauthorized access")
    
#     return [{"chat_id": chat.chat_id, "chat_conversation_id": chat.chat_conversation_id} for chat in chats]

# @chat_router.get("/chats/{chat_id}")
# def get_chat_by_id(
#     chat_id: int,
#     db: Session = Depends(get_db),
#     current_user: User = Depends(get_current_user)
# ):
#     chat = db.query(ChatHistory).filter(
#         ChatHistory.id == chat_id,
#         ChatHistory.user_id == current_user.id,  # Auth check here
#         ChatHistory.is_deleted == False
#     ).first()
    
#     if not chat:
#         raise HTTPException(status_code=404, detail="Chat not found or unauthorized access")

#     return {
#         "chat_id": chat.id,
#         "query": chat.query,
#         "response": chat.response,
#         "context": chat.context,
#         "created_at": chat.created_at,
#         "conversation_id": chat.chat_conversation_id,
#         "instruction": {
#             "id": chat.instruction.id if chat.instruction else None,
#             "name": chat.instruction.name if chat.instruction else None,
#             "content": chat.instruction.content if chat.instruction else None
#         } if chat.instruction else None
#     }

# --- Chat Response Generation ---

# @chat_router.post("/generate_group_response")
# def generate_group_response(
#     conversation_id: int,
#     user_prompt: str,
#     db: Session = Depends(get_db),
#     current_user: User = Depends(get_current_user)
# ):
#     return generate_response_for_conversation(conversation_id, user_prompt, db, current_user)

#RAG

@chat_router.post("/generate_group_response")
def generate_group_response(
    conversation_id: int,
    user_prompt: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):        
    return generate_response_for_conversation(conversation_id, user_prompt, db, current_user)