from fastapi import HTTPException, Depends, status
from functionality.jwt_token import decodeJWT
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from database.models import User, timezone
from database.db_connection import get_db
from utils.logging_utils import logger
from sqlalchemy.exc import SQLAlchemyError
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
    try:
        token = credentials.credentials
        token_data = decodeJWT(token)
        logger.info("Token received and decoded.")
    except Exception as e:
        logger.exception("Failed to decode JWT token.")
        raise HTTPException(status_code=400, detail="❌ Invalid or malformed token.")

    if token_data.get("expired"):
        logger.warning("Token has expired.")
        try:
            user_id = token_data["payload"].get("user_id") if token_data["payload"] else None
            if user_id:
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    user.is_active = False
                    user.logout_time = timezone
                    db.commit()
                    logger.info(f"User ID {user_id} marked inactive due to expired token.")
        except SQLAlchemyError as e:
            logger.exception("Database error while logging out expired token user.")
            raise HTTPException(status_code=500, detail="⚠️ Token expired, but failed to update user status.")
        raise HTTPException(status_code=401, detail="❌ Token expired. Auto-logged out.")

    if not token_data.get("valid"):
        logger.error("Token is invalid.")
        raise HTTPException(status_code=401, detail="❌ Invalid token.")

    user_id = token_data["payload"].get("user_id")
    try:
        user = db.query(User).filter(User.id == user_id).first()
    except SQLAlchemyError as e:
        logger.exception("Database error while fetching user.")
        raise HTTPException(status_code=500, detail="⚠️ Database error while authenticating user.")

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
    try:
        if user.role != "admin":
            logger.warning(f"Access denied for User ID {user.id}. Role: {user.role}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="❌ Access denied. Only admins are allowed to access this resource."
            )
        logger.info(f"Admin access granted for User ID {user.id}.")
        return user
    except AttributeError as e:
        logger.exception("User object is malformed or missing 'role'.")
        raise HTTPException(status_code=500, detail="⚠️ User data is corrupted or invalid.")