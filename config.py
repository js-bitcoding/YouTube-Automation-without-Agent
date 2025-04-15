import os
from dotenv import load_dotenv

load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:test123@localhost/youtube_automation")

THUMBNAIL_STORAGE_PATH = os.getenv("THUMBNAIL_STORAGE_PATH")
GENERATED_THUMBNAILS_PATH = os.getenv("GENERATED_THUMBNAILS_PATH")
GENERATED_AUDIO_PATH = os.getenv("GENERATED_AUDIO_PATH")
VOICE_TONE_DIR = os.getenv("VOICE_TONE_DIR")
UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER")