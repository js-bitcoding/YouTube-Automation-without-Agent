import os
import re
import wave
import json
import uuid
import whisper
import requests
import subprocess
from fastapi import UploadFile, HTTPException, status
from pathlib import Path
from PyPDF2 import PdfReader
from pydub import AudioSegment
import google.generativeai as genai
from vosk import Model, KaldiRecognizer
from docx import Document as DocxDocument
from youtube_transcript_api import YouTubeTranscriptApi
from config import GEMINI_API_KEY, YOUTUBE_API_KEY, VOICE_TONE_DIR
from utils.logging_utils import logger

GEMINI_API_KEY = GEMINI_API_KEY
genai.configure(api_key=GEMINI_API_KEY)

def analyze_transcript_style(transcript: str):
    """
    Analyzes the speaking style and tone/accent from a provided transcript.

    Args:
        transcript (str): The transcript of speech or dialogue to be analyzed.

    Returns:
        dict: A dictionary with two keys:
            - "style": The speaking style (e.g., informal, educational, storytelling, etc.)
            - "tone": The speaking tone or accent (e.g., casual, energetic, calming, etc.)
    
    If the analysis fails or is not returned, defaults to "Casual" for both style and tone.
    """
    analysis_prompt = f"""
    You are a language expert. Analyze the following transcripts and describe take time if you want but give the exact details about:
    1. The speaking **style** (e.g., informal, enthusiastic, educational, storytelling, motivational, etc.)
    2. The speaking **tone/accent** (e.g., casual, serious, energetic, calming, etc.)

    ### Transcript:
    {transcript}

    Just provide in simple text without markdown and give only one value for both:
    - Style:
    - Tone:

    """

    model = genai.GenerativeModel("gemini-1.5-pro-latest")
    response = model.generate_content(analysis_prompt)
    style = ""
    tone = ""
    if response and response.text:
        lines = response.text.splitlines()
        logger.info(f"lines:::{lines}")
        for line in lines:
            if line.lower().startswith("style:"):
                style = line.split(":", 1)[1].strip()
                logger.info(f"Style:::{style}")
            if line.lower().startswith("tone:"):
                tone = line.split(":", 1)[1].strip()
                logger.info(f"Tone:::{tone}")
        return {"tone": tone, "style": style}
    return "Casual", "Casual"

def generate_script(document_content: str, style: str, tone: str, mode: str = "Short-form"):
    """
    Generates a detailed YouTube video script based on the provided transcript, tone, style, and mode.

    Args:
        document_content (str): The transcript or content to base the YouTube script on.
        style (str): The speaking style for the script (e.g., informal, educational, motivational).
        tone (str): The speaking tone/accent for the script (e.g., casual, energetic, calming).
        mode (str, optional): The mode of the script generation. Can be "Short-form", "Long-form", or "Storytelling". Defaults to "Short-form".

    Returns:
        str: The generated YouTube video script based on the given parameters. If there's an error during generation, returns "Error generating script".
    
    Instructions for generation:
    - Expands on the provided transcript, ensuring clarity, engagement, and detailed insights.
    - Adapts the script to the specified mode, style, and tone.
    - Ensures the script can be easily converted into speech.
    """
    logger.info(f"Transcript inside the generate with gemini function :::::::: {document_content}")
    logger.info(f"mode ::: {mode} tone ::: {tone} style ::: {style}")
    prompt = f"""Generate a YouTube video script in {mode} mode with a {tone} tone and {style} style.
        You are an expert YouTube scriptwriter. Your task is to generate a **unique and detailed YouTube video script** while maintaining the **meaning and context** of the provided transcript.  

        ### **Instructions:**  
        1. **DO NOT summarize** the transcript. Instead, expand on it with more details, engaging explanations, and additional insights.  
        2. Maintain a **logical flow** with pauses (`...`) where needed for narration.
        3. Add a **YouTube intro hook** based on the selected **tone and style** to grab attention instantly.  
        4. If the mode is **long-form**, ensure the script is **detailed, engaging, and more descriptive** than the original.  
        5. If the mode is **short-form**, keep the content **concise but impactful**, without summarizing.  
        6. If the mode is **storytelling**, extend the transcript significantly, adding **rich descriptions, emotions, and narrative depth** while preserving its meaning.  
        7. **Rephrase sentences** naturally to avoid repetition but retain the core ideas.  
        8. **Avoid using escape sequences** in the generated text.  
        9. Ensure the script can be easily converted into speech.  

        ### **Document Content (Reference):**  
        {document_content}

        ### **Generate a new, detailed, and engaging YouTube script based on the above guidelines.**  
        """

    logger.info("Generating Script with the Gemini::::", prompt)
    model = genai.GenerativeModel("gemini-1.5-pro-latest")
    response = model.generate_content(prompt)
    logger.info(f"Response form Gemini :: {response}")
    if response and response.text:
        formatted_script = response.text.replace("\n", "\n\n")
        return formatted_script
    else:
        return "Error generating script"

def convert_to_wav(input_file: str) -> str:
    """
    Converts an audio file to WAV format with specific parameters.

    Args:
        input_file (str): The path to the input audio file to be converted.

    Returns:
        str: The path to the converted WAV file.

    Converts the input audio file to a WAV file with the following settings:
    - Mono channel
    - 16 kHz sample rate
    - 16-bit sample width (PCM)
    
    If the input file is already in WAV format, it simply returns the input file path without modification.
    """
    file_ext = os.path.splitext(input_file)[-1].lower()
    wav_file = input_file.replace(file_ext, ".wav")
 
    if file_ext != ".wav":
        audio = AudioSegment.from_file(input_file, format=file_ext.replace(".", ""))
        audio = audio.set_channels(1).set_frame_rate(16000).set_sample_width(2)  # Mono, 16kHz, 16-bit PCM
        audio.export(wav_file, format="wav")
 
    return wav_file
 
def transcribe_audio(file_path: str):
    """
    Converts an audio file to WAV format and transcribes the speech to text using Vosk model.

    Args:
        file_path (str): The path to the audio file to be transcribed.

    Returns:
        dict: A dictionary containing the transcribed text under the key "transcription".

    Process:
        - Converts the input audio file to WAV format if it is not already in WAV format.
        - Verifies that the WAV file is mono PCM with 16-bit sample width.
        - Uses the Vosk speech recognition model to transcribe the audio to text.
        - Returns the transcribed text as a string in the dictionary format.

    Raises:
        Exception: If the Vosk model is not found, or if the audio file does not meet the expected format (WAV, mono, PCM).
    """
    model_path = "action_models/vosk-model-small-en-us-0.15" 
    if not os.path.exists(model_path):
        raise Exception("Please download the Vosk model and place it in the 'models' folder.")

    wav_file = convert_to_wav(file_path)

    try:
        with wave.open(wav_file, "rb") as wf:
            if wf.getnchannels() != 1 or wf.getsampwidth() != 2 or wf.getcomptype() != "NONE":
                raise Exception("Audio file must be WAV format mono PCM.")

            model = Model(model_path)
            rec = KaldiRecognizer(model, wf.getframerate())
            result_text = ""

            while True:
                data = wf.readframes(4000)
                if len(data) == 0:
                    break
                if rec.AcceptWaveform(data):
                    res = json.loads(rec.Result())
                    result_text += " " + res.get("text", "")

            res = json.loads(rec.FinalResult())
            result_text += " " + res.get("text", "")
  
    finally:
        if os.path.exists(wav_file):
            os.remove(wav_file)

    return {"transcription": result_text.strip()}

async def handle_voice_tone_upload(file: UploadFile, user_id: int) -> str:
    """
    Handles the upload of a voice tone file, converts it to WAV format if necessary, and stores it.

    Args:
        file (UploadFile): The uploaded audio file (either .mp3 or .wav).
        user_id (int): The user ID associated with the upload.

    Returns:
        str: The path to the stored voice tone file.

    Raises:
        HTTPException: 
            - If the uploaded file is not of type .mp3 or .wav.
            - If any error occurs during the conversion or saving process.
    """
    ext = file.filename.split(".")[-1].lower()
    if ext not in ["mp3", "wav"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .mp3 or .wav files are allowed"
        )

    base_filename = Path(file.filename).stem
    voice_sample_path = Path(VOICE_TONE_DIR) / f"{base_filename}.wav"

    if voice_sample_path.exists():
        return str(voice_sample_path)

    temp_path = Path(VOICE_TONE_DIR) / f"temp_{user_id}.{ext}"

    with open(temp_path, "wb") as f:
        f.write(await file.read())

    try:
        if ext == "mp3":
            audio = AudioSegment.from_mp3(temp_path)
            audio.export(voice_sample_path, format="wav")
        else:
            temp_path.rename(voice_sample_path)

        return str(voice_sample_path)

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

MAX_CHARS = 300
def split_text(text: str, max_length: int = MAX_CHARS):
    """
    Splits a long text into chunks of sentences, ensuring that each chunk does not exceed the specified maximum length.

    Args:
        text (str): The input text to be split into smaller chunks.
        max_length (int, optional): The maximum allowed length for each chunk. Default is `MAX_CHARS`.

    Returns:
        list: A list of text chunks, each of which is a string containing one or more sentences. 
              The length of each chunk will not exceed `max_length`.

    Example:
        text = "This is the first sentence. This is the second sentence. This is the third sentence."
        result = split_text(text, max_length=50)
        print(result)  # Output: ['This is the first sentence. This is the second sentence. ', 
                        'This is the third sentence.']
    """
    sentences = text.split('. ')
    chunks = []
    current = ""
    for sentence in sentences:
        if len(current) + len(sentence) < max_length:
            current += sentence + ". "
        else:
            chunks.append(current.strip())
            current = sentence + ". "
    if current:
        chunks.append(current.strip())
    return chunks

def get_video_details(query: str, max_results: int = 5):
    """
    Uses the YouTube Data API to search for videos matching the specified query.

    Args:
        query (str): The search query to find videos.
        max_results (int, optional): The maximum number of video results to return. Defaults to 5.

    Returns:
        list: A list of dictionaries, each containing details of a video (video ID, title, and link). 
              If the request fails, an empty list is returned.

    Example:
        query = "Python tutorial"
        result = get_video_details(query, max_results=3)
        print(result)
        # Output: [
        #   {"video_id": "abcdefg12345", "title": "Learn Python in 10 minutes", "link": "https://www.youtube.com/watch?v=abcdefg12345"},
        #   {"video_id": "hijklmn67890", "title": "Python for beginners", "link": "https://www.youtube.com/watch?v=hijklmn67890"},
        #   {"video_id": "opqrstuvwxyz", "title": "Master Python quickly", "link": "https://www.youtube.com/watch?v=opqrstuvwxyz"}
        # ]
    """
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet",
        "q": query,
        "maxResults": max_results,
        "key": YOUTUBE_API_KEY,
        "type": "video"
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        items = response.json().get("items", [])
        video_details = []
        for item in items:
            video_id = item["id"]["videoId"]
            title = item["snippet"]["title"]
            link = f"https://www.youtube.com/watch?v={video_id}"
            video_details.append({
                "video_id": video_id,
                "title": title,
                "link": link
            })
        return video_details
    else:
        return []

def get_video_id(youtube_url: str):
    """
    Extracts the video ID from a YouTube URL.

    Args:
        youtube_url (str): The URL of the YouTube video.

    Returns:
        str: The extracted video ID (11 characters long) if the URL is valid.
             Returns None if the URL doesn't contain a valid video ID.

    Example:
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        video_id = get_video_id(url)
        print(video_id)
        # Output: "dQw4w9WgXcQ"
    """
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", youtube_url)
    return match.group(1) if match else None

def fetch_transcript(youtube_url: str):
    """
    Fetches the transcript of a YouTube video.

    This function first attempts to retrieve the transcript directly using the YouTube API. 
    If no transcript is available, it will attempt to download the video’s audio and use the Whisper model for transcription.

    Args:
        youtube_url (str): The URL of the YouTube video for which the transcript is requested.

    Returns:
        tuple: A tuple containing:
            - str or None: The transcript text if available or None if no transcript could be fetched.
            - str or None: An error message if something goes wrong, or None if the operation is successful.
    """
    video_id = get_video_id(youtube_url)
    if not video_id:
        return None, "Invalid YouTube URL"
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        logger.info(f"transcript list :: {transcript_list}")
        transcript_text = " ".join([item["text"] for item in transcript_list])
        logger.info(f"transcript text :: {transcript_text}")
        return (transcript_text if transcript_text else None), None
    except Exception as e:
        logger.info(f"No subtitles found for video {video_id}. Trying Whisper transcription...")

        unique_filename = f"{uuid.uuid4().hex}.mp3"
        audio_path = os.path.join("tmp", unique_filename)

        if download_audio(youtube_url, audio_path):
            if os.path.exists(audio_path):
                try:
                    transcript_text = transcribe_audio_with_whisper(audio_path)
                    os.remove(audio_path)
                    return transcript_text, None
                except Exception as whisper_error:
                    return None, f"Whisper transcription failed: {whisper_error}"
            else:
                return None, f"Audio file not found at path: {audio_path}"
        else:
            return None, f"Failed to download audio for transcription"

def format_script_response(raw_script: str) -> str:
    """
    Cleans and formats the generated script by:
    - Removing timestamps like (0:00 - 0:05)
    - Removing markdown (**bold text**)
    - Removing text inside parentheses (e.g., (Upbeat background music starts playing))
    - Keeping only the actual content
    
    Args:
        raw_script (str): The raw YouTube video script that may contain timestamps, markdown, and parentheses.

    Returns:
        str: A cleaned and formatted version of the script with the unwanted parts removed.

    """
    cleaned_script = re.sub(r'\(\d{1,2}:\d{2} - \d{1,2}:\d{2}\)', '', raw_script)
    cleaned_script = re.sub(r'\*\*(.*?)\*\*', r'\1', cleaned_script)
    cleaned_script = re.sub(r'\(.*?\)', '', cleaned_script)
    cleaned_script = re.sub(r'\n+', '\n', cleaned_script).strip()

    return cleaned_script

def download_audio(video_url: str, output_path: str) -> bool:
    """
    Downloads the audio from a YouTube video using `yt-dlp` and saves it in MP3 format.

    Args:
        video_url (str): The URL of the YouTube video to download audio from.
        output_path (str): The file path where the downloaded audio should be saved.

    Returns:
        bool: True if the audio was downloaded and saved successfully, False if there was an error.
    """
    try:
        command = [
            "yt-dlp",
            "-x", "--audio-format", "mp3",
            "-o", output_path,
            video_url
        ]
        subprocess.run(command, check=True)
        return True
    except subprocess.CalledProcessError as e:
        logger.info(f"Error downloading audio: {e}")
        return False

def transcribe_audio_with_whisper(audio_path: str) -> str:
    """
    Transcribes the audio file using Whisper model.

    Args:
        audio_path (str): Path to the audio file to transcribe.

    Returns:
        str: Transcribed text from the audio file.
    """
    model = whisper.load_model("base")
    result = model.transcribe(audio_path)
    return result["text"]

def get_user_voice_sample(user_id: int) -> str:
    """
    Retrieves the user's voice sample file (either .mp3 or .wav format).

    Args:
        user_id (int): The ID of the user to retrieve the voice sample for.

    Returns:
        str: Path to the voice sample file if it exists, otherwise None.
    """
    for ext in ["mp3", "wav"]:
        path = os.path.join(VOICE_TONE_DIR, f"user_{user_id}.{ext}")
        if os.path.exists(path):
            return path
    return None

def extract_text_from_file(file_path: str) -> str:
    """
    Extracts text from various file formats.

    Args:
        file_path (str): Path to the file to extract text from.

    Returns:
        str: Extracted text from the file.
    """
    if file_path.endswith(".pdf"):
        return extract_text_from_pdf(file_path)
    elif file_path.endswith(".docx"):
        return extract_text_from_docx(file_path)
    elif file_path.endswith(".txt"):
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    return ""

def extract_text_from_pdf(file_path: str) -> str:
    """
    Extracts text from a PDF file.

    Args:
        file_path (str): Path to the PDF file.

    Returns:
        str: Extracted text from the PDF file.
    """
    reader = PdfReader(file_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text.strip()

def extract_text_from_docx(file_path: str) -> str:
    """
    Extracts text from a DOCX file.

    Args:
        file_path (str): Path to the DOCX file.

    Returns:
        str: Extracted text from the DOCX file.
    """
    doc = DocxDocument(file_path)
    text = "\n".join([para.text for para in doc.paragraphs])
    return text.strip()
