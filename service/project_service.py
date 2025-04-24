from fastapi import HTTPException
from sqlalchemy.orm import Session
from database.models import Project
from utils.logging_utils import logger

def create_project(db: Session, name: str, user_id: int):
    """
    Creates a new project and associates it with the specified user.

    Args:
        db (Session): Database session.
        name (str): Project name.
        user_id (int): ID of the user creating the project.

    Returns:
        Project: The newly created project.
    """
    project = Project(name=name, user_id=user_id)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project

def update_project(db: Session, project_id: int, name: str, user_id: int):
    """
    Updates the name of an existing project for a specific user.

    Args:
        db (Session): Database session.
        project_id (int): ID of the project to update.
        name (str): New name for the project.
        user_id (int): ID of the user updating the project.

    Returns:
        Project: The updated project.

    Raises:
        HTTPException: If the project is not found or the user doesn't have access.
    """
    project = db.query(Project).filter(
        Project.id == project_id, 
        Project.user_id == user_id,
        Project.is_deleted == False
        ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found or access denied")

    project.name = name
    db.commit()
    db.refresh(project)
    
    return project

def delete_project(db: Session, project_id: int, user_id: int):
    """
    Marks a project as deleted for a specific user.

    Args:
        db (Session): Database session.
        project_id (int): ID of the project to delete.
        user_id (int): ID of the user requesting the deletion.

    Returns:
        dict: A message indicating whether the project was successfully deleted or not.

    Raises:
        HTTPException: If the project is not found or already deleted.
    """
    logger.info(f"inside the project delete function")
    project = db.query(Project).filter(
        Project.id == project_id, 
        Project.user_id == user_id,
        Project.is_deleted == False
        ).first()
    logger.info(f"project is ::: {project}")
    
    if project:
        try:
            project.is_deleted = True
            db.commit()
            logger.info(f"Project {project_id} deleted successfully.")
            return {"message": f"Project {project_id} deleted successfully."}
        except Exception as e:
            db.rollback()
            logger.info(f"Error deleting project {project_id}: {e}")
            return {"error": "Failed to delete project"}
    else:
        raise HTTPException(status_code=404, detail="Project not found or already deleted")

def list_projects(db: Session, user_id: int):
    """
    Fetches all non-deleted projects for a specific user.

    Args:
        db (Session): Database session.
        user_id (int): ID of the user for whom to list projects.

    Returns:
        list: A list of projects associated with the user that are not deleted.
    """
    return db.query(Project).filter(
        Project.user_id == user_id,
        Project.is_deleted == False
    ).all()
