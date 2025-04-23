from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database.db_connection import get_db
from database.models import User
from database.schemas import UserCountResponse
from functionality.current_user import admin_only

admin_router = APIRouter()

@admin_router.get("/count", response_model=UserCountResponse)
def get_user_count(db: Session = Depends(get_db), _: User = Depends(admin_only)):
    users = db.query(User).filter(User.is_deleted == False).all()
    if not users:
        raise HTTPException(status_code=404, detail="No active users found")
    return {
        "total_users": len(users),
        "users": users
    }

@admin_router.put("/{user_id}")
def update_user(
    user_id: int,
    username: str = None,
    is_active: bool = None,
    role: str = None,
    db: Session = Depends(get_db),
    _: User = Depends(admin_only)
):
    user = db.query(User).filter(User.id == user_id, User.is_deleted == False).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if username:
        user.username = username
    if is_active is not None:
        user.is_active = is_active
    if role:
        if role and role not in ("admin", "user"):
            raise HTTPException(status_code=400, detail="Role must be 'admin' or 'user'")
        user.role = role

    db.commit()
    db.refresh(user)
    return {"message": "✅ User updated", "user": {"id": user.id, "username": user.username, "role": user.role, "updated_at": user.updated_at}}

@admin_router.delete("/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db), _: User = Depends(admin_only)):
    user = db.query(User).filter(User.id == user_id, User.is_deleted == False).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found or already deleted")
    
    user.is_deleted = True
    db.commit()
    return {"message": f"🗑️ User ID {user_id} deleted"}
