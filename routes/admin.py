from database.models import User
from sqlalchemy.orm import Session
from utils.logging_utils import logger
from database.db_connection import get_db
from sqlalchemy.exc import SQLAlchemyError
from functionality.current_user import admin_only
from database.schemas import UserCountResponse
from fastapi import APIRouter, Depends, HTTPException

admin_router = APIRouter()

@admin_router.get("/active_users/", response_model=UserCountResponse)
def get_user_count(db: Session = Depends(get_db), _: User = Depends(admin_only)):
    """
    Returns the total count and list of all active (non-deleted) users.

    Args:
        db (Session): SQLAlchemy DB session.
        _ (User): Authenticated admin user (validated by admin_only).

    Returns:
        dict: Total number of active users and their details.
    """
    try:
        users = db.query(User).filter(User.is_deleted == False).all()
        if not users:
            raise HTTPException(status_code=404, detail="No active users found")
        return {
            "total_users": len(users),
            "users": users
        }
    except SQLAlchemyError as e:
        logger.exception("Database error while fetching users.")
        raise HTTPException(status_code=500, detail="⚠️ Failed to fetch users")


@admin_router.put("/{user_id}/")
def update_user(
    user_id: int,
    username: str = None,
    is_active: bool = None,
    role: str = None,
    db: Session = Depends(get_db),
    _: User = Depends(admin_only)
):
    """
    Updates user details such as username, active status, or role.

    Args:
        user_id (int): ID of the user to update.
        username (str, optional): New username.
        is_active (bool, optional): User's active status.
        role (str, optional): New role ('admin' or 'user').
        db (Session): SQLAlchemy DB session.
        _ (User): Authenticated admin user.

    Returns:
        dict: Confirmation message with updated user details.
    """
    try:
        user = db.query(User).filter(User.id == user_id, User.is_deleted == False).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if username:
            user.username = username
        if is_active is not None:
            user.is_active = is_active
        if role:
            if role not in ("admin", "user"):
                raise HTTPException(status_code=400, detail="Role must be 'admin' or 'user'")
            user.role = role

        db.commit()
        db.refresh(user)

        return {
            "message": "✅ User updated",
            "user": {
                "id": user.id,
                "username": user.username,
                "role": user.role,
                "updated_at": user.updated_at
            }
        }

    except SQLAlchemyError as e:
        logger.exception("Database error while updating user.")
        db.rollback()
        raise HTTPException(status_code=500, detail="⚠️ Failed to update user")

@admin_router.delete("/{user_id}/")
def delete_user(user_id: int, db: Session = Depends(get_db), _: User = Depends(admin_only)):
    """
    Soft-deletes a user by setting `is_deleted` to True.

    Args:
        user_id (int): ID of the user to delete.
        db (Session): SQLAlchemy DB session.
        _ (User): Authenticated admin user.

    Returns:
        dict: Confirmation message indicating deletion.
    """
    try:
        user = db.query(User).filter(User.id == user_id, User.is_deleted == False).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        user.is_deleted = True
        db.commit()
        return {"message": f"🗑️ User ID {user_id} deleted"}

    except SQLAlchemyError as e:
        logger.exception("Database error while deleting user.")
        db.rollback()
        raise HTTPException(status_code=500, detail="⚠️ Failed to delete user")
