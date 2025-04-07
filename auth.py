from datetime import datetime
from sqlalchemy.orm import Session
from fastapi.security import HTTPBearer
from passlib.context import CryptContext
from database.db_connection import get_db
from fastapi.responses import JSONResponse
from database.models import User,UserLoginHistory
from database.schemas import UserLogin,UserRegister
from fastapi import APIRouter, Depends, HTTPException
from functionality.current_user import get_current_user
from functionality.jwt_token import create_jwt_token


router = APIRouter()
security = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")



#ratelimit
# @router.get("/user_api", dependencies=[Depends(rate_limiter_per_user)])
async def user_api(user_id: int = Depends(get_current_user)):
    return {"message": f"Hello User {user_id}, you can access this endpoint every 2 seconds!"}




#without captcha
@router.post("/signup")
def signup(user_data: UserRegister, db: Session = Depends(get_db)):

    #Blank Validation
    if user_data.username.strip().lower() == "string" or not user_data.username.strip():
        raise HTTPException(status_code=400, detail="Username cannot be empty you need to provide.")
    if user_data.password.strip().lower() == "string" or not user_data.password.strip():
        raise HTTPException(status_code=400, detail="Password cannot be empty you need to provide.")
    
      # Check if the user already exists
    existing_user = db.query(User).filter(User.username == user_data.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="❌ User already exists. Please try with different Names")

    hashed_password = pwd_context.hash(user_data.password)
    new_user = User(username=user_data.username, password=hashed_password)
    db.add(new_user)
    db.commit()
    return JSONResponse(status_code=201,
        content={"message": "✅ Your registered successfully! Now you can login"}
    )

@router.post("/login")
def login(user_data: UserLogin, db: Session = Depends(get_db)):
    if user_data.username.strip().lower() == "string" or not user_data.username.strip():
        raise HTTPException(status_code=400, detail="Username cannot be empty. You need to provide.")
    if user_data.password.strip().lower() == "string" or not user_data.password.strip():
        raise HTTPException(status_code=400, detail="Password cannot be empty. You need to provide.")
    
    user = db.query(User).filter(User.username == user_data.username).first()
    if not user or not pwd_context.verify(user_data.password, user.password):
        raise HTTPException(status_code=400, detail="❌ Invalid credentials. Your username or password is wrong.")
    
    # Insert login record into user_login_history table
    login_record = UserLoginHistory(user_id=user.id, login_time=datetime.utcnow())
    db.add(login_record)
    
    # Update user status to active
    user.is_active = True
    db.commit()
    db.refresh(login_record)

    token = create_jwt_token({"user_id": user.id})
    return JSONResponse(status_code=201,content= { 
        "token": token,
        "message": "You have logged in successfully! Now You Can Explore"
        
    })

# @router.post("/logout")
# def logout(user_id: int, db: Session = Depends(get_db)):
#     user = db.query(User).filter(User.id == user_id).first()
    
#     if not user:
#         raise HTTPException(status_code=404, detail="User not found.")
    
#     # Fetch the latest login record for this user
#     latest_login = db.query(UserLoginHistory).filter(
#         UserLoginHistory.user_id == user.id,
#         UserLoginHistory.logout_time.is_(None)  # ✅ Ensure we only update the last open session
#     ).order_by(UserLoginHistory.login_time.desc()).first()
    
#     if latest_login:
#         latest_login.logout_time = datetime.utcnow()
    
#     # Update user status to inactive
#     user.is_active = False
#     db.commit()
    
#     return JSONResponse(status_code=201,content={"message": "Logout successful!"})

#without user id pass
# @router.post("/logout")
# def logout(
#     user_id: int = Depends(get_current_user),  # Directly get user_id from JWT
#     db: Session = Depends(get_db)
# ):
#     user = db.query(User).filter(User.id == user_id).first()
    
#     if not user:
#         raise HTTPException(status_code=404, detail="User not found.")
    
#     # Fetch the latest login record for this user
#     latest_login = db.query(UserLoginHistory).filter(
#         UserLoginHistory.user_id == user.id,
#         UserLoginHistory.logout_time.is_(None)  # ✅ Ensure we only update the last open session
#     ).order_by(UserLoginHistory.login_time.desc()).first()
    
#     if latest_login:
#         latest_login.logout_time = datetime.utcnow()
    
#     # Update user status to inactive
#     user.is_active = False
#     db.commit()
    
#     return JSONResponse(status_code=201, content={"message": "Logout successful!"})

@router.post("/logout")
def logout(
    current_user: User = Depends(get_current_user),  # This is the actual User object
    db: Session = Depends(get_db)
):
    # Fetch the latest login record for this user
    latest_login = db.query(UserLoginHistory).filter(
        UserLoginHistory.user_id == current_user.id,
        UserLoginHistory.logout_time.is_(None)
    ).order_by(UserLoginHistory.login_time.desc()).first()

    if latest_login:
        latest_login.logout_time = datetime.utcnow()

    # Update user status to inactive
    current_user.is_active = False
    db.commit()

    return JSONResponse(status_code=201, content={"message": "Logout successful!"})

