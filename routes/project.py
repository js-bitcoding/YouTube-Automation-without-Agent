from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database.models import User, Project
from database.schemas import ProjectCreate, ProjectUpdate
from service.project_service import create_project, update_project, delete_project
from database.db_connection import get_db
from auth import get_current_user

project_router = APIRouter(prefix="/projects")

@project_router.post("/create")
def create_project_api(
    project: ProjectCreate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
    ):
    return create_project(db, project.name)

@project_router.put("/{project_name}")
def update_project_api(project_name: str, payload: ProjectUpdate, db: Session = Depends(get_db)):
    return update_project(db, project_name, payload.name)

@project_router.delete("/{project_name}")
def delete_project_api(project_name: str, db: Session = Depends(get_db)):
    print("deleting project")
    return delete_project(db, project_name)
