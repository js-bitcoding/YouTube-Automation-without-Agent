from pydantic import BaseModel
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, Query, HTTPException
from database.db_connection import get_db
from database.schemas import VideoSaveRequest
from database.models import Video, Channel
from database.models import User, UserSavedVideo
from functionality.current_user import get_current_user
from service.youtube_service import fetch_youtube_videos, fetch_video_by_id
from service.engagement_service import calculate_engagement_rate, calculate_view_to_subscriber_ratio, calculate_view_velocity
from utils.logging_utils import logger

router = APIRouter()
saved_videos = []

@router.get("/search/")
def get_videos(
    query: str, 
    max_results: int = Query(10, description="Number of results to return", ge=1, le=50),
    duration_category: str = Query(None, description="Filter by duration: short, medium, long"),
    min_views: int = Query(None, description="Minimum views required"),
    min_subscribers: int = Query(None, description="Minimum subscriber count"),
    upload_date: str = Query(None, description="Filter by upload date: today, this_week, this_month, this_year"),
    db: Session = Depends(get_db)
):
    """
    Search YouTube videos with filters like query, max results, duration, views, 
    subscribers, and upload date.

    Args:
        query (str): Search query.
        max_results (int): Number of results to return (default 10).
        duration_category (str): Filter by video duration.
        min_views (int): Minimum views.
        min_subscribers (int): Minimum subscribers.
        upload_date (str): Filter by upload date.
        db (Session): Database session.

    Returns:
        list: List of videos matching the search criteria.
    """
    try:
        logger.info(f"User is searching for YouTube videos with query: {query}")
        return fetch_youtube_videos(query, max_results, duration_category, min_views, min_subscribers, upload_date)
    except Exception as e:
        logger.error(f"Error during video search: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while searching for videos.")

@router.get("/video/{videoid}")
def get_video_details(videoid: str):
    """
    API endpoint to retrieve details for a specific video by its video ID. 

    This function fetches video information such as title, channel details, views, likes, 
    comments, and more. If the video is not found, an error message is returned.

    Args:
        videoid (str): The ID of the video to fetch details for.

    Returns:
        dict: The details of the video, including its title, channel info, views, likes, 
              comments, and other relevant metrics.

    Raises:
        HTTPException: 
            - 404 if the video is not found.
    """
    try:
        logger.info(f"Fetching details for video {videoid}")
        video_data = fetch_video_by_id(videoid)
        if "error" in video_data:
            logger.error(f"Error fetching video details for {videoid}: {video_data['error']}")
            raise HTTPException(status_code=404, detail="Video not found")
        logger.info(f"Video details fetched successfully for {videoid}")
        return video_data
    except Exception as e:
        logger.exception(f"Error occurred while fetching video details for {videoid}: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while fetching video details.")


@router.post("/video/save/{video_id}")
def save_video(
    video_id: str, 
    db: Session = Depends(get_db), 
    user: User = Depends(get_current_user)
    ):
    """
    API endpoint to save a video by video ID. It checks if the video and its associated channel 
    exist in the database and saves them if not. The user can save a video once, and the API 
    prevents saving the same video multiple times.

    Args:
        video_id (str): The ID of the video to be saved.
        db (Session): The database session, injected via dependency.
        user (User): The current logged-in user, injected via dependency.

    Returns:
        dict: A message indicating whether the video was saved successfully, 
              along with the saved video's ID.

    Raises:
        HTTPException: 
            - 404 if the video or user is not found.
            - 400 if the video has already been saved by the user.
    """
    try:
        logger.info(f"User {user.id} is attempting to save video {video_id}")

        video_details = fetch_video_by_id(video_id)

        if "error" in video_details:
            logger.error(f"Video {video_id} not found")
            raise HTTPException(status_code=404, detail="Video not found")

        user_record = db.query(User).filter(User.id == user.id).first()
        if not user_record:
            raise HTTPException(status_code=404, detail="User not found")

        existing_channel = db.query(Channel).filter_by(channel_id=video_details["channel_id"]).first()
        if not existing_channel:
            new_channel = Channel(
                channel_id=video_details["channel_id"],
                name=video_details["channel_name"],
                total_subscribers=video_details["subscribers"]
            )
            db.add(new_channel)
            db.commit()
            db.refresh(new_channel)
            logger.info(f"New channel {video_details['channel_name']} added to the database")

        existing_video = db.query(Video).filter_by(video_id=video_id).first()
        if not existing_video:
            video_details["view_to_subscriber_ratio"] = calculate_view_to_subscriber_ratio(video_details["views"], video_details["subscribers"])
            video_details["view_velocity"] = calculate_view_velocity(video_details)
            video_details["engagement_rate"] = calculate_engagement_rate(video_details)

            new_video = Video(
                video_id=video_details["video_id"],
                title=video_details["title"],
                channel_id=video_details["channel_id"],
                channel_name=video_details["channel_name"],
                upload_date=video_details["upload_date"],
                thumbnail=video_details["thumbnail"],
                video_url=video_details["video_url"],
                views=video_details["views"],
                likes=video_details["likes"],
                comments=video_details["comments"],
                subscribers=video_details["subscribers"],
                engagement_rate=video_details["engagement_rate"],
                view_to_subscriber_ratio=video_details["view_to_subscriber_ratio"],
                view_velocity=video_details["view_velocity"]
            )
            db.add(new_video)
            db.commit()
            db.refresh(new_video)
            logger.info(f"New video {video_id} saved to the database")
            video = new_video
        else:
            logger.info(f"Video {video_id} already exists in the database")
            video = existing_video

        existing_entry = (
            db.query(UserSavedVideo)
            .filter(UserSavedVideo.user_id == user.id, UserSavedVideo.video_id == video_id)
            .first()
        )

        if existing_entry:
            logger.warning(f"User {user.id} tried to save video {video_id} again.")
            raise HTTPException(status_code=400, detail="Video already saved")

        saved_video = UserSavedVideo(user_id=user.id, video_id=video_id)
        db.add(saved_video)
        db.commit()
        db.refresh(saved_video)

        logger.info(f"User {user.id} successfully saved video {video_id}")
        return {"message": "Video saved successfully!", "video_id": video_id}

    except HTTPException as e:
        logger.warning(f"HTTP error occurred: {e.detail}")
        raise e
    except Exception as e:
        logger.exception(f"Unexpected error occurred while saving video {video_id}: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while saving the video.")

@router.get("/video/saved/")
def get_saved_videos(
    db: Session = Depends(get_db), 
    user: User = Depends(get_current_user)
    ):
    """
    Retrieves all saved videos for the current user.

    Args:
        db (Session): The database session, injected via dependency.
        user (User): The current logged-in user, injected via dependency.

    Returns:
        dict: A dictionary containing a list of saved videos for the user, including details such as
              video ID, title, channel info, upload date, and engagement metrics.

    Raises:
        HTTPException: If no saved videos are found for the user, a 404 error is raised.
    """
    try:
        logger.info(f"User {user.id} is fetching their saved videos")

        saved_videos = (
            db.query(Video)
            .join(UserSavedVideo, Video.video_id == UserSavedVideo.video_id)
            .filter(UserSavedVideo.user_id == user.id)
            .all()
        )

        if not saved_videos:
            logger.warning(f"User {user.id} has no saved videos.")
            raise HTTPException(status_code=404, detail="No saved videos found")

        logger.info(f"User {user.id} has {len(saved_videos)} saved videos.")
        return {
            "saved_videos": [
                {
                    "video_id": video.video_id,
                    "title": video.title,
                    "channel_id": video.channel_id,
                    "channel_name": video.channel_name,
                    "upload_date": video.upload_date,
                    "thumbnail": video.thumbnail,
                    "video_url": video.video_url,
                    "views": video.views,
                    "likes": video.likes,
                    "comments": video.comments,
                    "subscribers": video.subscribers,
                    "engagement_rate": video.engagement_rate,
                    "view_to_subscriber_ratio": video.view_to_subscriber_ratio,
                    "view_velocity": video.view_velocity,
                }
                for video in saved_videos
            ]
        }

    except Exception as e:
        logger.exception(f"Error occurred while retrieving saved videos for user {user.id}: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while retrieving saved videos.")