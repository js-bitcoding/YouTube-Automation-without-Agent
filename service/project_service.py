from fastapi import HTTPException
from sqlalchemy.orm import Session
from database.models import Project

def create_project(db: Session, name: str, user_id: int):
    project = Project(name=name, user_id=user_id)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project

def update_project(db: Session, project_id: int, name: str, user_id: int):
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
    project = db.query(Project).filter(
        Project.id == project_id, 
        Project.user_id == user_id,
        Project.is_deleted == False
        ).first()
    
    if project:
        try:
            project.is_deleted = True
            db.commit()
            return {"message": f"Project {project_id} deleted successfully."}
        except Exception as e:
            db.rollback()
            return {"error": "Failed to delete project"}
    else:
        raise HTTPException(status_code=404, detail="Project not found or already deleted")

def list_projects(db: Session, user_id: int):
    return db.query(Project).filter(
        Project.user_id == user_id,
        Project.is_deleted == False
    ).all()
