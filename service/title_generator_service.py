# import os
# import re
# import requests
# from dotenv import load_dotenv
# from sqlalchemy.orm import Session
# from langchain.tools import Tool
# from langchain_ollama import OllamaLLM
# from langchain.memory import ConversationBufferMemory
# from langchain.agents import initialize_agent, AgentType
# from database.models import GeneratedTitle
# from utils.logging_utils import logger  

# load_dotenv()

# YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

# llm = OllamaLLM(model="llama3.2:1b")

# title_tool = Tool(
#     name="YouTubeTitleGenerator",
#     func=lambda input_text: generate_titles_prompt(*get_video_metadata(input_text)) 
#     if detect_input_type(input_text) == "url" 
#     else generate_titles_prompt(input_text),
#     description="Generates 5 viral YouTube video titles based on a YouTube video URL or a topic. Input should be a string in the format: '<topic>::<description>'."
# )


# memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)

# agent = initialize_agent(
#     tools=[title_tool],
#     llm=llm,
#     agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,  # ✅ Use this instead
#     verbose=True,
#     memory=memory,
#     handle_parsing_errors=True
# )


# def extract_video_id(youtube_url: str) -> str:
#     """
#     Extract the video ID from a YouTube URL.

#     Args:
#         youtube_url (str): The YouTube video URL.

#     Returns:
#         str: The video ID if found, or None if the URL is invalid or does not contain a video ID.
#     """
#     try:
#         match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", youtube_url)
#         return match.group(1) if match else None
#     except Exception as e:
#         logger.error(f"Error extracting video ID from URL: {e}")
#         return None

# def get_video_metadata(youtube_url: str):
#     """
#     Retrieve a video's title and description via the YouTube Data API.

#     Args:
#         youtube_url (str): URL of the YouTube video.

#     Returns:
#         tuple: (title (str) or None, description (str) or None) if found;
#                otherwise (None, None).
#     """
#     try:
#         video_id = extract_video_id(youtube_url)
#         if not video_id:
#             return None, None

#         api_url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet&id={video_id}&key={YOUTUBE_API_KEY}"

#         response = requests.get(api_url, timeout=10)
#         response.raise_for_status()
#         data = response.json()

#         if "items" in data and len(data["items"]) > 0:
#             snippet = data["items"][0]["snippet"]
#             video_topic = snippet.get("title", "Unknown Title")
#             video_description = snippet.get("description", "")
#             return video_topic, video_description
#         else:
#             return None, None
#     except requests.exceptions.RequestException as e:
#         logger.error(f"Error fetching video metadata for URL {youtube_url}: {e}")
#         return None, None
#     except Exception as e:
#         logger.error(f"Unexpected error while retrieving metadata for {youtube_url}: {e}")
#         return None, None

# def process_generated_titles(response: str) -> list:
#     """
#     Clean and process AI-generated titles from a response string.

#     Args:
#         response (str): The raw AI-generated title response.

#     Returns:
#         list: A list of processed titles, up to a maximum of 6.
#     """
#     try:
#         if not response:
#             return []

#         titles = response.strip().split("\n")
#         titles = [re.sub(r"^\d+[\.\)]?\s*", "", title).strip() for title in titles if title.strip()]
        
#         return titles[:6]
#     except Exception as e:
#         logger.error(f"Error processing generated titles: {e}")
#         return []

# def generate_titles_prompt(input_text: str) -> str:
#     if "::" in input_text:
#         topic, description = input_text.split("::", 1)
#     else:
#         topic, description = input_text, ""
    
#     return (
#         f"Generate exactly 5 viral YouTube video titles based on the following details:\n\n"
#         f"Title: {topic.strip()}\nDescription: {description.strip()}\n\n"
#         f"Output each title on a new line."
#     )

# def detect_input_type(user_input: str):
#     """
#     Determine if the input is a YouTube URL or a plain topic.

#     Args:
#         user_input (str): The input string to analyze.

#     Returns:
#         str: "url" if the input is a YouTube URL, otherwise "topic".
#     """
#     try:
#         if "youtube.com" in user_input or "youtu.be" in user_input:
#             return "url"
#         return "topic"
#     except Exception as e:
#         logger.error(f"Error detecting input type: {e}")
#         return "topic"

# def generate_ai_titles(user_input: str, user_id: int, db: Session):
#     """
#     Generate 5 AI-powered YouTube titles based on user input and store them in the database.

#     Args:
#         user_input (str): The input topic or YouTube URL.
#         user_id (int): The ID of the user requesting title generation.
#         db (Session): SQLAlchemy session for database interaction.

#     Returns:
#         dict: A dictionary containing the generated titles.
    
#     Raises:
#         TypeError: If 'db' is not a Session instance.
#         ValueError: If title generation fails or the agent response format is incorrect.
#     """
#     if not isinstance(db, Session):
#         raise TypeError(f"Expected 'db' to be a Session instance, but got {type(db)}")

#     try:
#         response = agent.invoke({"input": generate_titles_prompt(user_input)})
        
#         if isinstance(response, dict) and "output" in response:
#             response = response["output"]
        
#         if not isinstance(response, str):
#             raise ValueError(f"Unexpected agent response format: {response}")
        
#         titles = process_generated_titles(response)

#         db_title = GeneratedTitle(video_topic=user_input, titles=titles, user_id=user_id)
#         db.add(db_title)
#         db.commit()
#         db.refresh(db_title)

#         return {"titles": titles}

#     except requests.exceptions.RequestException as e:
#         logger.error(f"Request error during AI title generation: {e}")
#         raise ValueError("Failed to generate titles due to a network issue. Please try again later.")
#     except Exception as e:
#         logger.error(f"Error during AI title generation: {e}")
#         raise ValueError("Failed to generate titles. Please try again later.")

import os
import re
import requests
from dotenv import load_dotenv
from langchain.tools import Tool
from sqlalchemy.orm import Session
from langchain_community.llms import Ollama
from database.models import GeneratedTitle
from langchain.agents import initialize_agent, AgentType

load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
llm = Ollama(model="llama3.2:1b")

def extract_video_id(youtube_url: str) -> str:
    """
    Extracts the video ID from a YouTube URL.

    Args:
        youtube_url (str): The full URL of the YouTube video.

    Returns:
        str: The 11-character video ID if found, else None.
    """
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", youtube_url)
    return match.group(1) if match else None

def get_video_metadata(youtube_url: str):
    """
    Fetches the video title and description using the YouTube Data API.

    Args:
        youtube_url (str): The URL of the YouTube video.

    Returns:
        tuple: (title, description) if successful, otherwise (None, None).
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
            return snippet.get("title", "Unknown Title"), snippet.get("description", "")
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Failed to fetch video metadata: {e}")
    except Exception as e:
        print(f"[ERROR] Unexpected error in get_video_metadata: {e}")
    
    return None, None

def process_generated_titles(response: str) -> list:
    """
    Processes a string response of generated titles into a list format.

    Args:
        response (str): Raw string output from the AI agent.

    Returns:
        list: A list of cleaned titles, max 6.
    """
    if not response:
        return []

    try:
        titles = response.strip().split("\n")
        titles = [re.sub(r"^\d+[\.\)]?\s*", "", title).strip() for title in titles if title.strip()]
        return titles[:6]
    except Exception as e:
        print(f"[ERROR] Failed to process generated titles: {e}")
        return []

def generate_titles_prompt(video_topic: str, video_description: str = "") -> str:
    """
    Constructs the prompt to generate YouTube titles.

    Args:
        video_topic (str): The main topic or title.
        video_description (str, optional): Description of the video.

    Returns:
        str: Formatted prompt string.
    """
    return (
        f"Generate exactly 5 viral YouTube video titles based on the following details:\n\n"
        f"Title: {video_topic}\nDescription: {video_description}\n\n"
        f"Output each title on a new line."
    )

def detect_input_type(user_input: str) -> str:
    """
    Determines if input is a YouTube URL or plain text topic.

    Args:
        user_input (str): The input provided by the user.

    Returns:
        str: "url" if input is a YouTube link, else "topic".
    """
    return "url" if "youtube.com" in user_input or "youtu.be" in user_input else "topic"

# Tool setup
title_tool = Tool(
    name="YouTubeTitleGenerator",
    func=lambda input_text: generate_titles_prompt(*get_video_metadata(input_text)) 
    if detect_input_type(input_text) == "url" 
    else generate_titles_prompt(input_text),
    description="Generates 5 viral YouTube video titles based on a YouTube video URL or a topic."
)

agent = initialize_agent(
    tools=[title_tool],
    llm=llm,
    agent=AgentType.OPENAI_FUNCTIONS,
    verbose=True,
    handle_parsing_errors=True
)

def generate_ai_titles(user_input: str, user_id: int, db: Session) -> dict:
    """
    Generates and stores AI-generated YouTube titles.

    Args:
        user_input (str): YouTube URL or a topic.
        user_id (int): ID of the user making the request.
        db (Session): SQLAlchemy database session.

    Returns:
        dict: Dictionary containing the generated titles.

    Raises:
        TypeError: If `db` is not a SQLAlchemy Session.
        ValueError: If title generation fails at any point.
    """
    if not isinstance(db, Session):
        raise TypeError(f"Expected 'db' to be a Session instance, but got {type(db)}")

    try:
        if detect_input_type(user_input) == "url":
            video_topic, video_description = get_video_metadata(user_input)
            if not video_topic:
                raise ValueError("Failed to retrieve video metadata from YouTube URL.")
            prompt = generate_titles_prompt(video_topic, video_description)
        else:
            prompt = generate_titles_prompt(user_input)

        response = agent.invoke({"input": prompt})

        if isinstance(response, dict) and "output" in response:
            response = response["output"]
        if not isinstance(response, str):
            raise ValueError(f"Unexpected agent response format: {response}")

        titles = process_generated_titles(response)
        if not titles:
            raise ValueError("No valid titles generated.")

        db_title = GeneratedTitle(video_topic=user_input, titles=titles, user_id=user_id)
        db.add(db_title)
        db.commit()
        db.refresh(db_title)

        return {"titles": titles}
    
    except Exception as e:
        raise ValueError(f"Failed to generate titles. Error: {e}")
