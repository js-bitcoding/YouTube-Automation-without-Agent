import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

class UserRegister(BaseModel):
    username: str 
    password: str 
    role: str = Field(default="user")
    
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

class ProjectCreate(BaseModel):
    name: Optional[str] = None

class ProjectUpdate(BaseModel):
    name: Optional[str] = None

class GroupCreate(BaseModel):
    name: Optional[str] = None
    project_id: Optional[int] = None
    youtube_links: Optional[List[str]] = []
    document_names: Optional[List[str]] = []

class GroupUpdate(BaseModel):
    name: Optional[str] = None

class KnowledgeUpload(BaseModel):
    group_name: str
    youtube_links: List[str] = []
    document_names: List[str] = []

class ChatCreate(BaseModel):
    name: str
    group_ids: List[int] = []

class ChatUpdate(BaseModel):
    name: Optional[str] = None

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
    is_deleted: bool

    class Config:
        orm_mode = True
