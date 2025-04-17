from sqlalchemy.orm import Session
from database.models import Project
from fastapi import HTTPException

def create_project(db: Session, name: str, user_id: int):
    project = Project(name=name, user_id=user_id)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project

def update_project(db: Session, project_id: int, name: str, user_id: int):
    # Fetch the project and ensure that it belongs to the user
    project = db.query(Project).filter(Project.id == project_id, Project.user_id == user_id).first()
    
    # If the project does not exist or does not belong to the current user, return an error
    if not project:
        raise HTTPException(status_code=404, detail="Project not found or access denied")
    
    # Update the project if it belongs to the user
    project.name = name
    db.commit()
    db.refresh(project)
    
    return project

def delete_project(db: Session, project_id: int, user_id: int):
    print("inside delete function")
    
    # Filter by both project_id and user_id to ensure the user can delete the project
    project = db.query(Project).filter(Project.id == project_id, Project.user_id == user_id).first()
    print(f"project is ::: {project}")
    
    if project:
        try:
            db.delete(project)
            db.commit()
            print(f"Project {project_id} deleted successfully.")
        except Exception as e:
            db.rollback()
            print(f"Error deleting project {project_id}: {e}")
            return {"error": "Failed to delete project"}
    else:
        raise HTTPException(status_code=404, detail="Project not found or access denied")
    
    return project

def list_projects(db: Session, user_id: int):
    return db.query(Project).filter(Project.user_id == user_id).all()
