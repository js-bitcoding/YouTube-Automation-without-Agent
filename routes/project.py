from fastapi import APIRouter, Depends, HTTPException, Form, Query
from sqlalchemy.orm import Session
from database.models import User, Project
from service.project_service import create_project, update_project, delete_project
from database.db_connection import get_db
from routes.auth import get_current_user
from utils.logging_utils import logger

project_router = APIRouter(prefix="/projects")

@project_router.post("/new/")
def create_project_api(
    name: str = Query(...), 
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
    try:
        existing_project = db.query(Project).filter(Project.name == name.strip(), Project.user_id == user.id).first()

        if existing_project:
            logger.warning(f"User {user.id} attempted to create a project with an existing name: {name}")
            raise HTTPException(status_code=400, detail=f"A project with the name '{name.strip()}' already exists.")

        if not isinstance(name, str) or name.strip() == "":
            logger.error(f"User {user.id} provided an invalid project name: {name}")
            raise HTTPException(status_code=400, detail="Project name cannot be empty or invalid.")

        created_project = create_project(db=db, name=name.strip(), user_id=user.id)
        logger.info(f"User {user.id} created project: {created_project.name}")
        return created_project

    except HTTPException as e:
        logger.error(f"HTTPException occurred while creating project for user {user.id}: {e.detail}")
        raise e 
    
    except Exception as e:
        logger.exception(f"Unexpected error while creating project for user {user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to create project.")

@project_router.put("/{project_id}/")
def update_project_api(
    project_id: int, 
    project_name: str = Query(...), 
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
    logger.info(f"User {user.id} requested to update project {project_id}")

    try:
        if not isinstance(project_name, str) or project_name.strip() == "":
            logger.error(f"User {user.id} provided an invalid project name: {project_name}")
            raise HTTPException(status_code=400, detail="Project name cannot be empty or invalid.")
        
        updated_project = update_project(db, project_id, project_name, user_id=user.id)
        
        if not updated_project:
            logger.warning(f"User {user.id} tried to update a non-existing or unauthorized project {project_id}")
            raise HTTPException(status_code=404, detail="Project not found or unauthorized access.")
        
        logger.info(f"User {user.id} successfully updated project {project_id}")
        return updated_project

    except HTTPException as e:
        raise e
    except Exception as e:        
        logger.exception(f"Error while updating project {project_id} for user {user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update project.")

@project_router.delete("/{project_id}/")
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
    logger.info(f"User {user.id} requested to delete project {project_id}")

    try:
        result = delete_project(db, project_id, user_id=user.id)
        
        if not result:
            logger.warning(f"User {user.id} attempted to delete a non-existing or unauthorized project {project_id}")
            raise HTTPException(status_code=404, detail="Project not found or unauthorized access.")
        
        logger.info(f"Project {project_id} successfully deleted by user {user.id}")
        return {"message": f"Project {project_id} successfully deleted."}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error while deleting project {project_id} for user {user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete project.")


@project_router.get("/")
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
    logger.info(f"User {user.id} requested to list projects.")

    try:
        projects = db.query(Project).filter(
            Project.user_id == user.id,
            Project.is_deleted == False
        ).all()

        if not projects:
            logger.warning(f"No projects found for user {user.id}")
            raise HTTPException(status_code=404, detail="No projects found for this user.")

        logger.info(f"{len(projects)} projects found for user {user.id}")
        return {
            "projects": [
                {"id": project.id, "name": project.name, "created_time": project.created_time}
                for project in projects
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error while listing projects for user {user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to list projects.")


@project_router.get("/{project_id}/")
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
    logger.info(f"User {user.id} requested to retrieve project {project_id}.")

    try:
        project = db.query(Project).filter(
            Project.id == project_id,
            Project.user_id == user.id,
            Project.is_deleted == False
        ).first()

        if not project:
            logger.warning(f"Project {project_id} not found for user {user.id}")
            raise HTTPException(status_code=404, detail="Project not found.")

        logger.info(f"Project {project_id} retrieved for user {user.id}")
        return {
            "id": project.id,
            "name": project.name,
            "created_time": project.created_time
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error while retrieving project {project_id} for user {user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve project.")