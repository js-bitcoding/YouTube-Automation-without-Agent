import io
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
    
    try:
        model = genai.GenerativeModel("gemini-2.0-flash-lite")
        response = model.generate_content(analysis_prompt)

        if response and response.text:
            style = "Unknown"
            tone = "Unknown"
            lines = [line.strip("- ").strip() for line in response.text.splitlines() if line.strip()]

            for line in lines:
                if line.lower().startswith("style:"):
                    style = line.split(":", 1)[1].strip()
                elif line.lower().startswith("tone:"):
                    tone = line.split(":", 1)[1].strip()

            logger.info(f"Extracted Style: {style} | Tone: {tone}")
            return {"tone": tone, "style": style}
        else:
            logger.warning("Empty or malformed model response.")
            return {"tone": "Casual", "style": "Casual"}

    except Exception as e:
        logger.error(f"Error analyzing transcript style: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to analyze transcript style.")

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

    try:
        logger.info("Generating Script with Gemini model...")
        model = genai.GenerativeModel("gemini-1.5-pro-latest")
        response = model.generate_content(prompt)

        logger.info(f"Response from Gemini: {response}")

        if response and response.text:
            formatted_script = response.text.replace("\n", "\n\n")
            return formatted_script
        else:
            logger.warning("Empty or invalid response received from the model.")
            return "Error generating script: No valid response from the model."

    except Exception as e:
        logger.error(f"Error generating script: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate the YouTube script due to an internal error.")

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
    try:
        file_ext = os.path.splitext(input_file)[-1].lower()

        if file_ext == ".wav":
            logger.info(f"The file is already in WAV format: {input_file}")
            return input_file

        wav_file = input_file.replace(file_ext, ".wav")

        logger.info(f"Converting {input_file} to WAV format...")
        audio = AudioSegment.from_file(input_file, format=file_ext.replace(".", ""))
        audio = audio.set_channels(1).set_frame_rate(16000).set_sample_width(2)
        audio.export(wav_file, format="wav")

        logger.info(f"Successfully converted {input_file} to {wav_file}")
        return wav_file

    except Exception as e:
        logger.error(f"Error converting file {input_file} to WAV format: {str(e)}")
        raise RuntimeError(f"Failed to convert {input_file} to WAV format") from e

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
        logger.error("Vosk model not found. Please download the Vosk model and place it in the 'models' folder.")
        raise Exception("Vosk model not found. Please download the Vosk model and place it in the 'models' folder.")

    try:
        wav_file = convert_to_wav(file_path)
    except Exception as e:
        logger.error(f"Error converting file {file_path} to WAV: {e}")
        raise Exception(f"Error converting file {file_path} to WAV.") from e

    try:
        with wave.open(wav_file, "rb") as wf:
            if wf.getnchannels() != 1 or wf.getsampwidth() != 2 or wf.getcomptype() != "NONE":
                logger.error(f"Invalid audio format for file {wav_file}: Expected mono PCM, 16-bit sample width.")
                raise Exception("Audio file must be in WAV format, mono PCM, 16-bit sample width.")

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
        
    except Exception as e:
        logger.error(f"Error during transcription: {e}")
        raise Exception(f"Error during transcription: {e}") from e

    try:
        if os.path.exists(wav_file):
            os.remove(wav_file)
            logger.info(f"Temporary WAV file {wav_file} removed.")
    except Exception as e:
        logger.error(f"Error removing temporary WAV file {wav_file}: {e}")

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
        logger.error(f"Invalid file type uploaded by user {user_id}: {file.filename}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .mp3 or .wav files are allowed"
        )

    base_filename = Path(file.filename).stem
    voice_sample_path = Path(VOICE_TONE_DIR) / f"{base_filename}.wav"

    if voice_sample_path.exists():
        logger.info(f"Voice tone file already exists for user {user_id}: {voice_sample_path}")
        return str(voice_sample_path)

    temp_path = Path(VOICE_TONE_DIR) / f"temp_{user_id}.{ext}"

    try:
        with open(temp_path, "wb") as f:
            f.write(await file.read())
        logger.info(f"File uploaded successfully for user {user_id}: {temp_path}")

        if ext == "mp3":
            try:
                audio = AudioSegment.from_mp3(temp_path)
                audio.export(voice_sample_path, format="wav")
                logger.info(f"Converted {temp_path} to {voice_sample_path}")
            except Exception as e:
                logger.error(f"Error converting MP3 to WAV for user {user_id}: {e}")
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error converting MP3 to WAV.")
        else:
            temp_path.rename(voice_sample_path)
            logger.info(f"Moved {temp_path} to final destination: {voice_sample_path}")

        return str(voice_sample_path)

    except Exception as e:
        logger.error(f"Error processing the uploaded file for user {user_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    finally:
        if temp_path.exists():
            try:
                os.remove(temp_path)
                logger.info(f"Removed temporary file: {temp_path}")
            except Exception as cleanup_error:
                logger.error(f"Error removing temporary file {temp_path}: {cleanup_error}")

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
    try:
        if not text:
            raise ValueError("The input text cannot be empty or None.")

        sentences = text.split('. ')
        if not sentences:
            raise ValueError("The input text must contain at least one sentence.")

        chunks = []
        current = ""

        for sentence in sentences:
            if len(current) + len(sentence) + 1 <= max_length:  
                current += sentence + ". "
            else:
                chunks.append(current.strip())
                current = sentence + ". "
        
        if current:
            chunks.append(current.strip())
        
        return chunks

    except Exception as e:
        print(f"Error in split_text: {str(e)}")
        return []  

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
    try:
        api_key = os.getenv("YOUTUBE_API_KEY")

        if not api_key:
            raise ValueError("YOUTUBE_API_KEY environment variable is not set")

        url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            "part": "snippet",
            "q": query,
            "maxResults": max_results,
            "key": api_key,
            "type": "video"
        }

        response = requests.get(url, params=params)
        response.raise_for_status()  

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

    except requests.exceptions.RequestException as e:
        print(f"Error occurred while fetching YouTube data: {e}")
        return []

    except ValueError as ve:
        print(f"ValueError: {ve}")
        return []

    except Exception as e:
        print(f"Error in get_video_details: {str(e)}")
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
    try:
        if not isinstance(youtube_url, str) or not youtube_url.strip():
            raise ValueError("The input URL must be a valid non-empty string.")

        match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", youtube_url)
        
        if match:
            return match.group(1)
        else:
            return None

    except Exception as e:
        print(f"Error in get_video_id: {str(e)}")
        return None

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
    try:
        if not isinstance(youtube_url, str) or not youtube_url.strip():
            return None, "Invalid input: URL must be a non-empty string"

        video_id = get_video_id(youtube_url)
        if not video_id:
            return None, "Invalid YouTube URL"

        try:
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
            logger.info(f"Transcript found for video {video_id} :: {transcript_list}")

            transcript_text = " ".join([item["text"] for item in transcript_list])
            return transcript_text if transcript_text else None, None

        except Exception as api_error:
            logger.error(f"Failed to fetch transcript via YouTube API for video {video_id}: {api_error}")

            unique_filename = f"{uuid.uuid4().hex}.mp3"
            audio_path = os.path.join("tmp", unique_filename)

            if download_audio(youtube_url, audio_path):
                if os.path.exists(audio_path):
                    try:
                        transcript_text = transcribe_audio_with_whisper(audio_path)
                        os.remove(audio_path)
                        return transcript_text, None
                    except Exception as whisper_error:
                        logger.error(f"Whisper transcription failed for {audio_path}: {whisper_error}")
                        return None, f"Whisper transcription failed: {whisper_error}"

                else:
                    return None, f"Audio file not found at path: {audio_path}"
            else:
                return None, "Failed to download audio for transcription"
    except Exception as e:
        logger.error(f"An error occurred while fetching transcript: {str(e)}")
        return None, f"An error occurred while fetching transcript: {str(e)}"

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
    try:
        if not isinstance(raw_script, str):
            raise ValueError("Input 'raw_script' must be a string")

        cleaned_script = re.sub(r'\(\d{1,2}:\d{2} - \d{1,2}:\d{2}\)', '', raw_script)  
        cleaned_script = re.sub(r'\*\*(.*?)\*\*', r'\1', cleaned_script)  
        cleaned_script = re.sub(r'\(.*?\)', '', cleaned_script)  
        cleaned_script = re.sub(r'\n+', '\n', cleaned_script).strip()  

        return cleaned_script

    except ValueError as e:
        logger.error(f"Input validation error: {e}")
        return f"Error: {e}"
    
    except re.error as e:
        logger.error(f"Regex error occurred: {e}")
        return f"Error: Regex error occurred - {e}"

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return f"Error: An unexpected error occurred - {e}"

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

        result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if result.stdout:
            logger.info(f"yt-dlp output: {result.stdout}")
        if result.stderr:
            logger.error(f"yt-dlp error: {result.stderr}")

        return True

    except subprocess.CalledProcessError as e:

        logger.error(f"Error downloading audio: {e}")
        logger.error(f"stderr: {e.stderr}")
        return False

    except FileNotFoundError as e:
        logger.error("yt-dlp executable not found. Please install yt-dlp.")
        return False

    except Exception as e:
        logger.error(f"Unexpected error while downloading audio: {e}")
        return False

def transcribe_audio_with_whisper(audio_path: str) -> str:
    """
    Transcribes the audio file using Whisper model.

    Args:
        audio_path (str): Path to the audio file to transcribe.

    Returns:
        str: Transcribed text from the audio file.
    """
    try:
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"The audio file at {audio_path} was not found.")
        
        model = whisper.load_model("base")
        
        result = model.transcribe(audio_path)
        
        return result["text"]
    
    except FileNotFoundError as e:
        return f"Error: {e}"

    except whisper.WhisperError as e:
        return f"Whisper model error: {e}"
    
    except Exception as e:
        return f"An unexpected error occurred: {e}"

def get_user_voice_sample(user_id: int) -> str:
    """
    Retrieves the user's voice sample file (either .mp3 or .wav format).

    Args:
        user_id (int): The ID of the user to retrieve the voice sample for.

    Returns:
        str: Path to the voice sample file if it exists, otherwise None.
    """
    try:
        for ext in ["mp3", "wav"]:
            path = os.path.join(VOICE_TONE_DIR, f"user_{user_id}.{ext}")
            
            if os.path.exists(path):
                return path
        
        return None
    
    except FileNotFoundError:
        return f"Error: The directory {VOICE_TONE_DIR} was not found."

    except PermissionError:
        return f"Error: Permission denied when accessing {VOICE_TONE_DIR}."

    except Exception as e:
        return f"An unexpected error occurred: {e}"

async def extract_text_from_file(upload_file: UploadFile) -> str:
    """
    Extracts text from UploadFile (not file path).

    Args:
        upload_file (UploadFile): Uploaded file to extract text from.

    Returns:
        str: Extracted text.
    """
    try:
        print("upload_file :: ", type(upload_file))
        contents = await upload_file.read()
        print("after contents")
        logger.debug(f"File {upload_file.filename} read, size: {len(contents)} bytes")
        
        if upload_file.filename.endswith(".pdf"):
            return extract_text_from_pdf(contents)
        elif upload_file.filename.endswith(".docx"):
            return extract_text_from_docx(contents)
        elif upload_file.filename.endswith(".txt"):
            return contents.decode("utf-8")  
        else:
            raise ValueError("Unsupported file format. Only .pdf, .docx, and .txt files are supported.")
    except Exception as e:
        return f"An unexpected error occurred: {str(e)}"

def extract_text_from_pdf(file_bytes: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text.strip() if text else "No text found in the PDF."
    except Exception as e:
        return f"Error extracting text from PDF: {str(e)}"

def extract_text_from_docx(file_bytes: bytes) -> str:
    try:
        doc = DocxDocument(io.BytesIO(file_bytes))
        text = "\n".join([para.text for para in doc.paragraphs])
        return text.strip() if text else "No text found in the DOCX."
    except Exception as e:
        return f"Error extracting text from DOCX: {str(e)}"
