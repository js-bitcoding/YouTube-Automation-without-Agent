import datetime
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String, Integer, Text, DateTime, func, JSON, ForeignKey, Boolean, Float, BigInteger, Table

Base = declarative_base()

chat_group_association = Table(
    "chat_group_association",
    Base.metadata,
    Column("chat_id", ForeignKey("chats.id"), primary_key=True),
    Column("group_id", ForeignKey("groups.id"), primary_key=True)
)


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    created_time = Column(DateTime, default=datetime.datetime.now, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))

    groups = relationship("Group", back_populates="project", cascade="all, delete-orphan")

class Group(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), index=True)
    created_time = Column(DateTime, default=datetime.datetime.now, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"))

    project = relationship("Project", back_populates="groups", passive_deletes=True)
    documents = relationship("Document", back_populates="group", cascade="all, delete-orphan")
    videos = relationship("YouTubeVideo", back_populates="group", cascade="all, delete-orphan")
    chats = relationship("Chat", secondary=chat_group_association, back_populates="groups")
    sessions = relationship("ChatSession", back_populates="group", cascade="all, delete-orphan")
    user = relationship("User", back_populates="groups", passive_deletes=True)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    is_active = Column(Boolean, default=False)
    role = Column(String, default="user")  # "admin" or "user"
   

    login_history = relationship("UserLoginHistory", back_populates="user", cascade="all, delete-orphan") 
    saved_thumbnails = relationship("Thumbnail", back_populates="user", cascade="all, delete-orphan")
    # generated_script = relationship("Script", back_populates="user", cascade="all, delete-orphan")
    # remixed_script = relationship("RemixedScript", back_populates="user", cascade="all, delete-orphan")
    saved_videos = relationship("UserSavedVideo", back_populates="user", cascade="all, delete-orphan")
    generated_titles = relationship("GeneratedTitle", back_populates="user", cascade="all, delete-orphan")
    groups = relationship("Group", back_populates="user", cascade="all, delete-orphan")
    projects = relationship("Project", backref="user", cascade="all, delete-orphan")
    chats = relationship("Chat", back_populates="user", cascade="all, delete-orphan")

class UserLoginHistory(Base):
    __tablename__ = "user_login_history"
 
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    login_time = Column(DateTime, default=datetime.datetime.now, nullable=False)
    logout_time = Column(DateTime,  nullable=True ,default=None)
    
    user = relationship("User")

class Channel(Base):
    __tablename__ = "channels"

    channel_id = Column(String(50), primary_key=True)
    name = Column(Text, nullable=False)  
    total_subscribers = Column(BigInteger, default=0)
    total_videos = Column(BigInteger, default=0)
    country = Column(String(50))

    videos = relationship("Video", back_populates="channel", cascade="all, delete-orphan")

class Video(Base):
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
    __tablename__ = "user_saved_videos"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)

    video_id = Column(String(50), ForeignKey("videos.video_id", ondelete="CASCADE"), primary_key=True)
    folder_name = Column(String(100))
    saved_at = Column(DateTime, default=datetime.datetime.now)

    user = relationship("User", back_populates="saved_videos")
    video = relationship("Video", back_populates="saved_by_users")

class GeneratedTitle(Base):
    __tablename__ = "generated_titles"

    id = Column(Integer, primary_key=True, index=True)
    video_topic = Column(String)
    titles = Column(JSON)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)

    user = relationship("User", back_populates="generated_titles")

class Thumbnail(Base):
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
    
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    user = relationship("User", back_populates="saved_thumbnails")

# class Script(Base):
#     __tablename__ = "scripts"
#     id = Column(Integer, primary_key=True, index=True)
#     input_title = Column(String, nullable=False)
#     video_title = Column(String, nullable=True)
#     mode = Column(String, nullable=False)
#     style = Column(String, nullable=False)
#     transcript = Column(Text, nullable=False)
#     generated_script = Column(Text, nullable=False)
#     youtube_links = Column(Text, nullable=True)
#     created_at = Column(DateTime, default=func.now())

#     user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
#     user = relationship("User", back_populates="generated_script")

# class RemixedScript(Base):
#     __tablename__ = "remixed_scripts"
#     id = Column(Integer, primary_key=True, index=True)
#     video_url = Column(String, unique=False, index=True)
#     mode = Column(String)
#     style = Column(String)
#     transcript = Column(Text)
#     remixed_script = Column(Text)

#     user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
#     user = relationship("User", back_populates="remixed_script")

class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String,nullable=True)
    content = Column(Text, nullable=False)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"))

    group = relationship("Group", back_populates="documents")

class YouTubeVideo(Base):
    __tablename__ = "youtube_videos"
    id = Column(Integer, primary_key=True, index=True)
    url = Column(String)
    transcript = Column(Text)  
    tone = Column(String)  
    style = Column(String)  
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"))

    group = relationship("Group", back_populates="videos")

# class Chat(Base):
#     __tablename__ = "chats"
#     id = Column(Integer, primary_key=True, index=True)
#     name = Column(String)
#     query = Column(Text)
#     response_text = Column(Text)
#     user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
#     instruction_id = Column(Integer, ForeignKey("instructions.id", ondelete="SET NULL"))
#     instruction = relationship("Instruction", back_populates="chats")

#     user = relationship("User", back_populates="chats")
#     groups = relationship("Group", secondary=chat_group_association, back_populates="chats")
#     history = relationship("ChatHistory", back_populates="chat", cascade="all, delete-orphan")

# class ChatHistory(Base):
#     __tablename__ = "chat_history"

#     id = Column(Integer, primary_key=True, index=True)
#     message = Column(Text, nullable=False)
#     sender = Column(String, nullable=False)
#     timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
#     chat_id = Column(Integer, ForeignKey("chats.id", ondelete="CASCADE"))

#     chat = relationship("Chat", back_populates="history")


class Instruction(Base):
    __tablename__ = "instructions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    content = Column(Text, nullable=False)

    chats = relationship("Chat", back_populates="instruction", cascade="all, delete-orphan")


class Chat(Base):
    __tablename__ = "chats"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    query = Column(Text)
    response_text = Column(Text)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    instruction_id = Column(Integer, ForeignKey("instructions.id", ondelete="SET NULL"))
    chatsession_id = Column(Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"))

    instruction = relationship("Instruction", back_populates="chats")
    user = relationship("User", back_populates="chats")
    sessions = relationship(
        "ChatSession",
        back_populates="chat",
        foreign_keys="[ChatSession.chat_id]"  # Explicit FK here
    )
    groups = relationship("Group", secondary=chat_group_association, back_populates="chats")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    chat_id = Column(Integer, ForeignKey("chats.id", ondelete="CASCADE"))
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"))
    conversation = Column(JSON, default=list)
    chat = relationship(
        "Chat",
        back_populates="sessions",
        foreign_keys=[chat_id]  # Explicit FK here
    )
    group = relationship("Group", back_populates="sessions")


   

