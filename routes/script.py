import os
import datetime
from config import UPLOAD_FOLDER
from sqlalchemy.orm import Session
from database.db_connection import get_db
from fastapi.responses import JSONResponse
from functionality.current_user import get_current_user
from database.models import RemixedScript, Script, User, Document
from fastapi import Depends, UploadFile, File, Form, HTTPException, status, APIRouter, Body
from service.script_service import (
    generate_script, 
    # generate_speech,
    fetch_transcript, 
    transcribe_audio, 
    get_video_details, 
    extract_text_from_file,
    format_script_response,
    handle_voice_tone_upload,
    analyze_transcript_style,
)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

script_router = APIRouter()

@script_router.post("/upload-document/")
async def upload_document(
    file: UploadFile = File(...),
    group: str = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
    ):
    if not file.filename.endswith((".pdf", ".docx", ".txt")):
        raise HTTPException(status_code=400, detail="Only PDF, DOCX, and TXT files are allowed.")
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    filename = f"{timestamp}_{file.filename}"
    file_path = os.path.join(UPLOAD_FOLDER, filename)

    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    extracted_text = extract_text_from_file(file_path)
    cleaned_text = " ".join(extracted_text.split())

    doc_entry = Document(filename=file.filename, content=cleaned_text)
    db.add(doc_entry)
    db.commit()
    db.refresh(doc_entry)

    return JSONResponse(content={
        "filename": file.filename, 
        "message": "Upload & text extraction successful"
        })

# @script_router.post("/generate-script/")
# def generate_script_api(
#     idea: str = Form(None),
#     title: str = Form(None),
#     tone: str = Form("Casual"),
#     mode: str = Form("Short-form"),
#     style: str = Form("Casual"),
#     db: Session = Depends(get_db),
#     current_user: User = Depends(get_current_user)
# ):
#     try:
#         if not idea and not title:
#             return {"error": "Either idea or title must be provided"}

#         search_query = idea if idea else title
#         videos = get_video_details(search_query, max_results=5)
#         print(f"Fetched trending videos ::: {videos}")

#         if not videos:
#             return {"error": "No trending YouTube videos found with subtitles"}

#         transcripts = []
#         youtube_links = []

#         for video in videos:
#             if len(transcripts) >= 3:  # Stop once we get 3 transcripts
#                 break
#             transcript, err = fetch_transcript(video["link"])
#             if transcript:
#                 transcripts.append(transcript)
#                 youtube_links.append(video["link"])

#         if not transcripts:
#             return {"error": "Failed to extract transcripts from videos"}
        
#         if len(transcripts) < 3:
#             return {"error": "Insufficient transcripts extracted. Try a different idea or title."}

#         combined_transcript = "\n".join(transcripts)

#         past_scripts = db.query(Script).filter(Script.input_title == search_query).all()
#         if past_scripts:
#             past_content = "\n".join([ps.generated_script for ps in past_scripts])
#             combined_transcript += f"\n\n{past_content}"

#         generated_script = generate_script(combined_transcript, mode=mode, tone=tone, style=style)

#         formatted_script = format_script_response(generated_script)
#         if "I can't help with this request." in formatted_script:
#             return {"error": "Script generation failed. Try modifying the input."}

#         new_script = Script(
#             input_title=search_query,
#             video_title=f"Script for {search_query}",
#             mode=mode,
#             style=style,
#             transcript=combined_transcript,
#             generated_script=formatted_script,
#             youtube_links=", ".join(youtube_links),
#             user_id=current_user.id
#         )
#         db.add(new_script)
#         db.commit()
#         db.refresh(new_script)

#         return {
#             "message": "Script generated successfully",
#             "script_id": new_script.id,
#             "generated_script": generated_script,
#             "youtube_links": youtube_links
#         }

#     except Exception as e:
#         return {"error": str(e)}

@script_router.post("/generate-script/")
def generate_script_api(
    idea: str = Form(None),
    title: str = Form(None),
    document_name: str = Form(...),
    mode: str = Form("Short-form"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        if not idea and not title:
            return {"error": "Either idea or title must be provided"}

        search_query = idea or title
        videos = get_video_details(search_query, max_results=5)

        transcripts = []
        youtube_links = []
        for video in videos:
            if len(transcripts) >= 3:
                break
            transcript, err = fetch_transcript(video["link"])
            if transcript:
                transcripts.append(transcript)
                youtube_links.append(video["link"])

        if len(transcripts) < 1:
            return {"error": "Could not extract enough transcripts for analysis."}

        combined_transcript = "\n".join(transcripts[:4])
        style, tone = analyze_transcript_style(combined_transcript)

        document = db.query(Document).filter(Document.filename == document_name).first()
        if not document:
            return {"error": "Document not found"}

        generated_script = generate_script(
                            document_content=document.content,
                            style=style,
                            tone=tone,
                            mode=mode
                        )
        formatted_script = format_script_response(generated_script)

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
            "style": style,
            "tone": tone,
            "generated_script": formatted_script,
            "youtube_links": youtube_links
        }

    except Exception as e:
        return {"error": str(e)}

@script_router.get("/get-scripts/")
def get_all_scripts(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user)
    ):
    scripts = db.query(Script).all()
    return {"scripts": scripts}

@script_router.get("/get-script/{script_id}/")
def get_script(
    script_id: int, 
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user)
    ):
    script = db.query(Script).filter(Script.id == script_id).first()
    if not script:
        return {"error": "Script not found"}
    return {"script": script}

@script_router.post("/speech-to-text/")
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

# @script_router.post("/text-to-speech/")
# async def text_to_speech_endpoint(
#     text: str = Form(...),
#     speech_name: str = Form(...),
#     tone_file: UploadFile = File(None),
#     db: Session = Depends(get_db),
#     current_user: User = Depends(get_current_user)
# ):
#     try:
#         user_id = current_user.id
#         voice_sample_path = None

#         if tone_file:
#             voice_sample_path = await handle_voice_tone_upload(tone_file, user_id)
#         print("voice_sample_path ::", voice_sample_path)
#         audio_file_url = generate_speech(text, speech_name, user_id, voice_sample_path)
#         if not audio_file_url:
#             raise HTTPException(status_code=500, detail="Audio file generation failed")

#         return {
#             "message": "Speech generated successfully",
#             "audio_file_url": audio_file_url
#         }

#     except HTTPException as http_exc:
#         raise http_exc
#     except Exception as e:
#         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@script_router.post("/remix-script/")
def remix_script_api(
    video_url: str = Form(...),
    mode: str = Form("Short-form"),
    document_name: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        transcript, err = fetch_transcript(video_url)
        if not transcript:
            return {"error": f"Failed to extract transcript: {err}"}
        
        style, tone = analyze_transcript_style(transcript)
        
        document = db.query(Document).filter(Document.filename == document_name).first()
        if not document:
            return {"error": "Document not found in database."}

        remixed_script = generate_script(
            document_content=document.content,
            mode=mode,
            style=style,
            tone=tone
            )

        formatted_script = format_script_response(remixed_script)
        if "I can't help with this request." in formatted_script:
            return {"error": "Script generation failed. Try modifying the input."}
        print(f"formatted script is this :::{formatted_script}")

        new_remixed_script = RemixedScript(
            video_url=video_url,
            mode=mode,
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