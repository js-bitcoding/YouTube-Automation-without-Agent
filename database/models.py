from datetime import datetime
from zoneinfo import ZoneInfo
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy import Column, String, Integer, Text, DateTime, func, JSON, ForeignKey, Boolean, Float, BigInteger, Table

timezone = datetime.now(ZoneInfo("Asia/Kolkata"))
Base = declarative_base()

chat_session_group = Table(
    "chat_session_group",
    Base.metadata,
    Column("chat_session_id", ForeignKey("chat_sessions.id", ondelete="CASCADE"), primary_key=True),
    Column("group_id", ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True),
    Column("created_at", DateTime, default=timezone),
    Column("updated_at", DateTime, default=timezone, onupdate=timezone),
    Column("is_deleted", Boolean, default=False)
)

class Project(Base):
    """
    Project model representing a user's project.
    """
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    created_time = Column(DateTime, default=timezone, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    is_deleted = Column(Boolean, default=False)

    groups = relationship("Group", back_populates="project", cascade="all, delete-orphan")
    
class Group(Base):
    """Group model representing a user's group within a project."""
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), index=True)
    created_time = Column(DateTime, default=timezone, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=timezone, onupdate=timezone, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"))
    is_deleted = Column(Boolean, default=False)

    project = relationship("Project", back_populates="groups", passive_deletes=True)
    documents = relationship("Document", back_populates="group", cascade="all, delete-orphan")
    videos = relationship("YouTubeVideo", back_populates="group", cascade="all, delete-orphan")
    sessions = relationship("ChatSession",secondary=chat_session_group,back_populates="groups")
    user = relationship("User", back_populates="groups", passive_deletes=True)

class User(Base):
    """User model representing a user with various relationships and attributes."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, nullable=False)
    password = Column(String, nullable=False)
    email_id = Column(String, unique=True, nullable=False)
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime, default=timezone)
    updated_at = Column(DateTime(timezone=True), default=timezone, onupdate=timezone)
    is_deleted = Column(Boolean, default=False)
    role = Column(String, default="user")
   
    login_history = relationship("UserLoginHistory", back_populates="user", cascade="all, delete-orphan") 
    saved_thumbnails = relationship("Thumbnail", back_populates="user", cascade="all, delete-orphan")
    saved_videos = relationship("UserSavedVideo", back_populates="user", cascade="all, delete-orphan")
    generated_titles = relationship("GeneratedTitle", back_populates="user", cascade="all, delete-orphan")
    groups = relationship("Group", back_populates="user", cascade="all, delete-orphan")
    projects = relationship("Project", backref="user", cascade="all, delete-orphan")
    chats = relationship("ChatHistory", back_populates="user", cascade="all, delete-orphan")
    instructions = relationship("Instruction", back_populates="user", cascade="all, delete-orphan")

class UserLoginHistory(Base):
    """UserLoginHistory model tracking user login and logout times."""
    __tablename__ = "user_login_history"
 
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    created_at = Column(DateTime(timezone=True), default=timezone, nullable=False)
    login_time = Column(DateTime, default=timezone, nullable=False)
    logout_time = Column(DateTime,  nullable=True ,default=None)
    
    user = relationship("User", back_populates="login_history")

class Channel(Base):
    """Channel model representing a YouTube channel with video details."""
    __tablename__ = "channels"

    channel_id = Column(String(50), primary_key=True)
    name = Column(Text, nullable=False)  
    total_subscribers = Column(BigInteger, default=0)
    total_videos = Column(BigInteger, default=0)
    country = Column(String(50))
    created_at = Column(DateTime, default=timezone)

    videos = relationship("Video", back_populates="channel", cascade="all, delete-orphan")

class Video(Base):
    """Video model representing YouTube video details and related statistics."""
    __tablename__ = "videos"

    video_id = Column(String(50), primary_key=True)
    title = Column(Text, nullable=False)
    description = Column(Text)
    channel_id = Column(String(50), ForeignKey("channels.channel_id", ondelete="CASCADE"), nullable=False)  
    channel_name = Column(Text, nullable=False)  
    thumbnail = Column(String(255))
    upload_date = Column(DateTime, nullable=False)
    views = Column(BigInteger, default=0)
    likes = Column(BigInteger, default=0)
    comments = Column(BigInteger, default=0)
    subscribers = Column(Integer, default=0)
    engagement_rate = Column(Float, default=0.0)
    view_to_subscriber_ratio = Column(Float, default=0.0) 
    view_velocity = Column(Float, default=0.0)
    video_url = Column(Text, nullable=False)
    
    channel = relationship("Channel", back_populates="videos")  
    trending_topics = relationship("TrendingTopic", back_populates="video", cascade="all, delete-orphan")
    saved_by_users = relationship("UserSavedVideo", back_populates="video", cascade="all, delete-orphan")

class TrendingTopic(Base):
    """TrendingTopic model representing video trends and related statistics."""
    __tablename__ = "trending_topics"

    trend_id = Column(Integer, primary_key=True, autoincrement=True)
    video_id = Column(String(50), ForeignKey("videos.video_id", ondelete="CASCADE"), nullable=False)
    trend_category = Column(String(100))
    trend_score = Column(Float)
    trend_growth = Column(Float)
    keyword = Column(String, unique=True, nullable=False)  
    count = Column(Integer, nullable=False, default=0)  

    video = relationship("Video", back_populates="trending_topics")

class UserSavedVideo(Base):
    """UserSavedVideo model representing the relationship between users and saved videos."""
    __tablename__ = "user_saved_videos"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    video_id = Column(String(50), ForeignKey("videos.video_id", ondelete="CASCADE"), primary_key=True)
    folder_name = Column(String(100))
    saved_at = Column(DateTime, default=timezone)
    is_deleted = Column(Boolean, default=False)

    user = relationship("User", back_populates="saved_videos")
    video = relationship("Video", back_populates="saved_by_users")

class GeneratedTitle(Base):
    """GeneratedTitle model representing a user's generated video titles."""
    __tablename__ = "generated_titles"

    id = Column(Integer, primary_key=True, index=True)
    video_topic = Column(String)
    titles = Column(JSON)
    created_at = Column(DateTime, default=timezone)
    is_deleted = Column(Boolean, default=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)

    user = relationship("User", back_populates="generated_titles")

class Thumbnail(Base):
    """Thumbnail model representing a video thumbnail associated with a user."""
    __tablename__ = "thumbnails"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(String, unique=False, nullable=False)
    title = Column(String, nullable=False)
    url = Column(String, nullable=False)
    saved_path = Column(String, nullable=True)
    text_detection = Column(JSON, nullable=True)
    face_detection = Column(Integer, nullable=True)
    emotion = Column(String, nullable=True)
    color_palette = Column(JSON, nullable=True)
    keyword = Column(Text)
    created_at = Column(DateTime, default=timezone)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    
    user = relationship("User", back_populates="saved_thumbnails")
    user_saved_thumbnail = relationship("UserSavedThumbnail", back_populates="thumbnail")

class Document(Base):
    """Document model representing a document associated with a group."""
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=True)
    content = Column(Text, nullable=False)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"))
    tone = Column(String)  
    style = Column(String)
    created_at = Column(DateTime, default=timezone)
    is_deleted = Column(Boolean, default=False)

    group = relationship("Group", back_populates="documents")

class YouTubeVideo(Base):
    """YouTubeVideo model representing a video in a specific group."""
    __tablename__ = "youtube_videos"
    id = Column(Integer, primary_key=True, index=True)
    url = Column(String)
    transcript = Column(Text)  
    tone = Column(String)  
    style = Column(String)  
    created_at = Column(DateTime, default=timezone)
    is_deleted = Column(Boolean, default=False)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"))

    group = relationship("Group", back_populates="videos")

class Instruction(Base):
    """Instruction model representing user-defined instructions for a conversation."""
    __tablename__ = "instructions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=timezone)
    updated_at = Column(DateTime, default=timezone, onupdate=timezone)
    is_activate = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False) 
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    
    user = relationship("User", back_populates="instructions")
    conversations = relationship("ChatConversation", back_populates="instruction", cascade="all, delete-orphan")

class ChatHistory(Base): 
    """ChatHistory model representing the history of a user's chat query and response."""
    __tablename__ = "chat_histories"

    id = Column(Integer, primary_key=True, index=True)
    query = Column(Text)
    response = Column(Text)
    context = Column(JSON)
    created_at = Column(DateTime, default=timezone)
    is_deleted = Column(Boolean, default=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))

    chat_conversation_id = Column(Integer, ForeignKey("chat_conversations.id", ondelete="CASCADE"))
    user = relationship("User", back_populates="chats")
    conversation = relationship("ChatConversation", back_populates="chats")

class ChatConversation(Base): 
    """ChatConversation model representing a conversation associated with a specific instruction.""" 
    __tablename__ = "chat_conversations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    created_at = Column(DateTime, default=timezone)
    updated_at = Column(DateTime, default=timezone, onupdate=timezone)
    is_deleted = Column(Boolean, default=False)
    instruction_id = Column(Integer, ForeignKey("instructions.id", ondelete="SET NULL"))
    chat_session_id = Column(Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"))
    instruction = relationship("Instruction", back_populates="conversations")

    session = relationship("ChatSession", back_populates="conversations")
    chats = relationship("ChatHistory", back_populates="conversation", cascade="all, delete-orphan")

class ChatSession(Base):
    """ChatSession model representing a user's chat session with associated groups and conversations."""
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    created_at = Column(DateTime, default=timezone)
    updated_at = Column(DateTime, default=timezone, onupdate=timezone)
    is_deleted = Column(Boolean, default=False)
    conversation = Column(MutableList.as_mutable(JSON), default=list)

    groups = relationship("Group", secondary=chat_session_group, back_populates="sessions")
    conversations = relationship("ChatConversation", back_populates="session", cascade="all, delete-orphan")

class UserSavedThumbnail(Base):
    """UserSavedThumbnail model representing a saved thumbnail by a user."""
    __tablename__ = "user_saved_thumbnail"

    thumbnail_id = Column(Integer, ForeignKey("thumbnails.id", ondelete="CASCADE"), primary_key=True)
    folder_name = Column(String(100))
    saved_at = Column(DateTime, default=timezone)
    is_deleted = Column(Boolean, default=False)

    thumbnail = relationship("Thumbnail", back_populates="user_saved_thumbnail")
