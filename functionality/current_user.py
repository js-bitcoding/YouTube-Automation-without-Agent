from datetime import datetime
from fastapi import HTTPException, Depends, status
from functionality.jwt_token import decodeJWT
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from database.models import User
from database.db_connection import get_db
from utils.logging_utils import logger

jwt_bearer = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(jwt_bearer), db: Session = Depends(get_db)):
    """
    Authenticates and returns the current user based on JWT token.

    Args:
        credentials (HTTPAuthorizationCredentials): Bearer token credentials.
        db (Session): SQLAlchemy DB session.

    Returns:
        User: The authenticated user object.

    Raises:
        HTTPException: If the token is expired, invalid, or user not found.
    """
    token = credentials.credentials
    token_data = decodeJWT(token)
    logger.info("Token received and decoded.")

    if token_data["expired"]:
        logger.warning("Token has expired.")
        user_id = token_data["payload"].get("user_id") if token_data["payload"] else None
        if user_id:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                user.is_active = False
                user.logout_time = datetime.utcnow()
                db.commit()
                logger.info(f"User ID {user_id} marked inactive and logout time recorded due to token expiry.")
        raise HTTPException(status_code=401, detail="❌ Token expired. Auto-logged out.")

    if not token_data["valid"]:
        logger.error("Invalid token.")
        raise HTTPException(status_code=401, detail="❌ Invalid token.")

    user_id = token_data["payload"]["user_id"]
    user = db.query(User).filter(User.id == user_id).first()

    if user is None:
        logger.error(f"User not found for ID {user_id}.")
        raise HTTPException(status_code=404, detail="❌ User not found.")

    logger.info(f"User ID {user_id} successfully authenticated.")
    return user

def admin_only(user: User = Depends(get_current_user)):
    """
    Ensures that the current user has admin privileges.

    Args:
        user (User): The currently authenticated user.

    Returns:
        User: The same user if they are an admin.

    Raises:
        HTTPException: If the user is not an admin.
    """
    if user.role != "admin":
        logger.warning(f"Access denied for User ID {user.id}. Role: {user.role}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="❌ Access denied. Only admins are allowed to access this resource."
        )
    logger.info(f"Admin access granted for User ID {user.id}.")
    return user