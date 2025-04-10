from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends
from database.db_connection import get_db
from database.models import GeneratedTitle, User
from functionality.current_user import get_current_user  
from service.title_generator_service import generate_ai_titles

router = APIRouter()

@router.post("/generate_titles/")
def get_titles(
    topic: str,
    user: User = Depends(get_current_user), 
    db: Session = Depends(get_db),
):
    return generate_ai_titles(topic, user.id, db)  

@router.get("/user_titles/")
def get_user_titles(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Fetch all AI-generated titles for the current user.
    """
    rows = db.query(GeneratedTitle).filter(GeneratedTitle.user_id == user.id).all()
    
    all_titles = []
    for row in rows:
        if isinstance(row.titles, list):
            all_titles.extend(row.titles)
        else:
            all_titles.append(row.titles)  

    return {"user_id": user.id, "generated_titles": all_titles}
