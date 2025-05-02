from fastapi import HTTPException
from sqlalchemy.orm import Session
from database.models import Project
from utils.logging_utils import logger
from sqlalchemy.exc import SQLAlchemyError

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

    try:
        existing = db.query(Project).filter(
            Project.name == name.strip(),
            Project.user_id == user_id,
            Project.is_deleted == False
        ).first()

        if existing:
            logger.warning(f"User {user_id} tried to create a duplicate project name: {name}")
            raise HTTPException(status_code=400, detail="Project with this name already exists.")

        project = Project(name=name, user_id=user_id)
        db.add(project)
        db.commit()
        db.refresh(project)
        return project

    except SQLAlchemyError as e:
        logger.error(f"Error creating project: {str(e)}")
        db.rollback() 
        raise HTTPException(status_code=500, detail="Failed to create project. Database error.")
    
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
    try:
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

    except SQLAlchemyError as e:
        logger.error(f"Error updating project {project_id}: {str(e)}")
        db.rollback() 
        raise HTTPException(status_code=500, detail="Failed to update project. Database error.")


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
        HTTPException: If the project is not found.
    """
    logger.info(f"Inside the project delete function")
    try:
        project = db.query(Project).filter(
            Project.id == project_id, 
            Project.user_id == user_id,
            Project.is_deleted == False
        ).first()

        if not project:
            raise HTTPException(status_code=404, detail="Project not found or access denied")

        project.is_deleted = True
        db.commit()

        logger.info(f"Project {project_id} deleted successfully.")
        return {"message": f"Project {project_id} deleted successfully."}

    except SQLAlchemyError as e:
        logger.error(f"Error deleting project {project_id}: {str(e)}")
        db.rollback()  
        raise HTTPException(status_code=500, detail="Failed to delete project. Database error.")

def list_projects(db: Session, user_id: int):
    """
    Fetches all non-deleted projects for a specific user.

    Args:
        db (Session): Database session.
        user_id (int): ID of the user for whom to list projects.

    Returns:
        list: A list of projects associated with the user that are not deleted.
    """
    try:
        projects = db.query(Project).filter(
            Project.user_id == user_id,
            Project.is_deleted == False
        ).all()

        if not projects:
            raise HTTPException(status_code=404, detail="No projects found for this user.")

        return projects

    except SQLAlchemyError as e:
        logger.error(f"Error fetching projects for user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch projects. Database error.")