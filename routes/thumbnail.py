import io
import os
import json
import torch
import shutil
from PIL import Image
from typing import Optional, List
from fastapi import Depends, UploadFile, File, Form, Query, HTTPException, APIRouter, Body
from sqlalchemy.orm import Session
from diffusers import StableDiffusionImg2ImgPipeline
from database.db_connection import get_db
from database.models import Thumbnail, User
from config import GENERATED_THUMBNAILS_PATH
from functionality.current_user import get_current_user
from service.thumbnail_service import (
    store_thumbnails, 
    validate_thumbnail,
    fetch_thumbnails_preview, 
)
from utils.logging_utils import logger

thumbnail_router = APIRouter()

@thumbnail_router.get("/fetch_thumbnails/")
def fetch_thumbnails(
    keyword: str = Query(...),
    user: User = Depends(get_current_user)
    ):
    """
    Fetches thumbnail previews based on a keyword.

    Args:
        keyword (str): Search keyword to fetch related thumbnails.
        user (User): Current user fetching the thumbnails.

    Returns:
        dict: A message and the fetched thumbnail results.
    """
    try:
        results = fetch_thumbnails_preview(keyword)
        logger.info(f"User {user.id} fetched thumbnails for preview with keyword '{keyword}'")
        return {"message": "Fetched thumbnails for preview.", "results": results}
    
    except Exception as e:
        logger.exception(f"Failed to fetch thumbnails for keyword '{keyword}' by user {user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch thumbnails.")

@thumbnail_router.post("/store_selected_thumbnails/")
def store_selected(
    video_ids: List[str] = Body(...),
    keyword: str = Query(...),
    current_user: User = Depends(get_current_user)
):
    """
    Stores selected thumbnails for a given list of video IDs.

    Args:
        video_ids (List[str]): List of video IDs to store thumbnails for.
        keyword (str): Search keyword associated with the thumbnails.
        current_user (User): Current user storing the thumbnails.

    Returns:
        dict: The result of the thumbnail storage process.
    """
    try:
        result = store_thumbnails(video_ids, keyword, current_user)
        logger.info(f"User {current_user.id} stored selected thumbnails with keyword '{keyword}'")
        return result
    except Exception as e:
        logger.exception(f"Failed to store selected thumbnails for user {current_user.id} with keyword '{keyword}': {e}")
        raise HTTPException(status_code=500, detail="Failed to store selected thumbnails.")

@thumbnail_router.get("/search/")
def search_thumbnails(
    keyword: Optional[str] = Query(None),
    text: Optional[str] = Query(None),
    emotion: Optional[str] = Query(None),
    min_faces: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Searches for thumbnails based on user-specific filters.

    Args:
        keyword (str, optional): Keyword associated with the thumbnail.
        text (str, optional): Text detected in the thumbnail.
        emotion (str, optional): Emotion detected in the thumbnail.
        min_faces (int, optional): Minimum number of faces detected in the thumbnail.
        db (Session): Database session.
        user (User): Current authenticated user.

    Returns:
        dict: List of thumbnails matching the search criteria.
    """
    try:
        query = db.query(Thumbnail).filter(Thumbnail.user_id == user.id)

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
            logger.warning(f"No matching thumbnails found for user {user.id} with keyword '{keyword}'")
            raise HTTPException(status_code=404, detail="No matching thumbnails found.")
        
        logger.info(f"User {user.id} retrieved {len(thumbnails)} matching thumbnails.")
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

    except Exception as e:
        logger.exception(f"Failed to search for thumbnails for user {user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to search for thumbnails.")

@thumbnail_router.post("/validate/")
def validate_thumbnail_api(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Validates a thumbnail uploaded by the user.

    Args:
        file (UploadFile): The thumbnail file to be validated.
        db (Session): Database session.
        user (User): Current authenticated user.

    Returns:
        dict: Validation result for the uploaded thumbnail.
    """
    try:
        temp_dir = "temp_uploads"
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, file.filename)

        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        result = validate_thumbnail(temp_path)
        os.remove(temp_path)

        logger.info(f"User {user.id} validated a thumbnail: {file.filename}")
        return result

    except Exception as e:
        logger.exception(f"Failed to validate thumbnail by user {user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to validate thumbnail.")

@thumbnail_router.get("/get_thumbnails/")
def get_my_thumbnails(
    db: Session = Depends(get_db), 
    user: User = Depends(get_current_user)
    ):
    """
    Retrieves all thumbnails saved by the current user.

    Args:
        db (Session): Database session.
        user (User): Current authenticated user.

    Returns:
        list: List of thumbnails associated with the user.
    """
    try:
        thumbnails = db.query(Thumbnail).filter(Thumbnail.user_id == user.id).all()
        logger.info(f"User {user.id} retrieved {len(thumbnails)} thumbnails.")
        return [
            {
                "id": thumb.id,
                "video_id": thumb.video_id,
                "title": thumb.title,
                "url": thumb.url,
                "saved_path": thumb.saved_path,
                "text_detection": thumb.text_detection,
                "face_detection": thumb.face_detection,
                "emotion": thumb.emotion,
                "color_palette": thumb.color_palette,
                "keyword": thumb.keyword,
            }
            for thumb in thumbnails
        ]

    except Exception as e:
        logger.exception(f"Failed to retrieve thumbnails for user {user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve thumbnails.")

@thumbnail_router.post("/generate_thumbnail/")
async def generate_thumbnail(
    prompt: str = Form(...), 
    image: UploadFile = File(...),
    filename: str = Form(None),
    user: User = Depends(get_current_user)
    ):
    """
    Generates a thumbnail using a provided image and prompt with Stable Diffusion.

    Args:
        prompt (str): Text prompt for generating the thumbnail.
        image (UploadFile): Image file to base the generation on.
        filename (str, optional): Desired filename for the output thumbnail (should end with .png).
        user (User): Current authenticated user.

    Returns:
        dict: Message indicating success and path of the generated thumbnail.
    """
    try:
        contents = await image.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB").resize((512, 512))

        device = "cuda" if torch.cuda.is_available() else "cpu"
        pipe = StableDiffusionImg2ImgPipeline.from_pretrained("runwayml/stable-diffusion-v1-5").to(device)
        
        result = pipe(prompt=prompt, image=image, strength=0.7).images[0]

        output_folder = GENERATED_THUMBNAILS_PATH
        if not filename:
            logger.warning(f"User {user.id} failed to generate thumbnail: filename is required.")
            raise HTTPException(status_code=400, detail="Filename is required.")
        
        if not filename.lower().endswith(".png"):
            filename += ".png"

        output_path = os.path.join(output_folder, filename)
        result.save(output_path)

        logger.info(f"User {user.id} generated a thumbnail with prompt '{prompt}' and saved as {filename}.")
        return {
            "message": "Image generated successfully.",
            "output_path": output_path.replace("\\", "/")
        }

    except Exception as e:
        logger.exception(f"Failed to generate thumbnail for user {user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate thumbnail.")