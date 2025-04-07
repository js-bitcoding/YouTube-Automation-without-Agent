from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List

class UserRegister(BaseModel):
    username: str 
    password: str 
    
class UserLogin(BaseModel):
    username: str 
    password: str 
    