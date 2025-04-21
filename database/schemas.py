from pydantic import BaseModel
from typing import Optional, List
import datetime

class UserRegister(BaseModel):
    username: str 
    password: str 
    
class UserLogin(BaseModel):
    username: str 
    password: str 
    
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
