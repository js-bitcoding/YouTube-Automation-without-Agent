from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends,HTTPException
from database.db_connection import get_db
from database.models import GeneratedTitle, User
from functionality.current_user import get_current_user  
from service.title_generator_service import generate_ai_titles
from utils.logging_utils import logger

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
        list: A list of AI-generated titles for the specified topic.

    Raises:
        HTTPException:
            - If the title generation fails or if there is any issue with user authentication.
    """
    if not topic:
        logger.error(f"User {user.id} provided an empty topic for title generation.")
        raise HTTPException(status_code=400, detail="Topic cannot be empty.")
    
    logger.info(f"User {user.id} is requesting AI-generated titles for topic '{topic}'")

    try:
        titles = generate_ai_titles(topic, user.id, db)
        if not titles:
            logger.warning(f"No titles were generated for user {user.id} with topic '{topic}'")
            raise HTTPException(status_code=500, detail="Title generation failed.")
        return {"topic": topic, "generated_titles": titles}
    
    except Exception as e:
        logger.exception(f"Error occurred during title generation for user {user.id} with topic '{topic}': {e}")
        raise HTTPException(status_code=500, detail="An error occurred while generating titles.")


@router.get("/user_titles/")
def get_user_titles(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Fetch all AI-generated titles for the currently authenticated user.

    Args:
        db (Session): SQLAlchemy DB session.
        user (User): The authenticated user requesting their generated titles.

    Returns:
        dict: A dictionary containing the user's ID and a list of their generated titles.

    Raises:
        HTTPException:
            - If no titles are found or if there are any issues retrieving the titles.
    """
    logger.info(f"User {user.id} is fetching their AI-generated titles.")
    
    try:
        rows = db.query(GeneratedTitle).filter(GeneratedTitle.user_id == user.id).all()

        if not rows:
            logger.warning(f"No generated titles found for user {user.id}.")
            raise HTTPException(status_code=404, detail="No titles found for this user.")

        all_titles = []
        for row in rows:
            if isinstance(row.titles, list):
                all_titles.extend(row.titles)
            else:
                all_titles.append(row.titles) 

        logger.info(f"User {user.id} has {len(all_titles)} generated titles.")
        return {"user_id": user.id, "generated_titles": all_titles}
    
    except Exception as e:
        logger.exception(f"Error occurred while fetching titles for user {user.id}: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while retrieving titles.")

