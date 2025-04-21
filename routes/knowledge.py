from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database.schemas import KnowledgeUpload
from service.knowledge_service import upload_knowledge
from database.db_connection import get_db

knowledge_router = APIRouter(prefix="/knowledge")

# @knowledge_router.post("/upload")
# def upload_knowledge_api(payload: KnowledgeUpload, db: Session = Depends(get_db)):
#     return upload_knowledge(db, payload.group_name, payload.youtube_links, payload.document_names)
