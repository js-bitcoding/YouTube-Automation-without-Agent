from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

class UserRegister(BaseModel):
    username: str 
    password: str 
    
class UserLogin(BaseModel):
    username: str 
    password: str 
    