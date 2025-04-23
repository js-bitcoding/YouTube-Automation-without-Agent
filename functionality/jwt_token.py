import os
import jwt as pyjwt
from dotenv import load_dotenv
from datetime import datetime, timedelta
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError
from utils.logging_utils import logger

load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))

def create_jwt_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    logger.info(f"JWT created with expiration {expire.isoformat()}")
    return pyjwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decodeJWT(jwtoken: str):
    try:
        payload = pyjwt.decode(jwtoken, SECRET_KEY, algorithms=[ALGORITHM])
        logger.info("JWT successfully decoded.")
        return {"valid": True, "expired": False, "payload": payload}
    except ExpiredSignatureError:
        logger.warning("JWT decoding failed: Token has expired.")
        return {"valid": False, "expired": True, "payload": None}
    except InvalidTokenError:
        logger.error("JWT decoding failed: Invalid token.")
        return {"valid": False, "expired": False, "payload": None}
