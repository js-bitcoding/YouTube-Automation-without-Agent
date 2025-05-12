import datetime, os
from config import UPLOAD_FOLDER
from typing import List, Optional
from sqlalchemy.orm import Session
from chromadb import PersistentClient
from utils.logging_utils import logger
from fastapi import UploadFile, HTTPException
from database.models import Group,User,Document,YouTubeVideo
from service.script_service import (
    fetch_transcript,
    extract_text_from_file,
    analyze_transcript_style,
)



chroma_client = PersistentClient(path="./chroma_db") 

async def process_group_content(
    group_id: Optional[int],
    files: List[UploadFile],
    youtube_links: List[str],
    db: Session,
    current_user: User
) -> dict:
    group = None
    project_id = None

    results = {"documents": [], "youtube_transcripts": [], "document_texts": [], "videos": []}

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
    else:
        group = db.query(Group).filter(Group.id == group_id).first()
        if not group or group.user_id != current_user.id:
            logger.error(f"Group with ID {group_id} not found for user {current_user.id}.")
            raise HTTPException(status_code=404, detail="Group not found.")
        
        project_id = group.project_id
        
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

                with open(file_path, "wb") as f:
                    content = await file.read()
                    f.write(content)

                logger.info(f"Extracting text from file {file.filename}")

                await file.seek(0)
                extracted_text = await extract_text_from_file(file)
                logger.info(f"Text extracted from file {file.filename}: {len(extracted_text)} characters")

                cleaned_text = " ".join(extracted_text.split())

                try:
                    analysis = analyze_transcript_style(cleaned_text)
                    tone = analysis.get("tone")
                    style = analysis.get("style")

                    if not tone or not tone.strip():
                        tone = "Unknown"
                    if not style or not style.strip():
                        style = "Unknown"

                except Exception as e:
                    logger.error(f"Error analyzing transcript style: {e}")
                    tone, style = "Unknown", "Unknown"

                doc_entry = Document(
                    filename=file.filename,
                    tone=tone,
                    style=style,
                    group_id=group_id
                )
                db.add(doc_entry)
                db.commit()
                db.refresh(doc_entry)

                results["document_texts"].append(cleaned_text)
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
            
                try:
                    analysis = analyze_transcript_style(transcript)
                    tone = analysis.get("tone")
                    style = analysis.get("style")

                    if not tone or not tone.strip():
                        tone = "Unknown"
                    if not style or not style.strip():
                        style = "Unknown"

                except Exception as e:
                    logger.error(f"Error analyzing transcript style: {e}")
                    tone, style = "Unknown", "Unknown"


                youtube_entry = YouTubeVideo(
                url=link,
                group_id=group_id,
                tone=tone,
                style=style,
                is_deleted=False
                )
                logger.debug(f"Saving YouTube video with Tone: {tone}, Style: {style}")  # Log the values being saved
                db.add(youtube_entry)
                db.commit()
                db.refresh(youtube_entry)
                logger.info(f"Saved video entry: {youtube_entry.id} | Tone: {youtube_entry.tone} | Style: {youtube_entry.style}")

                results["youtube_transcripts"].append(transcript)
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

async def update_groups_content(
    group_id: Optional[int],
    files: List[UploadFile],
    youtube_links: List[str],
    db: Session,
    current_user: User,
    document_ids: Optional[List[int]] = None,
    youtube_ids: Optional[List[int]] = None
) -> dict:
    results = {
        "documents": [],
        "youtube_transcripts": [],
        "document_texts": [],
        "videos": [],
        "doc_objects": [],  
        "yt_objects": []    
    }

    group = db.query(Group).filter(Group.id == group_id).first()
    if not group or group.user_id != current_user.id:
        logger.error(f"Group with ID {group_id} not found for user {current_user.id}.")
        raise HTTPException(status_code=404, detail="Group not found.")

    project_id = group.project_id

    for idx, file in enumerate(files or []):
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

            await file.seek(0)
            extracted_text = await extract_text_from_file(file)
            cleaned_text = " ".join(extracted_text.split())

            try:
                analysis = analyze_transcript_style(cleaned_text)
                tone = analysis.get("tone")
                style = analysis.get("style")

                if not tone or not tone.strip():
                    tone = "Unknown"
                if not style or not style.strip():
                    style = "Unknown"

            except Exception as e:
                    logger.error(f"Error analyzing transcript style: {e}")
                    tone, style = "Unknown", "Unknown"

            document_id = document_ids[idx] if document_ids and idx < len(document_ids) else None

            if document_id:
                doc_entry = db.query(Document).filter(
                    Document.id == document_id, Document.group_id == group_id
                ).first()
                if not doc_entry:
                    raise HTTPException(status_code=404, detail=f"Document ID {document_id} not found.")
                doc_entry.filename = file.filename
                doc_entry.tone = tone
                doc_entry.style = style
            else:
                doc_entry = Document(
                    filename=file.filename,
                    tone=tone,
                    style=style,
                    group_id=group_id
                )
                db.add(doc_entry)

            db.commit()
            db.refresh(doc_entry)

            results["doc_objects"].append({
                "id": doc_entry.id,
                "filename": doc_entry.filename,
                "tone": doc_entry.tone,
                "style": doc_entry.style
            })

            results["document_texts"].append(cleaned_text)
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

    for idx, link in enumerate(youtube_links or []):
        try:
            transcript, err = fetch_transcript(link)
            if not transcript:
                results["videos"].append({
                    "video_url": link,
                    "error": f"Transcript extraction failed: {err}"
                })
                continue

            try:
                analysis = analyze_transcript_style(transcript)
                tone = analysis.get("tone")
                style = analysis.get("style")

                if not tone or not tone.strip():
                    tone = "Unknown"
                if not style or not style.strip():
                    style = "Unknown"

            except Exception as e:
                    logger.error(f"Error analyzing transcript style: {e}")
                    tone, style = "Unknown", "Unknown"

            youtube_id = youtube_ids[idx] if youtube_ids and idx < len(youtube_ids) else None

            if youtube_id:
                yt_entry = db.query(YouTubeVideo).filter(
                    YouTubeVideo.id == youtube_id, YouTubeVideo.group_id == group_id
                ).first()
                if not yt_entry:
                    raise HTTPException(status_code=404, detail=f"YouTube ID {youtube_id} not found.")
                yt_entry.url = link
                yt_entry.tone = tone
                yt_entry.style = style
            else:
                yt_entry = YouTubeVideo(
                    url=link,
                    group_id=group_id,
                    tone=tone,
                    style=style,
                    is_deleted=False
                )
                db.add(yt_entry)

            db.commit()
            db.refresh(yt_entry)

            results["yt_objects"].append({
                "id": yt_entry.id,
                "url": yt_entry.url,
                "tone": yt_entry.tone,
                "style": yt_entry.style
            })

            results["youtube_transcripts"].append(transcript)
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

def fetch_all_chroma_documents(project_id: int, group_id: int) -> dict:
    """
    Fetches all non-deleted document and transcript chunks for a group from ChromaDB.
    Returns a dictionary with 'documents' and 'youtube_transcripts'.
    """
    collection_name = f"project_{project_id}_group_{group_id}"

    try:
        collection = chroma_client.get_collection(name=collection_name)
        
        if collection is None:
            logger.warning(f"Collection '{collection_name}' does not exist. Please ensure the collection is created properly.")
            return {"documents": [], "youtube_transcripts": []}

        items = collection.get(include=["documents", "metadatas"])

        if not isinstance(items, dict) or "documents" not in items or "metadatas" not in items:
            logger.warning(f"Unexpected structure in ChromaDB collection '{collection_name}': {items}")
            return {"documents": [], "youtube_transcripts": []}

        documents = items["documents"]
        metadatas = items["metadatas"]

       
        logger.debug(f"Found {len(documents)} documents and {len(metadatas)} metadata entries in collection '{collection_name}'.")

        documents_data = []
        youtube_transcripts_data = []

        for doc, meta in zip(documents, metadatas):
            if not meta.get("is_deleted", False):
            
                content = doc.strip() if isinstance(doc, str) else None
                if content:
                    if meta.get("type") == "document":
                        documents_data.append({
                            "content": content,
                            "type": "document",
                            "document_id": meta.get("document_id")
                        })
                    elif meta.get("type") == "youtube_transcript":
                        youtube_transcripts_data.append({
                            "content": content,
                            "type": "youtube_transcript",
                            "youtube_id": meta.get("youtube_id")
                        })

        logger.debug(f"Found {len(youtube_transcripts_data)} youtube transcripts.")

        return {"documents": documents_data, "youtube_transcripts": youtube_transcripts_data}

    except Exception as e:
        logger.warning(f"Could not fetch documents from ChromaDB collection '{collection_name}': {e}")
        return {"documents": [], "youtube_transcripts": []}

def get_user_groups_with_content(user_id: int, db: Session):
    """
    Retrieves all groups and their associated content for the current user.

    Args: db (Session): SQLAlchemy DB session. current_user (User): Authenticated user.

    Returns: dict: A list of groups with associated content.

    Raises: HTTPException: If no groups are found for the current user.
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
          
            chroma_docs_response = fetch_all_chroma_documents(group.project_id, group.id)
            logger.debug(f"ChromaDB response for group {group.id}: {chroma_docs_response}")

            chroma_docs = chroma_docs_response.get("documents", [])
            youtube_transcripts = chroma_docs_response.get("youtube_transcripts", [])

            group_content = {
                "group_id": group.id,
                "group_name": group.name,
                "project_id": group.project_id,
                "documents": [],
                "youtube_links": []
            }

      
            documents = db.query(Document).filter(
                Document.group_id == group.id,
                Document.is_deleted == False
            ).all()

            for doc in documents:
             
                matching_chunks = [
                    item for item in chroma_docs
                    if isinstance(item, dict)
                    and item.get("type") == "document"
                    and item.get("document_id") == doc.id
                ]

                document_content = {
                    "filename": doc.filename,
                    "tone": doc.tone or "Unknown",
                    "style": doc.style or "Unknown",
                    "content": ""
                }

                seen_content = set()  
                aggregated_content = []  

                for chunk in matching_chunks:
                    chunk_content = chunk["content"]
                   
                    if chunk_content not in seen_content:
                        aggregated_content.append(chunk_content)
                        seen_content.add(chunk_content)

                document_content["content"] = "\n".join(aggregated_content)

                group_content["documents"].append(document_content)

          
            youtube_links = db.query(YouTubeVideo).filter(
                YouTubeVideo.group_id == group.id,
                YouTubeVideo.is_deleted == False
            ).all()

            for youtube in youtube_links:
             
                matching_transcripts = [
                    item for item in youtube_transcripts
                    if isinstance(item, dict)
                    and item.get("type") == "youtube_transcript"
                    and item.get("youtube_id") == youtube.id  
                ]

                youtube_content = {
                    "url": youtube.url,
                    "tone": youtube.tone or "Unknown",
                    "style": youtube.style or "Unknown",
                    "transcript": "No transcript available"
                }

                seen_transcripts = set() 
                aggregated_transcripts = []  

                for transcript in matching_transcripts:
                    transcript_content = transcript.get("content")
                   
                    if transcript_content not in seen_transcripts:
                        aggregated_transcripts.append(transcript_content)
                        seen_transcripts.add(transcript_content)

                
                if aggregated_transcripts:
                    youtube_content["transcript"] = "\n".join(aggregated_transcripts)
                else:
                    youtube_content["transcript"] = "No transcript available"

                group_content["youtube_links"].append(youtube_content)

            group_list.append(group_content)

        return group_list
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error occurred while fetching groups for user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="An error occurred while fetching groups and content.")

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
