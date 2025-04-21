from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException,Request
from fastapi.responses import JSONResponse
from typing import List, Optional,Union
import requests
import datetime, os
from database.models import Group, Document,  Project, User,YouTubeVideo
from functionality.current_user import get_current_user
from config import UPLOAD_FOLDER
from sqlalchemy.orm import Session
from database.schemas import GroupCreate, GroupUpdate
from service.group_service import get_user_groups_with_content, update_group, delete_group,process_group_content
from database.db_connection import get_db
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

group_router = APIRouter(prefix="/groups")

# @group_router.post("/create")
# def create_group_api(payload: GroupCreate, db: Session = Depends(get_db)):
#     return create_group(db, payload.name, payload.project_id, payload.document_names, payload.youtube_links)

# @group_router.post("/create-with-content")
# async def knowledge_api(
#     project_id: int = Form(...),  # ✅
#     group_id: Optional[int] = Form(None),
#     files: List[UploadFile] = File(None),
#     youtube_links: List[str] = Form(default=[]),
#     mode: str = Form("Short-form"),
#     db: Session = Depends(get_db),
#     current_user: User = Depends(get_current_user)
# ):
#     results = {"documents": [], "videos": []}

#     # ----------- Handle Group Creation for group_id 0 -----------
#     if group_id == 0:
#         new_group = Group(
#             name=f"Group for {current_user.username}",
#             project_id=project_id,
#             user_id=current_user.id
#         )
#         db.add(new_group)
#         db.commit()
#         db.refresh(new_group)
#         group_id = new_group.id
#         results["group"] = {"message": f"New group created with ID {group_id}"}

#     # ----------- Validate Group Belongs to Project -----------
#     group = db.query(Group).filter(Group.id == group_id, Group.project_id == project_id).first()
    
#     if not group:
#         raise HTTPException(status_code=404, detail="Group not found for this project.")


#     # ----------- Handle Document Uploads -----------
#     if isinstance(files, list) and any(files):
#         for file in files:
#             if not file or not file.filename:
#                 continue

#             if not file.filename.endswith((".pdf", ".docx", ".txt")):
#                 results["documents"].append({
#                     "filename": file.filename,
#                     "error": "Unsupported file type. Only PDF, DOCX, and TXT are allowed."
#                 })
#                 continue

#             try:
#                 timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
#                 filename = f"{timestamp}_{file.filename}"
#                 file_path = os.path.join(UPLOAD_FOLDER, filename)

#                 with open(file_path, "wb") as f:
#                     content = await file.read()
#                     f.write(content)

#                 extracted_text = extract_text_from_file(file_path)
#                 cleaned_text = " ".join(extracted_text.split())

#                 doc_entry = Document(
#                     filename=file.filename,
#                     content=cleaned_text,
#                     group_id=group_id
#                 )
#                 db.add(doc_entry)
#                 db.commit()
#                 db.refresh(doc_entry)

#                 results["documents"].append({
#                     "filename": file.filename,
#                     "message": "Uploaded and extracted successfully"
#                 })
#             except Exception as e:
#                 results["documents"].append({
#                     "filename": file.filename,
#                     "error": f"Failed to process document: {str(e)}"
#                 })

#     # ----------- Handle YouTube Link Transcript Extraction -----------
#     if youtube_links:
#         for link in youtube_links:
#             try:
#                 transcript, err = fetch_transcript(link)
#                 if not transcript:
#                     results["videos"].append({
#                         "video_url": link,
#                         "error": f"Transcript extraction failed: {err}"
#                     })
#                     continue
#                 analysis = analyze_transcript_style(transcript)
#                 tone = analysis.get("tone", "Unknown")
#                 style = analysis.get("style", "Unknown")

#                 youtube_entry = YouTubeVideo(
#                     url=link,
#                     group_id=group_id,
#                     transcript=transcript,
#                     tone=tone,
#                     style=style
#                 )
#                 db.add(youtube_entry)
#                 db.commit()
#                 db.refresh(youtube_entry)

#                 results["videos"].append({
#                     "video_url": link,
#                     "message": "Transcript extracted and link saved",
#                     "transcript_excerpt": transcript[:300],  # optional preview
#                     "style":style,
#                     "tone":tone
#                 })

#             except Exception as e:
#                 results["videos"].append({
#                     "video_url": link,
#                     "error": str(e)
#                 })

#     if not results["documents"] and not results["videos"]:
#         raise HTTPException(status_code=400, detail="No valid documents or YouTube links provided.")

#     return JSONResponse(content=results)



@group_router.post("/create-with-content")
async def knowledge_api(
    project_id: int = Form(...),
    group_id: Optional[int] = Form(None),
    files: List[UploadFile] = File(None),
    youtube_links: List[str] = Form(default=[]),
    mode: str = Form("Short-form"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Call the helper function to process the group content
    results = await process_group_content(
        project_id, group_id, files, youtube_links, db, current_user
    )

    # If no valid documents or YouTube links were processed, return an error
    if not results["documents"] and not results["videos"]:
        raise HTTPException(status_code=400, detail="No valid documents or YouTube links provided.")

    return JSONResponse(content=results)

# @group_router.put("/{group_name}")
# def update_group_api(group_name: str, payload: GroupUpdate, db: Session = Depends(get_db)):
#     return update_group(db, group_name, payload.name)

# @group_router.delete("/{group_name}")
# def delete_group_api(group_name: str, db: Session = Depends(get_db)):
#     return delete_group(db, group_name)


@group_router.put("/{group_id}")
def update_group_api(group_id: int, payload: GroupUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    group = update_group(db, group_id, payload.name, current_user.id)
    if not group:
        raise HTTPException(status_code=403, detail="You are not authorized to update this group")
    return group

@group_router.delete("/{group_id}")
def delete_group_api(group_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    group = delete_group(db, group_id, current_user.id)
    if not group:
        raise HTTPException(status_code=403, detail="You are not authorized to delete this group")
    return {"message": "Group deleted successfully"}

@group_router.get("/user-groups-content")
def get_user_groups_with_content_api(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    content = get_user_groups_with_content(current_user.id, db)
    return {"groups": content}