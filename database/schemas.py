import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, EmailStr

class UserRegister(BaseModel):
    username: str 
    password: str 
    email_id : EmailStr
    
class VideoSaveRequest(BaseModel):
    video_id: str
    title: str
    description: str

class UserLogin(BaseModel):
    username: str 
    password: str 
    
class UserOut(BaseModel):
    id: int
    username: str
    is_active: bool
    role: str

    class Config:
        orm_mode = True

class UserCountResponse(BaseModel):
    total_users: int
    users: List[UserOut]

class InstructionBase(BaseModel):
    name: str
    content: str

class InstructionCreate(InstructionBase):
    pass

class InstructionUpdate(BaseModel):
    name: Optional[str] = None
    content: Optional[str] = None

class InstructionOut(InstructionBase):
    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime
    is_activate: bool
    is_deleted: bool

    class Config:
        orm_mode = True
