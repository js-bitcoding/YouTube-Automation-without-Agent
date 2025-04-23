from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database.models import User, Project
from database.schemas import ProjectCreate, ProjectUpdate
from service.project_service import create_project, update_project, delete_project
from database.db_connection import get_db
from auth import get_current_user
from utils.logging_utils import logger

project_router = APIRouter(prefix="/projects")

@project_router.post("/create")
def create_project_api(
    project: ProjectCreate, 
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    logger.info(f"User {user.id} requested create for new project")

    if not project.name or len(project.name.strip()) == 0:
        logger.error(f"User {user.id} tried to create a project with an invalid name: {project.name}")
        raise HTTPException(status_code=400, detail="Project name cannot be empty.")
    
    return create_project(db=db, name=project.name, user_id=user.id)

@project_router.put("/{project_id}")
def update_project_api(
    project_id: int, 
    payload: ProjectUpdate, 
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    logger.info(f"User {user.id} requested update for project {project_id}")

    if payload.name and len(payload.name.strip()) == 0:
        logger.error(f"User {user.id} tried to update project {project_id} with an invalid name: {payload.name}")
        raise HTTPException(status_code=400, detail="Project name cannot be empty.")

    updated_project = update_project(db, project_id, payload.name, user_id=user.id)
    if not updated_project:
        logger.error(f"User {user.id} tried to update a non-existing project: {project_id}")
        raise HTTPException(status_code=404, detail="Project not found.")

    return updated_project

@project_router.delete("/{project_id}")
def delete_project_api(
    project_id: int, 
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    logger.info(f"User {user.id} requested delete for project {project_id}")
    return delete_project(db, project_id, user_id=user.id)

@project_router.get("/list")
def list_projects_api(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    projects = db.query(Project).filter(
        Project.user_id == user.id,
        Project.is_deleted == False
    ).all()

    if not projects:
        logger.info(f"No projects found for user {user.id}")
        raise HTTPException(status_code=404, detail="No projects found for this user.")

    logger.info(f"{len(projects)} project(s) retrieved for user {user.id}")
    return {
        "projects": [
            {
                "id": project.id,
                "name": project.name,
                "created_time": project.created_time
            }
            for project in projects
        ]
    }

@project_router.get("/get/{project_id}")
def get_project_by_id(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == user.id,
        Project.is_deleted == False
    ).first()

    if not project:
        logger.info(f"Project with ID {project_id} not found for user {user.id}")
        raise HTTPException(status_code=404, detail="Project not found.")

    logger.info(f"Project with ID {project_id} retrieved for user {user.id}")
    return {
        "id": project.id,
        "name": project.name,
        "created_time": project.created_time
    }
