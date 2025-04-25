from datetime import datetime
from sqlalchemy.orm import Session
from fastapi.security import HTTPBearer
from passlib.context import CryptContext
from fastapi import APIRouter, Depends, HTTPException
from database.db_connection import get_db
from fastapi.responses import JSONResponse
from database.models import User,UserLoginHistory
from database.schemas import UserLogin,UserRegister
from functionality.jwt_token import create_jwt_token
from functionality.current_user import get_current_user
from utils.logging_utils import logger

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
    if db.query(User).filter(User.email_id == user_data.email_id, User.is_deleted == False).first():
        logger.warning(f"Signup failed for email {user_data.email_id}: Email already registered.")
        raise HTTPException(status_code=400, detail="❌ Email already in use. Please use a different one.")

    if user_data.username.strip().lower() == "string" or not user_data.username.strip():
        logger.warning(f"Signup failed for username {user_data.username}: Username cannot be empty.")
        raise HTTPException(status_code=400, detail="Username cannot be empty you need to provide.")
    
    if user_data.password.strip().lower() == "string" or not user_data.password.strip():
        logger.warning(f"Signup failed for username {user_data.username}: Password cannot be empty.")
        raise HTTPException(status_code=400, detail="Password cannot be empty you need to provide.")
    
    existing_user = db.query(User).filter(
        User.username == user_data.username,
        User.is_deleted == False
        ).first()
    
    if existing_user:
        logger.warning(f"Signup failed for username {user_data.username}: User already exists.")
        raise HTTPException(status_code=400, detail="❌ User already exists. Please try with different Names")

    hashed_password = pwd_context.hash(user_data.password)
    new_user = User(
        username=user_data.username, 
        password=hashed_password,
        email_id=user_data.email_id,
        role="user"
        )
    
    db.add(new_user)
    db.commit()

    logger.info(f"User {user_data.username} registered successfully")
    return JSONResponse(status_code=201,
        content={"message": f"✅ Registered successfully as ! Now you can login"}
    )

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
    if user_data.username.strip().lower() == "string" or not user_data.username.strip():
        logger.warning(f"Login failed for username {user_data.username}: Username cannot be empty.")
        raise HTTPException(status_code=400, detail="Username cannot be empty. You need to provide.")
    
    if user_data.password.strip().lower() == "string" or not user_data.password.strip():
        logger.warning(f"Login failed for username {user_data.username}: Password cannot be empty.")
        raise HTTPException(status_code=400, detail="Password cannot be empty. You need to provide.")
    
    user = db.query(User).filter(
        User.username == user_data.username
        ).first()
    
    if not user or not pwd_context.verify(user_data.password, user.password):
        logger.warning(f"Invalid login attempt for username {user_data.username}: Incorrect username or password.")
        raise HTTPException(status_code=400, detail="❌ Invalid credentials. Your username or password is wrong.")

    login_record = UserLoginHistory(
        user_id=user.id,
        login_time=datetime.utcnow(),
        logout_time=None
    )
    db.add(login_record)

    user.is_active = True
    db.commit()
    db.refresh(login_record)

    token = create_jwt_token({"user_id": user.id})
    logger.info(f"User {user_data.username} logged in successfully.")
    return JSONResponse(status_code=201,content= { 
        "token": token,
        "message": "You have logged in successfully! Now You Can Explore"
    })

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
    logger.debug(f"Logging out user ID: {current_user.id}")

    latest_login = db.query(UserLoginHistory).filter(
        UserLoginHistory.user_id == current_user.id,
        UserLoginHistory.logout_time.is_(None)
    ).order_by(UserLoginHistory.login_time.desc()).first()

    logger.debug(f"Latest login record: {latest_login}")

    if latest_login:
        latest_login.logout_time = datetime.utcnow()
        db.add(latest_login)
    else:
        logger.warning(f"No active login record found for user {current_user.username}")

    current_user.is_active = False
    db.commit()

    logger.info(f"User {current_user.username} logged out successfully.")
    return JSONResponse(status_code=201, content={"message": "Logout successful!"})

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
    logger.info(f"User {current_user.username} requested their current user details.")
    return {
        "id": current_user.id,
        "username": current_user.username,
        "role": current_user.role,
        "is_active": current_user.is_active,
    }
