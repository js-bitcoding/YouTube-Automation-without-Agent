from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database.models import User, Project
from database.schemas import ProjectCreate, ProjectUpdate
from service.project_service import create_project, update_project, delete_project,list_projects
from database.db_connection import get_db
from auth import get_current_user

project_router = APIRouter(prefix="/projects")

@project_router.post("/create")
def create_project_api(
    project: ProjectCreate, 
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    return create_project(db=db, name=project.name, user_id=user.id)

@project_router.put("/{project_id}")
def update_project_api(
    project_id: int, 
    payload: ProjectUpdate, 
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    # Pass project_id and user_id to the update function
    return update_project(db, project_id, payload.name, user_id=user.id)

@project_router.delete("/{project_id}")
def delete_project_api(
    project_id: int, 
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    print("deleting project")
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
        raise HTTPException(status_code=404, detail="No projects found for this user.")

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
