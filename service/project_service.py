from sqlalchemy.orm import Session
from database.models import Project

def create_project(db: Session, name: str):
    project = Project(name=name)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project

def update_project(db: Session, project_name: str, name: str):
    project = db.query(Project).filter(Project.name == project_name).first()
    if project:
        project.name = name
        db.commit()
        db.refresh(project)
    return project

def delete_project(db: Session, project_name: str):
    print("inside delete function")
    project = db.query(Project).filter(Project.name == project_name).first()
    print(f"project is ::: {project}")
    if project:
        try:
            db.delete(project)
            db.commit()
            print(f"Project {project_name} deleted successfully.")
        except Exception as e:
            db.rollback()
            print(f"Error deleting project {project_name}: {e}")
            return {"error": "Failed to delete project"}
    
    return project
