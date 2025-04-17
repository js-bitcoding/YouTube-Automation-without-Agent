from fastapi import APIRouter, Depends ,HTTPException
from sqlalchemy.orm import Session
from database.models import User,Group,Chat,chat_group_association
from database.schemas import ChatCreate, ChatUpdate
from service.chat_service import create_chat, update_chat, delete_chat, list_chats
from database.db_connection import get_db
from functionality.current_user import get_current_user
from service.chat_ai_agent_service import fetch_group_data,agent

chat_router = APIRouter(prefix="/chats")


@chat_router.post("/create")
def create_chat_api(
    payload: ChatCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Deduplicate group_ids to avoid integrity errors
    unique_group_ids = list(set(payload.group_ids))

    # Fetch the groups from the database
    groups = db.query(Group).filter(Group.id.in_(unique_group_ids)).all()

    # Create a new Chat instance
    chat = Chat(
        name=payload.name,
        user_id=current_user.id
    )

    # Add the chat to the session
    db.add(chat)
    db.commit()  # Commit to get chat.id populated

    # Now that the chat has been added and has a chat.id, check for existing associations
    existing_association_set = set(
        (existing.chat_id, existing.group_id)
        for existing in db.query(chat_group_association).filter(chat_group_association.c.chat_id == chat.id).all()
    )

    # Add only the groups that aren't already associated
    for group in groups:
        # If the association doesn't exist, add it to the chat
        if (chat.id, group.id) not in existing_association_set:
            chat.groups.append(group)

    # Commit the final changes
    db.commit()
    db.refresh(chat)

    return chat





@chat_router.post("/generate_group_response")
def generate_group_response(
    chat_id: int,         # Chat ID to fetch associated group data
    user_prompt: str,     # User prompt for the agent to process
    db: Session = Depends(get_db),  # Dependency to get the DB session
    current_user: User = Depends(get_current_user)  # Dependency to get current user
):
    """
    API endpoint to process group data and generate a response based on user prompt.
    - Fetches the relevant content (from Document or YouTubeVideo) based on the groups associated with the chat_id.
    - Uses the agent to generate a response based on that content and user prompt.
    """

    # Step 1: Fetch the chat
    chat = db.query(Chat).filter(Chat.id == chat_id).first()

    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    # Step 2: Get the group IDs from the associated groups
    group_ids = [group.id for group in chat.groups]

    if not group_ids:
        raise HTTPException(status_code=404, detail="No groups associated with this chat")

    # Step 3: Fetch the relevant group data (documents or video transcripts)
    group_data = fetch_group_data(group_ids, db)

    if not group_data:
        raise HTTPException(status_code=404, detail="No data found for the given groups")

    # Debugging: print the group_data and user_prompt to make sure it's correct
    print("Group Data:", group_data)
    print("User Prompt:", user_prompt)

    # Combine group data and user prompt into a single input
    full_input = f"Here is some content:\n{group_data}\n\nNow, answer the following prompt:\n{user_prompt}"

    # Check for sensitive or prohibited content in the group_data
    prohibited_keywords = ["illegal", "exploit", "harmful", "abuse"]
    if any(keyword in group_data.lower() for keyword in prohibited_keywords):
        raise HTTPException(status_code=400, detail="Content contains prohibited keywords")

    # Step 4: Call the agent to generate a response based on the full input
    try:
        response = agent.invoke({"input": full_input})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error with agent execution: {str(e)}")

    # Return the AI-generated response
    return {"response": response}

@chat_router.put("/{chat_name}")
def update_chat_api(chat_name: str, payload: ChatUpdate, db: Session = Depends(get_db)):
    return update_chat(db, chat_name, payload.name)

@chat_router.delete("/{chat_name}")
def delete_chat_api(chat_name: str, db: Session = Depends(get_db)):
    return delete_chat(db, chat_name)

@chat_router.get("/list/{user_id}")
def list_chats_api(user_id: int, db: Session = Depends(get_db)):
    return list_chats(db, user_id)
