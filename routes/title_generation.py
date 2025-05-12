from sqlalchemy.orm import Session
from utils.logging_utils import logger
from database.db_connection import get_db
from database.models import GeneratedTitle, User
from fastapi import APIRouter, Depends,HTTPException
from functionality.current_user import get_current_user  
from service.title_generator_service import generate_ai_titles

router = APIRouter()

@router.post("/generate_titles/")
def get_titles(
    topic: str,
    user: User = Depends(get_current_user), 
    db: Session = Depends(get_db),
):
    """
    Generates AI-generated titles based on the provided topic for the authenticated user.

    Args:
        topic (str): The topic for which titles will be generated.
        user (User): The authenticated user requesting the title generation.
        db (Session): SQLAlchemy DB session.

    Returns:
        dict: A dictionary containing the input topic and a list of AI-generated titles.

    Raises:
        HTTPException:
            - 400: If topic is missing.
            - 500: If title generation fails or any unexpected error occurs.
    """
    try:
        if not topic:
            logger.error(f"User {user.id} provided an empty topic for title generation.")
            raise HTTPException(status_code=400, detail="Topic cannot be empty.")

        logger.info(f"User {user.id} is requesting AI-generated titles for topic '{topic}'")

        try:
            titles = generate_ai_titles(topic, user.id, db)

            if not titles or "titles" not in titles or not titles["titles"]:
                logger.warning(f"No titles were generated for user {user.id} with topic '{topic}'")
                raise HTTPException(status_code=500, detail="Title generation failed.")

            return {"topic": topic, "generated_titles": titles["titles"]}

        except Exception as inner_exception:
            logger.exception(f"Error during title generation for user {user.id} with topic '{topic}': {inner_exception}")
            raise HTTPException(status_code=500, detail="An error occurred while generating titles.")
    
    except Exception as outer_exception:
        logger.exception(f"Unexpected error in request by user {user.id}: {outer_exception}")
        raise HTTPException(status_code=500, detail="Internal server error during title generation.")

@router.get("/user_titles/")
def get_user_titles(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Retrieve all video topics and their corresponding generated titles for the authenticated user.

    Returns a structured list of video entries with:
    - Topic name
    - Generated title list
    - Internal title ID

    Args:
        db (Session): SQLAlchemy DB session.
        user (User): The currently authenticated user.

    Returns:
        dict: {
            "user_id": int,
            "videos": List[{
                "topic": str,
                "titlesid": int,
                "titles": List[str]
            }],
            "message": Optional[str]
        }

    Raises:
        HTTPException: 500 - On unexpected database or processing error.
    """
    logger.info(f"User {user.id} is requesting grouped titles by topic.")

    try:
        rows = db.query(GeneratedTitle).filter(
            GeneratedTitle.user_id == user.id,
            GeneratedTitle.is_deleted == False
        ).all()


        videos = []

        for row in rows:
            topic = row.video_topic.strip() if row.video_topic else None
            titles_list = row.titles if isinstance(row.titles, list) else []

            if not topic or not titles_list:
                logger.warning(f"Skipping row ID {row.id}: Empty topic or titles.")
                continue

            videos.append({
                "topic": topic,
                "titlesid": row.id,
                "titles": titles_list
            })

        if not videos:
            logger.info(f"No titles found for user {user.id}.")
            return {
                "user_id": user.id,
                "videos": [],
                "message": "No generated titles found for this user."
            }

        logger.info(f"User {user.id} has {len(videos)} video entries with generated titles.")
        return {
            "user_id": user.id,
            "videos": videos
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error occurred while fetching grouped titles for user {user.id}: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while retrieving titles.")
    
@router.delete("/delete_title/")
def delete_title(
    title_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Soft-deletes a specific generated title by its ID for the authenticated user.
    Sets the `is_deleted` flag to True instead of removing the record.

    Args:
        title_id (int): The ID of the generated title to delete.
        db (Session): SQLAlchemy DB session.
        user (User): The currently authenticated user.

    Returns:
        dict: A success message upon soft deletion.

    Raises:
        HTTPException:
            - 404: If the title is not found or does not belong to the user.
            - 500: If an unexpected error occurs.
    """
    logger.info(f"User {user.id} requested soft deletion of title ID {title_id}")

    try:
        title_entry = db.query(GeneratedTitle).filter(
            GeneratedTitle.id == title_id,
            GeneratedTitle.user_id == user.id,
            GeneratedTitle.is_deleted == False  
        ).first()

        if not title_entry:
            logger.warning(f"Title ID {title_id} not found or already deleted for user {user.id}")
            raise HTTPException(status_code=404, detail="Title not found or already deleted.")

        title_entry.is_deleted = True
        db.commit()

        logger.info(f"Title ID {title_id} soft-deleted successfully for user {user.id}")
        return {"message": "Title marked as deleted."}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error occurred during soft deletion of title ID {title_id} for user {user.id}: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while deleting the title.")
    
