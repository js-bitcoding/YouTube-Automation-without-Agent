import os
import re
import requests
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from langchain.tools import Tool
from langchain_ollama import OllamaLLM
from langchain.memory import ConversationBufferMemory
from langchain.agents import initialize_agent, AgentType
from database.models import GeneratedTitle

load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

llm = OllamaLLM(model="llama3.2:1b")  

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

def extract_video_id(youtube_url: str) -> str:
    """
    Extract the video ID from a YouTube URL.

    Args:
        youtube_url (str): The YouTube video URL.

    Returns:
        str: The video ID if found, or None if the URL is invalid or does not contain a video ID.
    """
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", youtube_url)
    return match.group(1) if match else None

def get_video_metadata(youtube_url: str):
    """
    Retrieve a video's title and description via the YouTube Data API.

    Args:
        youtube_url (str): URL of the YouTube video.

    Returns:
        tuple: (title (str) or None, description (str) or None) if found;
               otherwise (None, None).
    """
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
    """
    Clean and process AI-generated titles from a response string.

    Args:
        response (str): The raw AI-generated title response.

    Returns:
        list: A list of processed titles, up to a maximum of 6.
    """
    if not response:
        return []

    titles = response.strip().split("\n")
    titles = [re.sub(r"^\d+[\.\)]?\s*", "", title).strip() for title in titles if title.strip()]
    
    return titles[:6]  

def generate_titles_prompt(video_topic: str, video_description: str = "") -> str:
    """
    Generate a structured prompt for generating viral YouTube video titles.

    Args:
        video_topic (str): The topic of the video.
        video_description (str, optional): The description of the video (default is an empty string).

    Returns:
        str: A formatted prompt string for generating video titles.
    """
    return (
        f"Generate exactly 5 viral YouTube video titles based on the following details:\n\n"
        f"Title: {video_topic}\nDescription: {video_description}\n\n"
        f"Output each title on a new line."
    )

def detect_input_type(user_input: str):
    """
    Determine if the input is a YouTube URL or a plain topic.

    Args:
        user_input (str): The input string to analyze.

    Returns:
        str: "url" if the input is a YouTube URL, otherwise "topic".
    """
    if "youtube.com" in user_input or "youtu.be" in user_input:
        return "url"
    return "topic"

def generate_ai_titles(user_input: str, user_id: int, db: Session):
    """
    Generate 5 AI-powered YouTube titles based on user input and store them in the database.

    Args:
        user_input (str): The input topic or YouTube URL.
        user_id (int): The ID of the user requesting title generation.
        db (Session): SQLAlchemy session for database interaction.

    Returns:
        dict: A dictionary containing the generated titles.
    
    Raises:
        TypeError: If 'db' is not a Session instance.
        ValueError: If title generation fails or the agent response format is incorrect.
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
