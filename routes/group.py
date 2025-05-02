import datetime
from typing import List
from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from functionality.current_user import get_current_user
from service.group_service import (
    get_user_groups_with_content, 
    update_group, 
    delete_group, 
    process_group_content, 
    get_user_group_with_content_by_id
)
from service.chat_ai_agent_service import initialize_chroma_store
from database.db_connection import get_db
from database.models import Group, Document,  Project, User,YouTubeVideo
from utils.logging_utils import logger

group_router = APIRouter(prefix="/groups")

@group_router.post("/create_empty/")
async def create_empty_group(
    project_id: str = Query(...),
    name: str = Form("Untitled Group"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Creates an empty group for a project, associated with the current user.

    Args:
        project_id (int): ID of the project the group is associated with.
        name (str): Name of the new group (defaults to "Untitled Group").
        db (Session): SQLAlchemy DB session.
        current_user (User): Authenticated user.

    Returns:
        dict: Confirmation message and details of the newly created group.
    """
    try:
        if project_id.strip().lower() == "string" or not project_id.strip():
            raise HTTPException(status_code=400, detail="❌ project_id cannot be empty or 'string'.")

        try:
            project_id = int(project_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="❌ project_id must be a valid integer.")

        if name.strip().lower() == "string" or not name.strip():
            raise HTTPException(status_code=400, detail="❌ Group name cannot be empty.")

        logger.info(f"Creating empty group for project ID {project_id} by user {current_user.id}")

        project = db.query(Project).filter(Project.id == project_id, Project.is_deleted == False).first()
        if not project:
            logger.warning(f"Project with ID {project_id} not found for user {current_user.id}")
            raise HTTPException(status_code=400, detail="Project not found.")

        new_group = Group(
            name=name,
            user_id=current_user.id,
            project_id=project_id,
            created_time=datetime.datetime.now()
        )

        db.add(new_group)
        db.commit()
        db.refresh(new_group)

        logger.info(f"Group {new_group.id} created successfully")
        return JSONResponse(content={
            "message": "Empty group created successfully.",
            "group_id": new_group.id,
            "name": new_group.name,
            "created_time": new_group.created_time.isoformat()
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error while creating group for project ID {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error while creating group for project ID {project_id}: {e}")

@group_router.put("/{group_id}/")
def update_group_api(
    group_id: int, 
    group_name: str = Query(...), 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
    ):
    """
    Updates a group's name for the specified group ID.

    Args:
        group_id (str): ID of the group to update (as string to allow validation).
        name (str): New name for the group.
        db (Session): SQLAlchemy DB session.
        current_user (User): Authenticated user.

    Returns:
        Group: The updated group details.

    Raises:
        HTTPException: If the user is unauthorized or input is invalid.
    """
    try:
        if group_name.strip().lower() == "string" or not group_name.strip():
            raise HTTPException(status_code=400, detail="❌ Group name cannot be empty.")

        logger.info(f"User {current_user.id} is updating group {group_id} with name '{group_name}'")

        group = update_group(db, group_id, group_name.strip(), current_user.id)
        if not group:
            logger.warning(f"Unauthorized update attempt for group {group_id} by user {current_user.id}")
            raise HTTPException(status_code=403, detail="You are not authorized to update this group")

        logger.info(f"Group {group_id} updated successfully by user {current_user.id}")
        return group

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error while updating group {group_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error while updating group {group_id}: {e}")


@group_router.put("/update-content")
async def update_group_content(
    project_id: int,
    group_id: int,
    files: List[UploadFile] = File(None),
    youtube_links: List[str] = Form(default=[]),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> dict:
    """
    Process uploaded documents and YouTube links for a group and store them in vector DB.

    Args:
        project_id (int): ID of the project.
        group_id (int): ID of the group.
        files (List[UploadFile]): Uploaded files.
        youtube_links (List[str]): Provided YouTube links.
        db (Session): SQLAlchemy DB session.
        current_user (User): Authenticated user.

    Returns:
        dict: Contains the list of documents and videos added to the group.
    """
    try:
        logger.info(f"Updating content for group {group_id} under project {project_id} by user {current_user.id}")

        project = db.query(Project).filter(
            Project.id == project_id,
            Project.user_id == current_user.id,
            Project.is_deleted == False
        ).first()
        if not project:
            logger.error(f"Project {project_id} not found for user {current_user.id}")
            raise HTTPException(status_code=400, detail="Project not found.")

        group = db.query(Group).filter(
            Group.id == group_id,
            Group.project_id == project_id,
            Group.is_deleted == False
        ).first()
        if not group:
            logger.warning(f"Group {group_id} not found under project {project_id}")
            raise HTTPException(status_code=404, detail="Group not found.")

        if files is None:
            files = []

        valid_links = [link.strip() for link in youtube_links if link.strip()]
        valid_files = [file for file in files if file.filename and file.content_type.startswith("application/")]

        if not valid_files and not valid_links:
            raise HTTPException(status_code=400, detail="❌ Please provide at least one document or YouTube link.")

        results = await process_group_content(
            project_id=project_id,
            group_id=group_id,
            files=valid_files,
            youtube_links=valid_links,
            db=db,
            current_user=current_user
        )

        if not results.get("documents") and not results.get("videos"):
            logger.warning("Process returned no documents or videos")
            raise HTTPException(status_code=400, detail="No valid documents or YouTube links processed.")

        saved_documents = db.query(Document).filter(Document.group_id == group_id).all()
        document_texts = [doc.content for doc in saved_documents if doc.content]

        saved_videos = db.query(YouTubeVideo).filter(YouTubeVideo.group_id == group_id).all()
        youtube_transcripts = [video.transcript for video in saved_videos if video.transcript]
        
        mixed_content = document_texts + youtube_transcripts

        if not mixed_content:
            logger.warning("No content found to embed into ChromaDB.")
            raise HTTPException(status_code=400, detail="❌ No content available for ChromaDB storage.")

        group_data = {
            "group_id": group.id,
            "formatted": f"Formatted content for the group {group_id} ",
            "documents": mixed_content
        }

        collection_name = f"project_{project_id}_group_{group_id}"

        try:
            vectorstore, all_chunks, collection_id, embedding = initialize_chroma_store(group_data, collection_name)
            logger.info(f"✅ Chroma Collection ID: {collection_id}")
            logger.info(f"✅ Chroma Embedding is : {embedding}")
        except Exception as e:
            logger.error(f"🚨 Error initializing Chroma store: {str(e)}")
            raise HTTPException(status_code=500, detail="Error initializing Chroma store")

        return JSONResponse(content=results)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error updating content for group {group_id} under project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"You cannot update this group content {e}")
    
@group_router.delete("/delete-content")
async def delete_group_content(
    project_id: int = Query(...),
    group_id: int = Query(...),
    document_ids: List[int] = Query(default=[]),
    youtube_video_ids: List[int] = Query(default=[]),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Deletes specified documents and YouTube videos from a group under a project.

    Args:
        project_id (int): ID of the project the group belongs to.
        group_id (int): ID of the group from which content is being deleted.
        document_ids (List[int]): List of document IDs to delete.
        youtube_video_ids (List[int]): List of YouTube video IDs to delete.
        db (Session): SQLAlchemy DB session.
        current_user (User): Authenticated user.

    Returns:
        dict: Contains lists of deleted document IDs, deleted video IDs, and any errors encountered.

    Raises:
        HTTPException: If project or group is not found, or if no valid content IDs are provided.
    """
    logger.info(f"Deleting content from group {group_id} by user {current_user.id}")
    results = {"documents_deleted": [], "videos_deleted": [], "errors": []}

    try:
        project = db.query(Project).filter(
            Project.id == project_id, 
            Project.user_id == current_user.id,
            Project.is_deleted == False
        ).first()

        if not project:
            logger.error(f"Project {project_id} not found or has been deleted for user {current_user.id}")
            raise HTTPException(status_code=400, detail="Project not found or has been deleted.")

        group = db.query(Group).filter(
            Group.id == group_id,
            Group.project_id == project_id,
            Group.is_deleted == False
        ).first()

        if not group:
            logger.warning(f"Group {group_id} not found during delete-content")
            raise HTTPException(status_code=404, detail="Group not found.")

        if document_ids:
            documents = db.query(Document).filter(
                Document.id.in_(document_ids),
                Document.group_id == group_id,
                Document.is_deleted == False
            ).all()
            for doc in documents:
                try:
                    doc.is_deleted = True
                    results["documents_deleted"].append(doc.id)
                except Exception as e:
                    logger.exception(f"Error deleting document ID {doc.id}: {e}")
                    results["errors"].append(f"Document ID {doc.id}: {str(e)}")
            db.commit()

        if youtube_video_ids:
            videos = db.query(YouTubeVideo).filter(
                YouTubeVideo.id.in_(youtube_video_ids),
                YouTubeVideo.group_id == group_id,
                YouTubeVideo.is_deleted == False
            ).all()
            for vid in videos:
                try:
                    vid.is_deleted = True
                    results["videos_deleted"].append(vid.id)
                except Exception as e:
                    logger.exception(f"Error deleting video ID {vid.id}: {e}")
                    results["errors"].append(f"Video ID {vid.id}: {str(e)}")
            db.commit()

        if not results["documents_deleted"] and not results["videos_deleted"]:
            logger.warning("No valid document or video IDs found for deletion")
            raise HTTPException(status_code=400, detail="No valid document or video IDs provided.")

        logger.info(f"Deleted content result for group {group_id}: {results}")
        return JSONResponse(content=results)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error during delete-content: {e}")
        raise HTTPException(status_code=500, detail="Failed during content deletion.")

@group_router.delete("/{group_id}/")
def delete_group_api(group_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Deletes a group after validating user permissions.

    Args:
        group_id (int): ID of the group to delete.
        db (Session): SQLAlchemy DB session.
        current_user (User): Authenticated user.

    Returns:
        dict: Confirmation message indicating successful deletion.

    Raises:
        HTTPException: If the group is not found, or the user is unauthorized.
    """
    logger.info(f"User {current_user.id} requesting delete for group {group_id}")

    try:
        group = delete_group(db, group_id, current_user.id)
        if not group:
            logger.warning(f"Group {group_id} not found or unauthorized deletion attempt by user {current_user.id}")
            raise HTTPException(status_code=403, detail="Group not found or you are not authorized to delete it.")

        logger.info(f"Group {group_id} deleted successfully by user {current_user.id}")
        return {"message": "✅ Group deleted successfully."}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error deleting group {group_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed while deleting the group.")

@group_router.get("/")
def get_user_groups_with_content_api(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves all groups and their associated content for the current user.

    Args:
        db (Session): SQLAlchemy DB session.
        current_user (User): Authenticated user.

    Returns:
        dict: A list of groups with associated content.

    Raises:
        HTTPException: If no groups are found for the current user.
    """
    logger.info(f"User {current_user.id} is requesting all groups and their content.")

    try:
        content = get_user_groups_with_content(current_user.id, db)

        if not content:
            logger.info(f"No groups found for user {current_user.id}.")
            raise HTTPException(status_code=404, detail="No groups found for the current user.")

        logger.info(f"Successfully fetched {len(content)} groups with content for user {current_user.id}.")
        return {"groups": content}

    except Exception as e:
        logger.exception(f"Error occurred while fetching groups for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail="An error occurred while fetching groups and content.")

@group_router.get("/{group_id}/")
def get_user_group_with_content_api(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves the content of a specific group for the current user.

    Args:
        group_id (int): The ID of the group to retrieve.
        db (Session): SQLAlchemy DB session.
        current_user (User): Authenticated user.

    Returns:
        dict: The group with its associated content.

    Raises:
        HTTPException: If the group is not found or the user is not authorized to access it.
    """
    logger.info(f"User {current_user.id} is requesting content for group {group_id}.")

    try:
        content = get_user_group_with_content_by_id(group_id, current_user.id, db)

        if not content:
            logger.warning(f"Group {group_id} not found for user {current_user.id} or unauthorized access.")
            raise HTTPException(status_code=404, detail="Group not found or unauthorized access.")

        logger.info(f"Successfully retrieved content for group {group_id} for user {current_user.id}.")
        return {"group": content}

    except Exception as e:
        logger.exception(f"Error occurred while fetching content for group {group_id} by user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail="An error occurred while retrieving the group content.")
