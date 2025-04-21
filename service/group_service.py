from sqlalchemy.orm import Session
from database.models import Group,User,Document,YouTubeVideo
from typing import List, Optional,Union
import datetime,os
from config import UPLOAD_FOLDER
from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException,Request
from service.script_service import (
   
    fetch_transcript,
   
    extract_text_from_file,
    
    analyze_transcript_style,
)


async def process_group_content(
    project_id: int,
    group_id: Optional[int],
    files: List[UploadFile],
    youtube_links: List[str],
    db: Session,
    current_user: User
) -> dict:
    results = {"documents": [], "videos": []}

    # ----------- Handle Group Creation for group_id 0 -----------
    if group_id == 0:
        new_group = Group(
            name=f"Group for {current_user.username}",
            project_id=project_id,
            user_id=current_user.id
        )
        db.add(new_group)
        db.commit()
        db.refresh(new_group)
        group_id = new_group.id
        results["group"] = {"message": f"New group created with ID {group_id}"}

    # ----------- Validate Group Belongs to Project -----------
    group = db.query(Group).filter(Group.id == group_id, Group.project_id == project_id).first()
    
    if not group:
        raise HTTPException(status_code=404, detail="Group not found for this project.")

    # ----------- Handle Document Uploads -----------
    if files:
        for file in files:
            if not file or not file.filename:
                continue

            if not file.filename.endswith((".pdf", ".docx", ".txt")):
                results["documents"].append({
                    "filename": file.filename,
                    "error": "Unsupported file type. Only PDF, DOCX, and TXT are allowed."
                })
                continue

            try:
                timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
                filename = f"{timestamp}_{file.filename}"
                file_path = os.path.join(UPLOAD_FOLDER, filename)

                with open(file_path, "wb") as f:
                    content = await file.read()
                    f.write(content)

                extracted_text = extract_text_from_file(file_path)
                cleaned_text = " ".join(extracted_text.split())

                doc_entry = Document(
                    filename=file.filename,
                    content=cleaned_text,
                    group_id=group_id
                )
                db.add(doc_entry)
                db.commit()
                db.refresh(doc_entry)

                results["documents"].append({
                    "filename": file.filename,
                    "message": "Uploaded and extracted successfully"
                })
            except Exception as e:
                results["documents"].append({
                    "filename": file.filename,
                    "error": f"Failed to process document: {str(e)}"
                })

    # ----------- Handle YouTube Link Transcript Extraction -----------
    if youtube_links:
        for link in youtube_links:
            try:
                transcript, err = fetch_transcript(link)
                if not transcript:
                    results["videos"].append({
                        "video_url": link,
                        "error": f"Transcript extraction failed: {err}"
                    })
                    continue
                analysis = analyze_transcript_style(transcript)
                tone = analysis.get("tone", "Unknown")
                style = analysis.get("style", "Unknown")

                youtube_entry = YouTubeVideo(
                    url=link,
                    group_id=group_id,
                    transcript=transcript,
                    tone=tone,
                    style=style
                )
                db.add(youtube_entry)
                db.commit()
                db.refresh(youtube_entry)

                results["videos"].append({
                    "video_url": link,
                    "message": "Transcript extracted and link saved",
                    "transcript_excerpt": transcript[:300],  # optional preview
                    "style": style,
                    "tone": tone
                })

            except Exception as e:
                results["videos"].append({
                    "video_url": link,
                    "error": str(e)
                })

    return results


def create_group(db: Session, name: str, project_name: str, docs: list, links: list):
    group = Group(name=name, project_id=project_name)
    db.add(group)
    db.commit()
    db.refresh(group)
    return group

# def update_group(db: Session, group_name: str, name: str):
#     group = db.query(Group).filter(Group.name == group_name).first()
#     if group:
#         group.name = name or group.name
#         db.commit()
#         db.refresh(group)
#     return group

# def delete_group(db: Session, group_name: str):
#     group = db.query(Group).filter(Group.name == group_name).first()
#     if group:
#         db.delete(group)
#         db.commit()
#     return group

def update_group(db: Session, group_id: int, name: str, user_id: int):
    # Query the group by group_id instead of group_name
    group = db.query(Group).filter(
        Group.id == group_id,
        Group.is_deleted == False
        ).first()
    
    if not group:
        return None  

    if group.user_id != user_id:
        return None 
    group.name = name or group.name
    db.commit()
    db.refresh(group)

    return group

def delete_group(db: Session, group_id: int, user_id: int):
    # Query the group by group_id instead of group_name
    group = db.query(Group).filter(
        Group.id == group_id,
        Group.is_deleted == False
        ).first()

    if not group:
        return None  # Group not found

    if group.user_id != user_id:
        return None  

    try:
        group.is_deleted = True
        db.commit()
        return group
    except Exception as e:
        db.rollback()
        print(f"Error soft-deleting group: {e}")
        return None

def get_user_groups_with_content(user_id: int, db: Session):
    groups = db.query(Group).filter(Group.user_id == user_id).all()

    if not groups:
        raise HTTPException(status_code=404, detail="No groups found for this user.")

    group_list = []
    for group in groups:
        documents = db.query(Document).filter(Document.group_id == group.id).all()
        videos = db.query(YouTubeVideo).filter(YouTubeVideo.group_id == group.id).all()

        group_list.append({
            "group_id": group.id,
            "group_name": group.name,
            "project_id": group.project_id,
            "documents": [
                {"filename": doc.filename, "content_snippet": doc.content[:300]} for doc in documents
            ],
            "videos": [
                {
                    "video_url": vid.url,
                    "transcript_excerpt": vid.transcript[:300],
                    "tone": vid.tone,
                    "style": vid.style
                }
                for vid in videos
            ]
        })

    return group_list