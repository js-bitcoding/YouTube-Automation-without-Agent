from sqlalchemy.orm import Session
from database.models import Group

def create_group(db: Session, name: str, project_name: str, docs: list, links: list):
    group = Group(name=name, project_id=project_name)
    db.add(group)
    db.commit()
    db.refresh(group)
    return group

def update_group(db: Session, group_name: str, name: str):
    group = db.query(Group).filter(Group.name == group_name).first()
    if group:
        group.name = name or group.name
        db.commit()
        db.refresh(group)
    return group

def delete_group(db: Session, group_name: str):
    group = db.query(Group).filter(Group.name == group_name).first()
    if group:
        db.delete(group)
        db.commit()
    return group
