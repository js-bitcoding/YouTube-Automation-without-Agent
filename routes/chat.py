from fastapi import APIRouter, Depends ,HTTPException
from sqlalchemy.orm import Session
from database.models import User,Group,Chat,chat_group_association,ChatSession
from database.schemas import ChatCreate, ChatUpdate
from service.chat_service import create_chat, update_chat, delete_chat, list_chats
from langchain_community.llms import Ollama
from database.db_connection import get_db
from functionality.current_user import get_current_user
from service.chat_ai_agent_service import fetch_group_data,agent
import datetime
chat_router = APIRouter(prefix="/chats")


# @chat_router.post("/create")
# def create_chat_api(
#     payload: ChatCreate,
#     db: Session = Depends(get_db),
#     current_user: User = Depends(get_current_user)
# ):
#     # Deduplicate group_ids to avoid integrity errors
#     unique_group_ids = list(set(payload.group_ids))

#     # Fetch the groups from the database
#     groups = db.query(Group).filter(Group.id.in_(unique_group_ids)).all()

#     # Create a new Chat instance
#     chat = Chat(
#         name=payload.name,
#         user_id=current_user.id
#     )

#     # Add the chat to the session
#     db.add(chat)
#     db.commit()  # Commit to get chat.id populated

#     # Now that the chat has been added and has a chat.id, check for existing associations
#     existing_association_set = set(
#         (existing.chat_id, existing.group_id)
#         for existing in db.query(chat_group_association).filter(chat_group_association.c.chat_id == chat.id).all()
#     )

#     # Add only the groups that aren't already associated
#     for group in groups:
#         # If the association doesn't exist, add it to the chat
#         if (chat.id, group.id) not in existing_association_set:
#             chat.groups.append(group)

#     # Commit the final changes
#     db.commit()
#     db.refresh(chat)

#     return chat


@chat_router.post("/create")
def create_chat_api(
    payload: ChatCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Deduplicate group_ids
    unique_group_ids = list(set(payload.group_ids))

    # Fetch groups
    groups = db.query(Group).filter(Group.id.in_(unique_group_ids)).all()

    # Create Chat
    chat = Chat(
        name=payload.name,
        user_id=current_user.id
    )
    db.add(chat)
    db.commit()
    db.refresh(chat)  # get chat.id

    # Create one ChatSession per group
    chat_sessions = []
    for group in groups:
        session = ChatSession(
            chat_id=chat.id,
            group_id=group.id
        )
        db.add(session)
        chat_sessions.append(session)

    db.commit()

    # Optional: set chat.session_id to the first session created
    if chat_sessions:
        chat.session_id = chat_sessions[0].id
        db.commit()

    # Associate chat with all groups
    for group in groups:
        if group not in chat.groups:
            chat.groups.append(group)

    db.commit()
    db.refresh(chat)

    return chat



llm = Ollama(model="llama3.2:1b")


def is_greeting(user_prompt: str) -> bool:
    """
    Detect if the user's prompt is a greeting or casual opener.
    """
    greetings = ["hello", "hi", "hey", "good morning", "good evening", "how are you", "yo", "sup"]
    return user_prompt.strip().lower() in greetings


# @chat_router.post("/generate_group_response")
# def generate_group_response(
#     chat_id: int,
#     user_prompt: str,
#     db: Session = Depends(get_db),
#     current_user: User = Depends(get_current_user)
# ):
#     # Fetch chat
#     chat = db.query(Chat).filter(Chat.id == chat_id).first()
#     if not chat:
#         raise HTTPException(status_code=404, detail="Chat not found")
#     if chat.user_id != current_user.id:
#         raise HTTPException(status_code=403, detail="You don't have access to this chat")

#     # Fetch chat history
#     history = db.query(ChatHistory)\
#         .filter(ChatHistory.chat_id == chat_id)\
#         .order_by(ChatHistory.timestamp.asc())\
#         .all()

#     history_prompt = "\n".join(f"{entry.sender}: {entry.message}" for entry in history)

#     # Initialize these variables to ensure they exist in all paths
#     group_ids = []
#     group_info = {"formatted": "", "tones": [], "styles": []}

#     # Handle casual greetings separately
#     if is_greeting(user_prompt):
#         full_prompt = f"""
# You are a friendly AI assistant chatting with a user.

# The user said: "{user_prompt}"

# Respond in a warm, conversational way — say hello, offer help, and invite them to ask about group content.
# """
#     else:
#         # Fetch group data, including tone and style metadata
#         group_ids = [group.id for group in chat.groups]
#         group_info = fetch_group_data(group_ids, db)

#         if not group_info["formatted"]:
#             raise HTTPException(status_code=404, detail="No content available for this chat")

#         full_prompt = f"""
# You are a helpful assistant having an ongoing conversation with a user.

# The user is referring to content from multiple sources, each with different tone and style. Please synthesize and respond accordingly.
# {group_info["formatted"]}

# Conversation so far:
# {history_prompt}

# User: {user_prompt}
# Assistant:
# """

#     # Call Ollama LLM
#     try:
#         response = llm(full_prompt)
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"LLM error: {str(e)}")

#     # Avoid duplicate chat history entries
#     if not db.query(ChatHistory).filter(
#         ChatHistory.chat_id == chat_id,
#         ChatHistory.sender == "User",
#         ChatHistory.message == user_prompt.strip()
#     ).first():
#         db.add(ChatHistory(chat_id=chat_id, message=user_prompt.strip(), sender="User"))

#     if not db.query(ChatHistory).filter(
#         ChatHistory.chat_id == chat_id,
#         ChatHistory.sender == "Assistant",
#         ChatHistory.message == response.strip()
#     ).first():
#         db.add(ChatHistory(chat_id=chat_id, message=response.strip(), sender="Assistant"))

#     db.commit()

#     return {
#         "response": response,
#         "chat_id": chat_id,
#         "user_message": user_prompt,
#         "assistant_message": response,
#         "based_on_groups": group_ids,
#         "tone_used": ", ".join([tone.capitalize() for tone in group_info["tones"]]) if group_info["tones"] else "",
#         "style_used": ", ".join([style.capitalize() for style in group_info["styles"]]) if group_info["styles"] else "",
#         "history": [{"sender": h.sender, "message": h.message, "timestamp": h.timestamp} for h in history] + [
#             {"sender": "User", "message": user_prompt},
#             {"sender": "Assistant", "message": response}
#         ]
#     }


@chat_router.post("/generate_group_response")
def generate_group_response(
    chat_id: int,
    user_prompt: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    if chat.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You don't have access to this chat")

    chat_session = db.query(ChatSession).filter(ChatSession.chat_id == chat_id).first()
    if not chat_session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    chat.chatsession_id = chat_session.id

    group_ids = [group.id for group in chat.groups]
    group_info = fetch_group_data(group_ids, db)

    if not group_info["formatted"]:
        raise HTTPException(status_code=404, detail="No content available for this chat")

    # Get conversation history from session
    history = chat_session.conversation or []

    history_prompt = "\n".join(f"{entry['sender']}: {entry['message']}" for entry in history)

    full_prompt = f"""
You are a helpful assistant having an ongoing conversation with a user.

The user is referring to content from multiple sources, each with different tone and style. Please synthesize and respond accordingly.
{group_info["formatted"]}

Conversation so far:
{history_prompt}

User: {user_prompt}
Assistant:
"""

    try:
        response = llm(full_prompt)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM error: {str(e)}")

    # Update Chat fields
    chat.query = user_prompt
    chat.response_text = response.strip()

    # Append conversation entries into session
    timestamp = datetime.datetime.utcnow().isoformat()
    chat_session.conversation.append(
        {"sender": "User", "message": user_prompt.strip(), "timestamp": timestamp}
    )
    chat_session.conversation.append(
        {"sender": "Assistant", "message": response.strip(), "timestamp": timestamp}
    )

    db.commit()

    return {
        "response": response,
        "chat_id": chat_id,
        "user_message": user_prompt,
        "assistant_message": response,
        "based_on_groups": group_ids,
        "tone_used": ", ".join([tone.capitalize() for tone in group_info["tones"]]) if group_info["tones"] else "",
        "style_used": ", ".join([style.capitalize() for style in group_info["styles"]]) if group_info["styles"] else "",
        "history": chat_session.conversation
    }



@chat_router.put("/{chat_name}")
def update_chat_api(chat_name: str, payload: ChatUpdate, db: Session = Depends(get_db)):
    return update_chat(db, chat_name, payload.name)

@chat_router.delete("/{chat_name}")
def delete_chat_api(chat_name: str, db: Session = Depends(get_db)):
    return delete_chat(db, chat_name)

@chat_router.get("/list/{user_id}")
def list_chats_api(user_id: int, db: Session = Depends(get_db)):
    return list_chats(db, user_id)
