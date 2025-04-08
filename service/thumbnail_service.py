import os
import cv2
import json
import base64
import requests
import mimetypes
import pytesseract
from fer import FER
from fastapi import Depends
from database.models import User
from mediapipe import solutions
from config import GEMINI_API_KEY
from colorthief import ColorThief
import google.generativeai as genai
from database.models import Thumbnail
from config import THUMBNAIL_STORAGE_PATH
from database.db_connection import SessionLocal
from functionality.current_user import get_current_user
from service.youtube_service import fetch_video_thumbnails

API_KEY = GEMINI_API_KEY
genai.configure(api_key=API_KEY)

MODEL_NAME = "gemini-2.0-flash-exp-image-generation"
# MODEL_NAME = "imagen-3.0-generate-002"

os.makedirs(THUMBNAIL_STORAGE_PATH, exist_ok=True)

# For emotion detection, we use a simple DNN-based approach with OpenCV.
# (You can replace this with a more sophisticated method if needed.)
FACE_PROTO = "action_models/deploy.prototxt"
FACE_MODEL = "action_models/res10_300x300_ssd_iter_140000.caffemodel"
face_net = cv2.dnn.readNetFromCaffe(FACE_PROTO, FACE_MODEL)

def detect_faces(image_path):
    img = cv2.imread(image_path)
    face_detector = solutions.face_detection.FaceDetection(min_detection_confidence=0.5)
    results = face_detector.process(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    return len(results.detections) if results.detections else 0

def detect_text(image_path):
    img = cv2.imread(image_path)
    text = pytesseract.image_to_string(img)
    return bool(text.strip())

def extract_fonts(image_path):
    img = cv2.imread(image_path)
    return pytesseract.image_to_string(img)

def extract_colors(image_path, color_count=3):
    try:
        color_thief = ColorThief(image_path)
        palette = color_thief.get_palette(color_count=color_count, quality=1)
        def rgb_to_hex(rgb):
            return '#%02x%02x%02x' % rgb
        return [rgb_to_hex(color) for color in palette]
    except Exception as e:
        return []

def encode_image(image_path):
    """Encodes image as base64 and gets MIME type."""
    mime_type, _ = mimetypes.guess_type(image_path)
    if not mime_type:
        mime_type = "image/jpeg"  # Default to JPEG if unknown

    with open(image_path, "rb") as img_file:
        return {
            "mime_type": mime_type,
            "data": base64.b64encode(img_file.read()).decode("utf-8")
        }

def generate_image_from_input(image_path: str, prompt: str):
    """
    Uses Gemini to generate an image based on an input image and user prompt.
    """
    try:
        image_data = encode_image(image_path)

        # Encode image as base64 with MIME type
        image_part = {
            "inline_data": {
                "mime_type": image_data["mime_type"],  # or "image/jpeg"
                "data": image_data["data"]
            }
        }

        # Create model instance
        model = genai.GenerativeModel(MODEL_NAME)

        # Call Gemini API
        # response = model.generate_content([
        #     {"role": "user", "parts": [{"inline_data": image_data}]},  # Image as Blob
        #     {"role": "user", "parts": [{"text": prompt}]}  # Prompt as text
        # ])

        response = model.generate_content(
            [
                {
                    "role": "user",
                    "parts": [image_part, {"text": prompt}]
                }
            ]
        )

        print("Full Response:", response)

        # Extract the generated image URL or base64 content
        if response and response.candidates:
            for candidate in response.candidates:
                for part in candidate.content.parts:
                    if hasattr(part, "inline_data"):
                        return part.inline_data.data
                        # return base64.b64encode(part.inline_data.data).decode("utf-8")  # Return base64 image data

        print("❌ No image returned in the response.")
        return None  # Handle case if no image is returned
    
    except Exception as e:
        print(f"Error generating image: {e}")
        return None

def save_thumbnail(video):
    """Downloads and saves a thumbnail image locally."""
    response = requests.get(video["thumbnail_url"])
    if response.status_code == 200:
        filename = f"{video['video_id']}.jpg"
        filepath = os.path.join(THUMBNAIL_STORAGE_PATH, filename)
        
        with open(filepath, "wb") as file:
            file.write(response.content)
        
        return filepath
    return None

def store_thumbnails(keyword, current_user: User = Depends(get_current_user)):
    """Fetches thumbnails from YouTube, analyzes them, and stores them in the database."""
    videos = fetch_video_thumbnails(keyword)
    if not videos:
        return {"message": "No thumbnails found for this keyword."}

    db = SessionLocal()
    results = []  # Change result to a list instead of a dict

    for video in videos:
        filepath = save_thumbnail(video)
        if filepath:
            # Validate the thumbnail and get analysis details
            validation = validate_thumbnail(filepath)

            # Save analysis results to the database
            thumbnail = Thumbnail(
                keyword=keyword,
                video_id=video["video_id"],
                title=video["title"],
                url=video["thumbnail_url"],
                saved_path=filepath,
                text_detection=validation["text_detection"],  # Store as a boolean
                face_detection=validation["face_detection"],
                emotion=validation["emotion"],
                color_palette=json.dumps(validation["color_palette"]),  # Store as JSON
                user_id=current_user.id
            )
            db.add(thumbnail)

            # Append structured result
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
    
    return {"message": "Thumbnails stored successfully.", "results": results}

def clarity_score(image_path):
    image = cv2.imread(image_path)
    return cv2.Laplacian(image, cv2.CV_64F).var()

def predict_ctr_score(image_path):
    clarity = clarity_score(image_path)
    text_presence = detect_text(image_path)
    face_presence = detect_faces(image_path)
    ctr = 0.5 + (0.1 if text_presence else -0.1) + (0.2 if face_presence else -0.2) + (0.2 if clarity > 100 else -0.2)
    return max(0, min(1, ctr))

def extract_fonts(image_path):
    text = pytesseract.image_to_string(image_path)
    return text

def detect_emotions(image_path):
    # Read the image
    img = cv2.imread(image_path)
    
    # Initialize the FER detector (mtcnn=True gives better face detection)
    detector = FER(mtcnn=True)
    
    # Detect emotions for all faces in the image
    results = detector.detect_emotions(img)
    
    if results:
        # If there are multiple faces, you might average them or choose the one with the highest confidence.
        # Here, we simply pick the dominant emotion of the first detected face.
        emotions = results[0]["emotions"]
        dominant_emotion = max(emotions, key=emotions.get)
        return dominant_emotion
    else:
        return None

def validate_thumbnail(image_path):
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
