import datetime
from fastapi import Form,Body
from typing import Optional, List, Union
from pydantic import BaseModel, Field, EmailStr

class UserRegister(BaseModel):
    username: str 
    password: str 
    email_id : EmailStr
    
class SaveVideoRequest(BaseModel):
    note: Optional[str] = None
    
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

    @classmethod
    def as_form(
            cls,
            name: str = Form(...),
            content: str = Body(...)
        ):
            return cls(name=name, content=content)
    
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

class GetFileDataRequest(BaseModel):
    """Request model for the get_file_data endpoint"""
    collection_name: str
    username: str
    file_name: Optional[str] = None

class DeleteFileDataRequest(BaseModel):
    """Request model for the delete_file_data endpoint"""
    username: str
    collection_name: str
    file_name: str

class DeleteAllCollectionDataRequest(BaseModel):
    """Request model for the delete_all_collection_data endpoint"""
    collection_name: str
    username: str

class VectorDataStoreRequest(BaseModel):
    collection_name: Union[str, List[str]]
    filename: str
    document: str  
    summary: Optional[str] = None
    metadata: Optional[dict] = None

class CollectionResponseModel(BaseModel):
    ids: List[str]
    embeddings: Optional[List[List[float]]]
    documents: List[str]
    uris: Optional[List[str]] = None
    data: Optional[List[str]] = None
    metadatas: List[Optional[dict]]
    included: List[str]