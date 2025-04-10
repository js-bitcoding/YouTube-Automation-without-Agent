import io
import os
import json
import torch
import shutil
from PIL import Image
from typing import Optional
from sqlalchemy.orm import Session
from database.db_connection import get_db
from fastapi.responses import JSONResponse
from database.models import Thumbnail, User
from diffusers import StableDiffusionImg2ImgPipeline
from functionality.current_user import get_current_user
from fastapi import Depends, UploadFile, File, Form, Query, HTTPException, status, APIRouter
from service.thumbnail_service import (
    store_thumbnails, 
    generate_image_from_input, 
    validate_thumbnail
)

thumbnail_router = APIRouter()

@thumbnail_router.get("/store/")
def store_api(
    keyword: str = Query(...),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user)
    ):
    result = store_thumbnails(keyword, user_id)
    return {"message": "Thumbnails stored successfully.", "results": result}

@thumbnail_router.get("/search/")
def search_thumbnails(
    keyword: Optional[str] = Query(None),
    text: Optional[str] = Query(None),
    emotion: Optional[str] = Query(None),
    min_faces: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
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

@thumbnail_router.post("/validate/")
def validate_thumbnail_api(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user)
):
    temp_dir = "temp_uploads"
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, file.filename)

    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    result = validate_thumbnail(temp_path)
    os.remove(temp_path)

    return result

@thumbnail_router.post("/generate-thumbnail/")
async def generate_thumbnail(
    prompt: str = Form(...), 
    image: UploadFile = File(...),
    filename: str = Form(None),
    user_id: int = Depends(get_current_user)
    ):

    contents = await image.read()
    image = Image.open(io.BytesIO(contents)).convert("RGB").resize((512, 512))

    device = "cuda" if torch.cuda.is_available() else "cpu"
    
    pipe = StableDiffusionImg2ImgPipeline.from_pretrained("runwayml/stable-diffusion-v1-5").to(device)
    
    result = pipe(prompt=prompt, image=image, strength=0.7).images[0]

    output_folder = "assets/generated_thumbnails"
    if not filename:
        raise HTTPException(status_code=400, detail="Filename is required.")
    
    if not filename.lower().endswith(".png"):
        filename += ".png"

    output_path = os.path.join(output_folder, filename)
    result.save(output_path)

    return {
        "message": "Image generated successfully.",
        "output_path": output_path.replace("\\", "/")
        }
