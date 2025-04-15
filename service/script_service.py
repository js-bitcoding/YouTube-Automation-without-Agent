import os
import re
import wave
import json
import uuid
# import torch
import whisper
import requests
# import traceback
# import torchaudio
import subprocess
# from gtts import gTTS
# from uuid import uuid4
from pathlib import Path
from PyPDF2 import PdfReader
from pydub import AudioSegment
import google.generativeai as genai
# from tortoise.api import TextToSpeech
from vosk import Model, KaldiRecognizer
from docx import Document as DocxDocument
# from tortoise.utils.audio import load_audio
from fastapi import UploadFile, HTTPException, status
from youtube_transcript_api import YouTubeTranscriptApi
from config import GEMINI_API_KEY, YOUTUBE_API_KEY, GENERATED_AUDIO_PATH, VOICE_TONE_DIR

GEMINI_API_KEY = GEMINI_API_KEY
genai.configure(api_key=GEMINI_API_KEY)

def analyze_transcript_style(transcript: str):
    """Analyze style and accent from the transcript."""
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
        print(f"lines:::{lines}")
        for line in lines:
            if line.lower().startswith("style:"):
                style = line.split(":", 1)[1].strip()
                print(f"Style:::{style}")
            if line.lower().startswith("tone:"):
                tone = line.split(":", 1)[1].strip()
                print(f"Tone:::{tone}")
        return style, tone
    return "Casual", "Casual"

# def generate_script(transcript: str, mode: str = "Short-form", tone: str = "Casual", style: str = "Casual"):
#     print(f"Transcript inside the generate with ollama function :::::::: {transcript}")
#     print(f"mode ::: {mode} tone ::: {tone} style ::: {style}")
#     prompt = f"""Generate a YouTube video script in {mode} mode with a {tone} tone and {style} style.
#         You are an expert YouTube scriptwriter. Your task is to generate a **unique and detailed YouTube video script** while maintaining the **meaning and context** of the provided transcript.  

#         ### **Instructions:**  
#         1. **DO NOT summarize** the transcript. Instead, expand on it with more details, engaging explanations, and additional insights.  
#         2. Maintain a **logical flow** with pauses (`...`) where needed for narration.
#         3. Add a **YouTube intro hook** based on the selected **tone and style** to grab attention instantly.  
#         4. If the mode is **long-form**, ensure the script is **detailed, engaging, and more descriptive** than the original.  
#         5. If the mode is **short-form**, keep the content **concise but impactful**, without summarizing.  
#         6. If the mode is **storytelling**, extend the transcript significantly, adding **rich descriptions, emotions, and narrative depth** while preserving its meaning.  
#         7. **Rephrase sentences** naturally to avoid repetition but retain the core ideas.  
#         8. **Avoid using escape sequences** in the generated text.  
#         9. Ensure the script can be easily converted into speech.

#         ### **Given Transcript (Reference):**  
#         {transcript}  

#         ### **Generate a new, detailed, and engaging YouTube script based on the above guidelines.**  
#         """

#     print("Generating Script with the Gemini::::", prompt)
#     model = genai.GenerativeModel("gemini-1.5-pro-latest")
#     response = model.generate_content(prompt)
#     print(f"Response form Gemini :: {response}")

#     if response and response.text:
#         formatted_script = response.text.replace("\n", "\n\n")
#         return formatted_script
#     else:
#         return "Error generating script"

def generate_script(document_content: str, style: str, tone: str, mode: str = "Short-form"):
    print(f"Transcript inside the generate with gemini function :::::::: {document_content}")
    print(f"mode ::: {mode} tone ::: {tone} style ::: {style}")
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

    print("Generating Script with the Gemini::::", prompt)
    model = genai.GenerativeModel("gemini-1.5-pro-latest")
    response = model.generate_content(prompt)
    print(f"Response form Gemini :: {response}")
    if response and response.text:
        formatted_script = response.text.replace("\n", "\n\n")
        return formatted_script
    else:
        return "Error generating script"

def convert_to_wav(input_file: str) -> str:
    file_ext = os.path.splitext(input_file)[-1].lower()
    wav_file = input_file.replace(file_ext, ".wav")
 
    if file_ext != ".wav":
        audio = AudioSegment.from_file(input_file, format=file_ext.replace(".", ""))
        audio = audio.set_channels(1).set_frame_rate(16000).set_sample_width(2)  # Mono, 16kHz, 16-bit PCM
        audio.export(wav_file, format="wav")
 
    return wav_file
 
def transcribe_audio(file_path: str):
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

# tts_model = TextToSpeech()

async def handle_voice_tone_upload(file: UploadFile, user_id: int) -> str:
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

# def generate_speech(text: str, speech_name: str, user_id: int, voice_sample_path: str) -> str:
#     try:
#         if not speech_name.lower().endswith(".mp3"):
#             speech_name += ".mp3"

#         unique_id = uuid4().hex[:6]
#         filename = f"{os.path.splitext(speech_name)[0]}_{unique_id}.mp3"
#         file_path = os.path.join(GENERATED_AUDIO_PATH, filename)

#         chunks = split_text(text, max_length=25)

#         waveform_list = []

#         if voice_sample_path and os.path.exists(voice_sample_path):
#             print(f"Using custom voice cloning :: {voice_sample_path}")
#             try:
#                 voice_samples = [load_audio(voice_sample_path, 22050)]
#                 conditioning_latents = tts_model.get_conditioning_latents(voice_samples)
#                 print(f"voice_samples: {voice_samples}")
#             except Exception as e: 
#                 print("Error in load_voice()")
#                 traceback.print_exc()
#                 raise HTTPException(status_code=500, detail="Voice loading failed")
#             print(f"conditioning_latents: {conditioning_latents}")
#             print("Voice samples loaded successfully.")
#             print(f"Chunks: {chunks}")
#             print("Appending generated waveform...")

#             for chunk in chunks:
#                 generated = tts_model.tts_with_preset(
#                     text=chunk,
#                     voice_samples=voice_samples,
#                     conditioning_latents=conditioning_latents,
#                     preset="fast",
#                     num_autoregressive_samples=4
#                 )
#                 waveform_list.append(generated.squeeze(0).cpu())

#             final_waveform = torch.cat(waveform_list, dim=1)
#             torchaudio.save(file_path, final_waveform, 24000)
#             return f"/{file_path}"

#         else:
#             combined = AudioSegment.empty()
#             for chunk in chunks:
#                 temp_path = f"{uuid4().hex[:6]}_temp.mp3"
#                 tts = gTTS(chunk)
#                 tts.save(temp_path)
#                 audio = AudioSegment.from_mp3(temp_path)
#                 combined += audio
#                 os.remove(temp_path)
#             combined.export(file_path, format="mp3")
#             return f"/{file_path}"
#     except Exception as e:
#         print("facing error inside function :: ", e)

def get_video_details(query: str, max_results: int = 5):
    """
    Uses the YouTube Data API to search for videos matching the query.
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
    """
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", youtube_url)
    return match.group(1) if match else None

def fetch_transcript(youtube_url: str):
    """
    Fetches the transcript of a YouTube video.
    """
    video_id = get_video_id(youtube_url)
    if not video_id:
        return None, "Invalid YouTube URL"
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        print(f"transcript list :: {transcript_list}")
        transcript_text = " ".join([item["text"] for item in transcript_list])
        print(f"transcript text :: {transcript_text}")
        return (transcript_text if transcript_text else None), None
    except Exception as e:
        print(f"No subtitles found for video {video_id}. Trying Whisper transcription...")

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
    """
    cleaned_script = re.sub(r'\(\d{1,2}:\d{2} - \d{1,2}:\d{2}\)', '', raw_script)
    cleaned_script = re.sub(r'\*\*(.*?)\*\*', r'\1', cleaned_script)
    cleaned_script = re.sub(r'\(.*?\)', '', cleaned_script)
    cleaned_script = re.sub(r'\n+', '\n', cleaned_script).strip()

    return cleaned_script

def download_audio(video_url: str, output_path: str) -> bool:
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
        print(f"Error downloading audio: {e}")
        return False

def transcribe_audio_with_whisper(audio_path: str) -> str:
    model = whisper.load_model("base")  # Or use "medium" / "large" if you want better quality
    result = model.transcribe(audio_path)
    return result["text"]

def get_user_voice_sample(user_id: int) -> str:
    for ext in ["mp3", "wav"]:
        path = os.path.join(VOICE_TONE_DIR, f"user_{user_id}.{ext}")
        if os.path.exists(path):
            return path
    return None

def extract_text_from_file(file_path: str) -> str:
    if file_path.endswith(".pdf"):
        return extract_text_from_pdf(file_path)
    elif file_path.endswith(".docx"):
        return extract_text_from_docx(file_path)
    elif file_path.endswith(".txt"):
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    return ""

def extract_text_from_pdf(file_path: str) -> str:
    reader = PdfReader(file_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text.strip()

def extract_text_from_docx(file_path: str) -> str:
    doc = DocxDocument(file_path)
    text = "\n".join([para.text for para in doc.paragraphs])
    return text.strip()
