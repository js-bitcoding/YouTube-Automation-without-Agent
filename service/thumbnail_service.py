import os
import cv2
import json
import base64
import requests
import mimetypes
import pytesseract
from fer import FER
from PIL import Image
from io import BytesIO
from typing import List
from mediapipe import solutions
from colorthief import ColorThief
import google.generativeai as genai
from database.models import Thumbnail, User
from database.db_connection import SessionLocal
from config import THUMBNAIL_STORAGE_PATH, GEMINI_API_KEY
from service.youtube_service import fetch_video_thumbnails
from utils.logging_utils import logger

API_KEY = GEMINI_API_KEY
genai.configure(api_key=API_KEY)

MODEL_NAME = "gemini-2.0-flash-exp-image-generation"

os.makedirs(THUMBNAIL_STORAGE_PATH, exist_ok=True)

def detect_faces(image_path: str):
    try:
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Image at {image_path} could not be loaded.")
        face_detector = solutions.face_detection.FaceDetection(min_detection_confidence=0.5)
        results = face_detector.process(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        return len(results.detections) if results.detections else 0
    except Exception as e:
        logger.error(f"Error in detect_faces: {e}")
        return 0

def detect_text(image_path: str):
    try:
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Image at {image_path} could not be loaded.")
        text = pytesseract.image_to_string(img)
        return bool(text.strip())
    except Exception as e:
        logger.error(f"Error in detect_text: {e}")
        return False

def extract_fonts(image_path: str):
    try:
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Image at {image_path} could not be loaded.")
        return pytesseract.image_to_string(img)
    except Exception as e:
        logger.error(f"Error in extract_fonts: {e}")
        return ""

def extract_colors(image_path: str, color_count=3):
    try:
        color_thief = ColorThief(image_path)
        palette = color_thief.get_palette(color_count=color_count, quality=1)
        def rgb_to_hex(rgb):
            return '#%02x%02x%02x' % rgb
        return [rgb_to_hex(color) for color in palette]
    except Exception as e:
        logger.error(f"Error in extract_colors: {e}")
        return []

def encode_image(image_path: str):
    try:
        mime_type, _ = mimetypes.guess_type(image_path)
        if not mime_type:
            mime_type = "image/jpeg"

        with open(image_path, "rb") as img_file:
            return {
                "mime_type": mime_type,
                "data": base64.b64encode(img_file.read()).decode("utf-8")
            }
    except Exception as e:
        logger.error(f"Error in encode_image: {e}")
        return {}

def generate_image_from_input(image_path: str, prompt: str):
    try:
        image_data = encode_image(image_path)
        image_part = {
            "inline_data": {
                "mime_type": image_data["mime_type"],
                "data": image_data["data"]
            }
        }

        model = genai.GenerativeModel(MODEL_NAME)

        response = model.generate_content(
            [
                {
                    "role": "user",
                    "parts": [image_part, {"text": prompt}]
                }
            ]
        )
        logger.info(f"Full Response:, {response}")

        if response and response.candidates:
            for candidate in response.candidates:
                for part in candidate.content.parts:
                    if hasattr(part, "inline_data"):
                        return part.inline_data.data
        logger.info("❌ No image returned in the response.")
        return None
    except Exception as e:
        logger.error(f"Error generating image: {e}")
        return None

def save_thumbnail(video: dict):
    try:
        response = requests.get(video["thumbnail_url"])
        if response.status_code == 200:
            filename = f"{video['video_id']}.jpg"
            filepath = os.path.join(THUMBNAIL_STORAGE_PATH, filename)
            
            with open(filepath, "wb") as file:
                file.write(response.content)
            
            return filepath
        else:
            logger.error(f"Failed to download thumbnail: {video['thumbnail_url']}")
            return None
    except Exception as e:
        logger.error(f"Error in save_thumbnail: {e}")
        return None

def fetch_thumbnails_preview(keyword: str):
    try:
        videos = fetch_video_thumbnails(keyword)
        results = []

        for video in videos:
            validation = validate_thumbnail(video['thumbnail_url'], from_url=True)
            results.append({
                "video_id": video["video_id"],
                "title": video["title"],
                "url": video["thumbnail_url"],
                "text_detection": validation["text_detection"],
                "face_detection": validation["face_detection"],
                "emotions": validation["emotion"],
                "color_palette": validation["color_palette"]
            })
        
        return results
    except Exception as e:
        logger.error(f"Error in fetch_thumbnails_preview: {e}")
        return []

def store_thumbnails(video_ids: List[str], keyword: str, current_user: User):
    try:
        videos = fetch_video_thumbnails(keyword)
        selected_videos = [v for v in videos if v["video_id"] in video_ids]

        if not selected_videos:
            return {"message": "No matching thumbnails found for provided video IDs."}

        db = SessionLocal()
        results = []

        for video in selected_videos:
            filepath = save_thumbnail(video)
            if filepath:
                validation = validate_thumbnail(filepath)

                thumbnail = Thumbnail(
                    keyword=keyword,
                    video_id=video["video_id"],
                    title=video["title"],
                    url=video["thumbnail_url"],
                    saved_path=filepath,
                    text_detection=validation["text_detection"],
                    face_detection=validation["face_detection"],
                    emotion=validation["emotion"],
                    color_palette=json.dumps(validation["color_palette"]),
                    user_id=current_user.id
                )
                db.add(thumbnail)

                results.append({
                    "filename": os.path.basename(filepath),
                    "title": video["title"],
                    "url": video["thumbnail_url"],
                    "text_detection": validation["text_detection"],
                    "face_detection": validation["face_detection"],
                    "emotions": validation["emotion"],
                    "color_palette": validation["color_palette"]
                })

        db.commit()
        db.close()

        return {"message": "Selected thumbnails stored successfully.", "results": results}
    except Exception as e:
        logger.error(f"Error in store_thumbnails: {e}")
        return {"message": f"An error occurred while storing thumbnails: {str(e)}"}

def clarity_score(image_path: str):
    try:
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Image at {image_path} could not be loaded.")
        return cv2.Laplacian(image, cv2.CV_64F).var()
    except Exception as e:
        logger.error(f"Error in clarity_score: {e}")
        return 0

def predict_ctr_score(image_path: str):
    try:
        clarity = clarity_score(image_path)
        text_presence = detect_text(image_path)
        face_presence = detect_faces(image_path)
        ctr = 0.5 + (0.1 if text_presence else -0.1) + (0.2 if face_presence else -0.2) + (0.2 if clarity > 100 else -0.2)
        return max(0, min(1, ctr))
    except Exception as e:
        logger.error(f"Error in predict_ctr_score: {e}")
        return 0

def detect_emotions(image_path):
    try:
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Image at {image_path} could not be loaded.")

        detector = FER(mtcnn=True)

        results = detector.detect_emotions(img)
        
        if results:
            emotions = results[0]["emotions"]
            dominant_emotion = max(emotions, key=emotions.get)
            return dominant_emotion
        else:
            return None
    except Exception as e:
        logger.error(f"Error in detect_emotions: {e}")
        return None

def validate_thumbnail(image_path: str, from_url=False):
    try:
        if from_url:
            response = requests.get(image_path)
            if response.status_code != 200:
                raise ValueError(f"Failed to fetch image from URL: {image_path}")
            image = Image.open(BytesIO(response.content)).convert("RGB")
            temp_path = "temp_thumbnail.jpg"
            image.save(temp_path)
            image_path = temp_path
        else:
            temp_path = None

        text_exists = detect_text(image_path)
        text_value = extract_fonts(image_path)
        faces = detect_faces(image_path)
        emotion = detect_emotions(image_path) if faces > 0 else None
        colors = extract_colors(image_path)
        
        return {
            "clarity": clarity_score(image_path),
            "predicted_ctr": predict_ctr_score(image_path),
            "text_detection": {
                "exists": text_exists,
                "value": text_value.strip() if text_exists else ""
            },
            "face_detection": faces,
            "emotion": emotion,
            "color_palette": colors
        }
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
