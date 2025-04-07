import datetime
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine, Column, String, Integer, Text, DateTime, func, JSON, ForeignKey, Boolean

Base = declarative_base()

class Thumbnail(Base):
    __tablename__ = "thumbnails"
    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(String, unique=True, nullable=False)
    title = Column(String, nullable=False)
    url = Column(String, nullable=False)
    saved_path = Column(String, nullable=True)
    text_detection = Column(JSON, nullable=True)
    face_detection = Column(Integer, nullable=True)
    emotion = Column(String, nullable=True)
    color_palette = Column(JSON, nullable=True)
    keyword = Column(Text)
    
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    user = relationship("User", back_populates="saved_thumbnails")


class Script(Base):
    __tablename__ = "scripts"
    id = Column(Integer, primary_key=True, index=True)
    input_title = Column(String, nullable=False)
    video_title = Column(String, nullable=True)
    mode = Column(String, nullable=False)
    style = Column(String, nullable=False)
    transcript = Column(Text, nullable=False)
    generated_script = Column(Text, nullable=False)
    youtube_links = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    user = relationship("User", back_populates="generated_script")

class RemixedScript(Base):
    __tablename__ = "remixed_scripts"
    id = Column(Integer, primary_key=True, index=True)
    video_url = Column(String, unique=True, index=True)
    mode = Column(String)
    style = Column(String)
    transcript = Column(Text)
    remixed_script = Column(Text)

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    user = relationship("User", back_populates="remixed_script")

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    is_active = Column(Boolean, default=False)
    role = Column(String, default="user")  # "admin" or "user"
    login_history = relationship("UserLoginHistory", back_populates="user", cascade="all, delete-orphan") 
   

    saved_thumbnails = relationship("Thumbnail", back_populates="user", cascade="all, delete-orphan")
    generated_script = relationship("Script", back_populates="user", cascade="all, delete-orphan")
    remixed_script = relationship("RemixedScript", back_populates="user", cascade="all, delete-orphan")
    

class UserLoginHistory(Base):
    __tablename__ = "user_login_history"
 
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    login_time = Column(DateTime, default=datetime.datetime.now, nullable=False)
    # logout_time = Column(DateTime, default=datetime.utcnow())
    logout_time = Column(DateTime,  nullable=True ,default=None)
    
    user = relationship("User")

