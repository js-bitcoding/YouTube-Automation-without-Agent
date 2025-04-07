import os
from dotenv import load_dotenv

load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:test123@localhost/youtube_automation")

THUMBNAIL_STORAGE_PATH = "assets/thumbnails/"
GENERATED_THUMBNAILS_PATH = "assets/generated/"
GENERATED_AUDIO_PATH = "assets/audio"
VOICE_TONE_DIR = "assets/voice_tones"