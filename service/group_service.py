import datetime, os
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import UploadFile, HTTPException
from config import UPLOAD_FOLDER
from database.models import Group,User,Document,YouTubeVideo
from service.script_service import (
    fetch_transcript,
    extract_text_from_file,
    analyze_transcript_style,
)
from utils.logging_utils import logger

async def process_group_content(
    project_id: int,
    group_id: Optional[int],
    files: List[UploadFile],
    youtube_links: List[str],
    db: Session,
    current_user: User
) -> dict:
    """
    Processes uploaded files and YouTube links, extracting relevant content and storing it in the database.

    Args:
        project_id (int): The ID of the project the group belongs to.
        group_id (Optional[int]): The ID of the group. If 0, a new group is created.
        files (List[UploadFile]): A list of uploaded files (PDF, DOCX, or TXT).
        youtube_links (List[str]): A list of YouTube video URLs.
        db (Session): The database session to interact with the database.
        current_user (User): The current user who is uploading the files and videos.

    Returns:
        dict: A dictionary with the results of processing the documents and videos. It contains two lists:
            - "documents": A list of dictionaries with filenames and status messages for each processed document.
            - "videos": A list of dictionaries with video URLs, extracted transcript excerpts, and status messages for each processed video.
            - "group": If a new group was created, a message with the group ID.
        
    Raises:
        HTTPException: If the group is not found for the given project.
    """
    results = {"documents": [], "videos": []}

    if group_id == 0:
        try:
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
        except Exception as e:
            logger.error(f"Failed to create new group: {e}")
            raise HTTPException(status_code=500, detail="Failed to create new group.")

    try:
        group = db.query(Group).filter(Group.id == group_id, Group.project_id == project_id).first()
        if not group:
            raise HTTPException(status_code=404, detail="Group not found for this project.")
    except Exception as e:
        logger.error(f"Error fetching group for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Error fetching group.")

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

                print("file_path :: ", file_path)
                with open(file_path, "wb") as f:
                    print("file type : ", type(file))   
                    content = await file.read()
                    f.write(content)

                logger.info(f"Extracting text from file {file.filename}")

                await file.seek(0)
                extracted_text = await extract_text_from_file(file)
            
                logger.info(f"Text extracted from file {file.filename}: {len(extracted_text)} characters")

                cleaned_text = " ".join(extracted_text.split())

                analysis = analyze_transcript_style(extracted_text)
                tone = analysis.get("tone", "Unknown")
                style = analysis.get("style", "Unknown")

                doc_entry = Document(
                    filename=file.filename,
                    content=cleaned_text,
                    tone=tone,
                    style=style,
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
                logger.error(f"Error processing document {file.filename}: {e}")
                results["documents"].append({
                "filename": file.filename,
                "error": f"Failed to process document: {str(e)}"
            })

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
                    style=style,
                    is_deleted=False
                )
                db.add(youtube_entry)
                db.commit()
                db.refresh(youtube_entry)

                results["videos"].append({
                    "video_url": link,
                    "message": "Transcript extracted and link saved",
                    "transcript_excerpt": transcript,
                    "style": style,
                    "tone": tone
                })
            except Exception as e:
                logger.error(f"Error processing YouTube video {link}: {e}")
                results["videos"].append({
                    "video_url": link,
                    "error": str(e)
                })

    return results

def create_group(db: Session, name: str, project_name: str):
    """
    Creates a new group in the database with the given name and project.

    Args:
        db (Session): Database session.
        name (str): Group name.
        project_name (str): Associated project name.

    Returns:
        Group: The created group object.
    """
    try:
        group = Group(name=name, project_id=project_name)
        db.add(group)
        db.commit()
        db.refresh(group)
        return group
    except Exception as e:
        logger.error(f"Error creating group {name} for project {project_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to create group.")


def update_group(db: Session, group_id: int, name: str, user_id: int):
    """
    Updates the name of an existing group if the user is the owner and the group is not deleted.

    Args:
        db (Session): Database session.
        group_id (int): ID of the group to update.
        name (str): New name for the group.
        user_id (int): ID of the user requesting the update.

    Returns:
        Group or None: The updated group object if successful, otherwise None.
    """
    try:
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
    except Exception as e:
        logger.error(f"Error updating group {group_id}: {e}")
        return None

def delete_group(db: Session, group_id: int, user_id: int):
    """
    Soft deletes a group if the user is the owner and the group exists.

    Args:
        db (Session): Database session.
        group_id (int): ID of the group to delete.
        user_id (int): ID of the user requesting the deletion.

    Returns:
        Group or None: The soft-deleted group if successful, otherwise None.
    """
    try:
        group = db.query(Group).filter(
            Group.id == group_id,
            Group.is_deleted == False
        ).first()

        if not group:
            return None

        if group.user_id != user_id:
            return None  

        group.is_deleted = True
        db.commit()
        return group
    except Exception as e:
        logger.error(f"Error soft-deleting group {group_id}: {e}")
        db.rollback()
        return None

def get_user_groups_with_content(user_id: int, db: Session):
    """
    Retrieves all active groups for a user along with associated documents and videos.

    Args:
        user_id (int): ID of the user for whom to fetch groups.
        db (Session): Database session.

    Returns:
        list: A list of groups, each with their associated documents and videos.

    Raises:
        HTTPException: If no groups are found for the user.
    """
    try:
        groups = db.query(Group).filter(
            Group.user_id == user_id,
            Group.is_deleted == False
        ).all()

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
                    {   "document id": doc.id,
                        "filename": doc.filename, "content_snippet": doc.content} for doc in documents
                ],
                "videos": [
                    {
                        "videos id": vid.id,
                        "video_url": vid.url,
                        "transcript_excerpt": vid.transcript,
                        "tone": vid.tone,
                        "style": vid.style
                    }
                    for vid in videos
                ]
            })

        return group_list
    except Exception as e:
        logger.error(f"Error retrieving groups for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving groups.")

def get_user_group_with_content_by_id(group_id: int, user_id: int, db: Session):
    """
    Retrieves a specific group by its ID for a user along with associated documents and videos.

    Args:
        group_id (int): The ID of the group to retrieve.
        user_id (int): The ID of the user to whom the group belongs.
        db (Session): The database session.

    Returns:
        dict: A dictionary containing the group's details, documents, and videos.

    Raises:
        HTTPException: If the group is not found for the user.
    """
    try:
        group = db.query(Group).filter(
            Group.id == group_id,
            Group.user_id == user_id,
            Group.is_deleted == False
        ).first()

        if not group:
            raise HTTPException(status_code=404, detail="Group not found.")

        documents = db.query(Document).filter(Document.group_id == group.id).all()
        videos = db.query(YouTubeVideo).filter(YouTubeVideo.group_id == group.id).all()

        return {
            "group_id": group.id,
            "group_name": group.name,
            "project_id": group.project_id,
            "documents": [
                {
                    "document id": doc.id,
                    "filename": doc.filename,
                    "content_snippet": doc.content
                } for doc in documents
            ],
            "videos": [
                {
                    "videos id": vid.id,
                    "video_url": vid.url,
                    "transcript_excerpt": vid.transcript,
                    "tone": vid.tone,
                    "style": vid.style
                } for vid in videos
            ]
        }
    except Exception as e:
        logger.error(f"Error retrieving group with ID {group_id} for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving group.")
