import os
import json
import auth
import shutil
from uuid import uuid4
from typing import Optional
from sqlalchemy.orm import Session
from fastapi.responses import JSONResponse
from config import GENERATED_THUMBNAILS_PATH, GENERATED_AUDIO_PATH, VOICE_TONE_DIR
from service.script_service import (
    generate_script, 
    transcribe_audio, 
    # text_to_speech, 
    get_video_details, 
    fetch_transcript, 
    format_script_response,
    get_user_voice_sample,
    generate_speech,
    handle_voice_tone_upload
)
# get_trending_videos_with_cc
from service.thumbnail_service import (
    store_thumbnails, 
    generate_image_from_input, 
    validate_thumbnail
)
from pydub import AudioSegment
from functionality.current_user import get_current_user
from database.models import Thumbnail, RemixedScript, Script, User
from fastapi import FastAPI, Depends, UploadFile, File, Form, Query, HTTPException, status
from database.db_connection import SessionLocal, init_db, get_db, engine, Base

Base.metadata.create_all(bind=engine)

app = FastAPI()

@app.on_event("startup")
def startup():
    init_db()

app.include_router(auth.router, prefix="/authentication", tags=["Authentication"])

@app.get("/store/")
def store_api(
    keyword: str = Query(...),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user)
    ):
    result = store_thumbnails(keyword, user_id)
    return {"message": "Thumbnails stored successfully.", "results": result}

@app.get("/search/")
def search_thumbnails(
    keyword: Optional[str] = Query(None),
    text: Optional[str] = Query(None),
    emotion: Optional[str] = Query(None),
    min_faces: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    query = db.query(Thumbnail).filter(Thumbnail.user_id == user.id)

    # Optional filtering
    if keyword:
        query = query.filter(Thumbnail.keyword == keyword)

    if text:
        query = query.filter(Thumbnail.text_detection.ilike(f"%{text}%"))

    if emotion:
        query = query.filter(Thumbnail.emotion == emotion)

    if min_faces is not None:
        query = query.filter(Thumbnail.face_detection >= min_faces)

    thumbnails = query.all()

    if not thumbnails:
        raise HTTPException(status_code=404, detail="No matching thumbnails found.")

    return {
        "keyword": keyword,
        "total": len(thumbnails),
        "thumbnails": [
            {
                "id": t.id,
                "video_id": t.video_id,
                "title": t.title,
                "url": t.url,
                "text_detection": t.text_detection,
                "face_detection": t.face_detection,
                "emotion": t.emotion,
                "color_palette": json.loads(t.color_palette) if t.color_palette else [],
            }
            for t in thumbnails
        ]
    }

@app.post("/validate/")
def validate_thumbnail_api(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user)
):
    # Optional: Save file to temp location
    temp_dir = "temp_uploads"
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, file.filename)

    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Pass the saved file path to your validation logic
    result = validate_thumbnail(temp_path)

    # Optional cleanup
    os.remove(temp_path)

    return result

from diffusers import StableDiffusionPipeline, StableDiffusionImg2ImgPipeline
from PIL import Image
import io
import torch

@app.post("/generate-thumbnail/")
async def generate_thumbnail(prompt: str = Form(...), image: UploadFile = File(...)):
    contents = await image.read()
    image = Image.open(io.BytesIO(contents)).convert("RGB").resize((512, 512))

    # Ensure you have CUDA
    device = "cuda" if torch.cuda.is_available() else "cpu"
    
    pipe = StableDiffusionImg2ImgPipeline.from_pretrained("runwayml/stable-diffusion-v1-5").to(device)
    
    result = pipe(prompt=prompt, image=image, strength=0.7).images[0]
    output_path = "edited_output.png"
    result.save(output_path)
    return {"message": "Image edited", "output_path": output_path}

@app.post("/generate-script/")
def generate_script_api(
    idea: str = Form(None),
    title: str = Form(None),
    tone: str = Form("Casual"),
    mode: str = Form("Short-form"),
    style: str = Form("Casual"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        if not idea and not title:
            return {"error": "Either idea or title must be provided"}

        search_query = idea if idea else title
        videos = get_video_details(search_query, max_results=5)
        print(f"Fetched trending videos ::: {videos}")

        if not videos:
            return {"error": "No trending YouTube videos found with subtitles"}

        transcripts = []
        youtube_links = []

        for video in videos:
            if len(transcripts) >= 3:  # Stop once we get 3 transcripts
                break
            transcript, err = fetch_transcript(video["link"])
            if transcript:
                transcripts.append(transcript)
                youtube_links.append(video["link"])

        if not transcripts:
            return {"error": "Failed to extract transcripts from videos"}
        
        if len(transcripts) < 3:
            return {"error": "Insufficient transcripts extracted. Try a different idea or title."}

        combined_transcript = "\n".join(transcripts)

        past_scripts = db.query(Script).filter(Script.input_title == search_query).all()
        if past_scripts:
            past_content = "\n".join([ps.generated_script for ps in past_scripts])
            combined_transcript += f"\n\n{past_content}"

        generated_script = generate_script(combined_transcript, mode=mode, tone=tone, style=style)

        formatted_script = format_script_response(generated_script)
        if "I can't help with this request." in formatted_script:
            return {"error": "Script generation failed. Try modifying the input."}

        new_script = Script(
            input_title=search_query,
            video_title=f"Script for {search_query}",
            mode=mode,
            style=style,
            transcript=combined_transcript,
            generated_script=formatted_script,
            youtube_links=", ".join(youtube_links),
            user_id=current_user.id
        )
        db.add(new_script)
        db.commit()
        db.refresh(new_script)

        return {
            "message": "Script generated successfully",
            "script_id": new_script.id,
            "generated_script": generated_script,
            "youtube_links": youtube_links
        }

    except Exception as e:
        return {"error": str(e)}

@app.get("/get-scripts/")
def get_all_scripts(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user)
    ):
    scripts = db.query(Script).all()
    return {"scripts": scripts}

@app.get("/get-script/{script_id}/")
def get_script(
    script_id: int, 
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user)
    ):
    script = db.query(Script).filter(Script.id == script_id).first()
    if not script:
        return {"error": "Script not found"}
    return {"script": script}

# Endpoint for Speech-to-Text (upload an audio file)
@app.post("/speech-to-text/")
def speech_to_text(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user)
    ):
    try:
        file_location = f"temp_{file.filename}"
        with open(file_location, "wb") as f:
            f.write(file.file.read())
        transcription = transcribe_audio(file_location)
        os.remove(file_location)
        return {"transcription": transcription}
    except Exception as e:
        return {"error": str(e)}

# Endpoint for Text-to-Speech (convert provided text to audio)
@app.post("/text-to-speech/")
async def text_to_speech_endpoint(
    text: str = Form(...),
    speech_name: str = Form(...),
    tone_file: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        user_id = current_user.id
        voice_sample_path = None

        # Handle voice tone upload if provided
        if tone_file:
            voice_sample_path = await handle_voice_tone_upload(tone_file, user_id)
        print("voice_sample_path ::", voice_sample_path)
        audio_file_url = generate_speech(text, speech_name, user_id, voice_sample_path)
        if not audio_file_url:
            raise HTTPException(status_code=500, detail="Audio file generation failed")

        return {
            "message": "Speech generated successfully",
            "audio_file_url": audio_file_url
        }

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.post("/remix-script/")
def remix_script_api(
    video_url: str = Form(...),
    tone: str = Form("Casual"),
    mode: str = Form("Short-form"),
    style: str = Form("Casual"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        transcript, err = fetch_transcript(video_url)
        if not transcript:
            return {"error": f"Failed to extract transcript: {err}"}

        remixed_script = generate_script(transcript, mode=mode, tone=tone, style=style)

        formatted_script = format_script_response(remixed_script)
        if "I can't help with this request." in formatted_script:
            return {"error": "Script generation failed. Try modifying the input."}
        print(f"formatted script is this :::{formatted_script}")

        new_remixed_script = RemixedScript(
            video_url=video_url,
            mode=mode,
            style=style,
            transcript=transcript,
            remixed_script=formatted_script,
            user_id=current_user.id
        )
        db.add(new_remixed_script)
        db.commit()
        db.refresh(new_remixed_script)

        return {
            "message": "Remixed script generated successfully",
            "remixed_script_id": new_remixed_script.id,
            "remixed_script": remixed_script
        }

    except Exception as e:
        return {"error": str(e)}