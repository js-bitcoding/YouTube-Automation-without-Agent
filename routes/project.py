from fastapi import APIRouter, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from database.models import User, Project
from service.project_service import create_project, update_project, delete_project
from database.db_connection import get_db
from auth import get_current_user
from utils.logging_utils import logger

project_router = APIRouter(prefix="/projects")

@project_router.post("/create")
def create_project_api(
    name: str = Form(...), 
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Creates a new project for the authenticated user.

    Args:
        project (ProjectCreate): The project data containing the name.
        db (Session): SQLAlchemy DB session.
        user (User): The authenticated user making the request.

    Returns:
        JSONResponse: Details of the created project.

    Raises:
        HTTPException:
            - If the project name is empty or invalid.
    """
    logger.info(f"User {user.id} requested create for new project")

    if not isinstance(name, str):
        logger.error(f"User {user.id} tried to create a project with an invalid name: {name}")
        raise HTTPException(status_code=422, detail="Project name cannot be empty.")
    
    if name.strip().lower() == "string" or not name.strip():
        logger.error(f"User {user.id} submitted an invalid project name: {name}")
        raise HTTPException(status_code=400, detail="Project name cannot be empty")

    
    return create_project(db=db, name=name.strip(), user_id=user.id)

@project_router.put("/{project_id}")
def update_project_api(
    project_id: int, 
    project_name: str = Form(...), 
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Updates the details of an existing project for the authenticated user.

    Args:
        project_id (int): The ID of the project to be updated.
        payload (ProjectUpdate): The data to update the project with (e.g., new project name).
        db (Session): SQLAlchemy DB session.
        user (User): The authenticated user making the request.

    Returns:
        Project: The updated project details.

    Raises:
        HTTPException:
            - If the project name is empty or invalid.
            - If the project does not exist or is not found.
    """
    logger.info(f"User {user.id} requested update for project {project_id}")

    if not isinstance(project_name, str):
        logger.error(f"User {user.id} tried to update project {project_id} with an invalid name: {name}")
        raise HTTPException(status_code=400, detail="Project name cannot be empty.")

    if project_name.strip().lower() == "string" or not project_name.strip():
        logger.error(f"User {user.id} submitted an invalid project name: {project_name}")
        raise HTTPException(status_code=400, detail="Project name cannot be empty")
    
    updated_project = update_project(db, project_id, project_name, user_id=user.id)
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
    """
    Deletes a project for the authenticated user.

    Args:
        project_id (int): The ID of the project to be deleted.
        db (Session): SQLAlchemy DB session.
        user (User): The authenticated user making the request.

    Returns:
        dict: A confirmation message stating the project has been deleted.

    Raises:
        HTTPException:
            - If the project does not exist or the user is not authorized to delete the project.
    """
    logger.info(f"User {user.id} requested delete for project {project_id}")
    return delete_project(db, project_id, user_id=user.id)

@project_router.get("/list")
def list_projects_api(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Retrieves a list of projects for the authenticated user.

    Args:
        db (Session): SQLAlchemy DB session.
        user (User): The authenticated user making the request.

    Returns:
        dict: A dictionary containing a list of projects with their IDs, names, and creation times.

    Raises:
        HTTPException:
            - If no projects are found for the user.
    """
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
    """
    Retrieves a project by its ID for the authenticated user.

    Args:
        project_id (int): The ID of the project to retrieve.
        db (Session): SQLAlchemy DB session.
        user (User): The authenticated user making the request.

    Returns:
        dict: A dictionary containing the project's ID, name, and creation time.

    Raises:
        HTTPException:
            - If the project is not found or is deleted.
    """
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
