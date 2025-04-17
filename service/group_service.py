from sqlalchemy.orm import Session
from database.models import Group

def create_group(db: Session, name: str, project_name: str, docs: list, links: list):
    group = Group(name=name, project_id=project_name)
    db.add(group)
    db.commit()
    db.refresh(group)
    return group

# def update_group(db: Session, group_name: str, name: str):
#     group = db.query(Group).filter(Group.name == group_name).first()
#     if group:
#         group.name = name or group.name
#         db.commit()
#         db.refresh(group)
#     return group

# def delete_group(db: Session, group_name: str):
#     group = db.query(Group).filter(Group.name == group_name).first()
#     if group:
#         db.delete(group)
#         db.commit()
#     return group

def update_group(db: Session, group_id: int, name: str, user_id: int):
    # Query the group by group_id instead of group_name
    group = db.query(Group).filter(Group.id == group_id).first()
    
    if not group:
        return None  

   
    if group.user_id != user_id:
        return None 
    group.name = name or group.name
    db.commit()
    db.refresh(group)

    return group

def delete_group(db: Session, group_id: int, user_id: int):
    # Query the group by group_id instead of group_name
    group = db.query(Group).filter(Group.id == group_id).first()

    if not group:
        return None  # Group not found

    
    if group.user_id != user_id:
        return None  

    db.delete(group)
    db.commit()

    return group

