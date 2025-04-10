import datetime
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String, Integer, Text, DateTime, func, JSON, ForeignKey, Boolean, Float, BigInteger

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
    saved_videos = relationship("UserSavedVideo", back_populates="user", cascade="all, delete-orphan")
    generated_titles = relationship("GeneratedTitle", back_populates="user", cascade="all, delete-orphan")

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
