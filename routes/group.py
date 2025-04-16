from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database.schemas import GroupCreate, GroupUpdate
from service.group_service import create_group, update_group, delete_group
from database.db_connection import get_db

group_router = APIRouter(prefix="/groups")

@group_router.post("/create")
def create_group_api(payload: GroupCreate, db: Session = Depends(get_db)):
    return create_group(db, payload.name, payload.project_id, payload.document_names, payload.youtube_links)

@group_router.put("/{group_name}")
def update_group_api(group_name: str, payload: GroupUpdate, db: Session = Depends(get_db)):
    return update_group(db, group_name, payload.name)

@group_router.delete("/{group_name}")
def delete_group_api(group_name: str, db: Session = Depends(get_db)):
    return delete_group(db, group_name)
