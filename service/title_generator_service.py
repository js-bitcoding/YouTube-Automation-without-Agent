import os
import re
import requests
from dotenv import load_dotenv
from langchain.tools import Tool
from sqlalchemy.orm import Session
from langchain_community.llms import Ollama
from database.models import GeneratedTitle
from langchain.memory import ConversationBufferMemory
from langchain.agents import initialize_agent, AgentType

load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

llm = Ollama(model="llama3.2:1b")  

def extract_video_id(youtube_url: str) -> str:
    """Extracts video ID from a YouTube URL."""
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", youtube_url)
    return match.group(1) if match else None

def get_video_metadata(youtube_url: str):
    """Fetches video title and description from YouTube API."""
    video_id = extract_video_id(youtube_url)
    if not video_id:
        return None, None

    api_url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet&id={video_id}&key={YOUTUBE_API_KEY}"

    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        data = response.json()

        if "items" in data and len(data["items"]) > 0:
            snippet = data["items"][0]["snippet"]
            video_topic = snippet.get("title", "Unknown Title")
            video_description = snippet.get("description", "")
            return video_topic, video_description
        else:
            return None, None
    except requests.exceptions.RequestException:
        return None, None

def process_generated_titles(response: str) -> list:
    """Cleans and processes AI-generated titles."""
    if not response:
        return []

    titles = response.strip().split("\n")
    titles = [re.sub(r"^\d+[\.\)]?\s*", "", title).strip() for title in titles if title.strip()]
    
    return titles[:5]  

def generate_titles_prompt(video_topic: str, video_description: str = "") -> str:
    """Creates a structured prompt for generating video titles."""
    return (
        f"Generate exactly 5 viral YouTube video titles based on the following details:\n\n"
        f"Title: {video_topic}\nDescription: {video_description}\n\n"
        f"Output each title on a new line."
    )

def detect_input_type(user_input: str):
    """Determines if the input is a YouTube URL or a plain topic."""
    if "youtube.com" in user_input or "youtu.be" in user_input:
        return "url"
    return "topic"

title_tool = Tool(
    name="YouTubeTitleGenerator",
    func=lambda input_text: generate_titles_prompt(*get_video_metadata(input_text)) 
    if detect_input_type(input_text) == "url" 
    else generate_titles_prompt(input_text),
    description="Generates 5 viral YouTube video titles based on a YouTube video URL or a topic."
)

memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)

agent = initialize_agent(
    tools=[title_tool],
    llm=llm,
    agent=AgentType.OPENAI_FUNCTIONS,
    verbose=True,
    memory=memory,
    handle_parsing_errors=True
)

def generate_ai_titles(user_input: str, user_id: int, db: Session):
    """
    Generates 5 AI-powered YouTube titles.
    - Ensures agent invocation is successful.
    - Stores generated titles as a single JSON list instead of separate rows.
    """
    if not isinstance(db, Session):
        raise TypeError(f"Expected 'db' to be a Session instance, but got {type(db)}")

    try:
        response = agent.invoke({"input": generate_titles_prompt(user_input)})
        if isinstance(response, dict) and "output" in response:
            response = response["output"]
        if not isinstance(response, str):
            raise ValueError(f"Unexpected agent response format: {response}")
    except Exception:
        raise ValueError("Failed to generate titles. Please try again later.")

    titles = process_generated_titles(response)

    db_title = GeneratedTitle(video_topic=user_input, titles=titles, user_id=user_id)
    db.add(db_title)
    db.commit()
    db.refresh(db_title)

    return {"titles": titles}
