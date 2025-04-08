import os
import jwt as pyjwt
from dotenv import load_dotenv
from datetime import datetime, timedelta
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError

load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))

def create_jwt_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return pyjwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decodeJWT(jwtoken: str):
    try:
        payload = pyjwt.decode(jwtoken, SECRET_KEY, algorithms=[ALGORITHM])
        return {"valid": True, "expired": False, "payload": payload}
    except ExpiredSignatureError:
        return {"valid": False, "expired": True, "payload": None}
    except InvalidTokenError:
        return {"valid": False, "expired": False, "payload": None}
