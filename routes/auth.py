from datetime import datetime
from fastapi import status
from sqlalchemy.orm import Session
from utils.logging_utils import logger
from fastapi.security import HTTPBearer
from passlib.context import CryptContext
from database.db_connection import get_db
from sqlalchemy.exc import SQLAlchemyError
from fastapi.responses import JSONResponse
from database.models import User,UserLoginHistory
from database.schemas import UserLogin,UserRegister
from functionality.jwt_token import create_jwt_token
from fastapi import APIRouter, Depends, HTTPException
from functionality.current_user import get_current_user

router = APIRouter()
security = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def user_api(user_id: int = Depends(get_current_user)):
    return {"message": f"Hello User {user_id}, you can access this endpoint every 2 seconds!"}

@router.post("/signup")
def signup(user_data: UserRegister, db: Session = Depends(get_db)):
    """
    Registers a new user with the provided username, password, and role.

    Validates that:
    - The username and password are not empty and are not set to default values.
    - The user role is either 'user' or 'admin'.
    - The username is not already taken by an existing user.

    Args:
        user_data (UserRegister): The registration details including username, password, and role.
        db (Session): The database session.

    Returns:
        JSONResponse: A message indicating whether the registration was successful or not.
    """
    try:
        if db.query(User).filter(User.email_id == user_data.email_id, User.is_deleted == False).first():
            logger.warning(f"Signup failed: Email {user_data.email_id} already in use.")
            raise HTTPException(status_code=400, detail="❌ Email already in use.")

        if user_data.username.strip().lower() == "string" or not user_data.username.strip():
            raise HTTPException(status_code=400, detail="Username cannot be empty.")

        if user_data.password.strip().lower() == "string" or not user_data.password.strip():
            raise HTTPException(status_code=400, detail="Password cannot be empty.")

        if db.query(User).filter(User.username == user_data.username, User.is_deleted == False).first():
            logger.warning(f"Signup failed: Username {user_data.username} already exists.")
            raise HTTPException(status_code=400, detail="❌ Username already taken.")

        hashed_password = pwd_context.hash(user_data.password)

        new_user = User(
            username=user_data.username,
            password=hashed_password,
            email_id=user_data.email_id,
            role="user"
        )
        db.add(new_user)
        db.commit()

        logger.info(f"User {user_data.username} registered successfully.")
        return JSONResponse(status_code=201, content={"message": "✅ Registered successfully! Now you can login."})

    except SQLAlchemyError as e:
        db.rollback()
        logger.exception("Signup failed due to DB error.")
        raise HTTPException(status_code=500, detail="⚠️ Registration failed due to a server error.")
    except Exception as e:
        logger.exception("Unexpected error during signup.")
        raise HTTPException(status_code=500, detail="Unexpected error during registration.")


@router.post("/login")
def login(user_data: UserLogin, db: Session = Depends(get_db)):
    """
    Handles user login by verifying credentials and generating a JWT token.

    Validates the following:
    - The username and password are provided and not empty.
    - The provided credentials match an existing user in the database.

    If the login is successful:
    - A login record is created in the `UserLoginHistory` table.
    - The user's account is marked as active.
    - A JWT token is generated for the user.

    Args:
        user_data (UserLogin): The login details, including username and password.
        db (Session): The database session.

    Returns:
        JSONResponse: A response containing the JWT token and a success message.
    """
    try:
        if user_data.username.strip().lower() == "string" or not user_data.username.strip():
            raise HTTPException(status_code=400, detail="Username cannot be empty.")

        if user_data.password.strip().lower() == "string" or not user_data.password.strip():
            raise HTTPException(status_code=400, detail="Password cannot be empty.")

        user = db.query(User).filter(User.username == user_data.username).first()
        if not user or not pwd_context.verify(user_data.password, user.password):
            logger.warning(f"Login failed: Invalid credentials for {user_data.username}.")
            raise HTTPException(status_code=400, detail="❌ Invalid username or password.")

        login_record = UserLoginHistory(user_id=user.id, login_time=datetime.utcnow(), logout_time=None)
        db.add(login_record)

        user.is_active = True
        db.commit()
        db.refresh(login_record)

        token = create_jwt_token({"user_id": user.id})
        logger.info(f"User {user.username} logged in successfully.")
        return JSONResponse(status_code=201, content={"token": token, "message": "✅ Login successful! Now You Can Explore It !"})
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Login failed due to DB error.")
        raise HTTPException(status_code=500, detail="⚠️ Login failed due to server error.")
    except Exception:
        logger.exception("Unexpected error during login.")
        raise HTTPException(status_code=500, detail="Password or Username Must be Valid")


@router.post("/logout")
def logout(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Logs out the current user by updating their login history and marking their account as inactive.

    Validates the following:
    - Finds the most recent active login record for the current user.
    - Updates the logout time for that login record.
    - Marks the user as inactive in the database.

    Args:
        current_user (User): The currently authenticated user.
        db (Session): The database session.

    Returns:
        JSONResponse: A success message indicating that the user has logged out.
    """
    try:
        logger.debug(f"Attempting logout for user ID: {current_user.id}")

        latest_login = db.query(UserLoginHistory).filter(
            UserLoginHistory.user_id == current_user.id,
            UserLoginHistory.logout_time.is_(None)
        ).order_by(UserLoginHistory.login_time.desc()).first()

        if latest_login:
            latest_login.logout_time = datetime.utcnow()
            db.add(latest_login)

        current_user.is_active = False
        db.commit()

        logger.info(f"User {current_user.username} logged out successfully.")
        return JSONResponse(status_code=201, content={"message": "✅ Logout successful!"})

    except SQLAlchemyError:
        db.rollback()
        logger.exception("Logout failed due to DB error.")
        raise HTTPException(status_code=500, detail="⚠️ Logout failed due to a server error.")
    except Exception:
        logger.exception("Unexpected error during logout.")
        raise HTTPException(status_code=500, detail="Unexpected error during logout.")

@router.get("/current_user/")
def whoami(
    current_user: User = Depends(get_current_user)
    ):
    """
    Fetches and returns the current user's details.

    Validates the following:
    - Retrieves the current authenticated user based on the provided token.

    Args:
        current_user (User): The currently authenticated user.

    Returns:
        dict: A dictionary containing the user's id, username, role, and active status.
    """
    try:
        logger.info(f"User {current_user.username} requested current user info.")
        return {
            "id": current_user.id,
            "username": current_user.username,
            "role": current_user.role,
            "is_active": current_user.is_active,
        }
    except Exception:
        logger.exception("Error fetching current user info.")
        raise HTTPException(status_code=500, detail="⚠️ Failed to retrieve user details.")
