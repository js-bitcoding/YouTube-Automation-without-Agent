# from pydantic import BaseModel
# from sqlalchemy.orm import Session
# from typing import Optional
# from database.db_connection import get_db
# from database.models import Video, Channel
# from database.schemas import SaveVideoRequest
# from database.models import User, UserSavedVideo
# from functionality.current_user import get_current_user
# from fastapi import APIRouter, Depends, Query, HTTPException,Body
# from service.youtube_service import fetch_youtube_videos, fetch_video_by_id,fetch_homepage_videos,fetch_related_videos
# from service.engagement_service import calculate_engagement_rate, calculate_view_to_subscriber_ratio, calculate_view_velocity

# router = APIRouter()
# saved_videos = []

# class VideoSaveRequest(BaseModel):
#     video_id: str
#     title: str
#     description: str

# @router.get("/videos")
# async def get_homepage_videos():
#     """
#     Fetches popular YouTube videos for the homepage and returns them as JSON.
#     """
#     videos = fetch_homepage_videos()  # Call the dedicated function for home page videos
#     return {"videos": videos}

# @router.get("/search/")
# def get_videos(
#     query: str, 
#     max_results: int = Query(10, description="Number of results to return", ge=1, le=50),
#     duration_category: str = Query(None, description="Filter by duration: short, medium, long"),
#     min_views: int = Query(None, description="Minimum views required"),
#     min_subscribers: int = Query(None, description="Minimum subscriber count"),
#     upload_date: str = Query(None, description="Filter by upload date: today, this week, this month, this year"),
#     db: Session = Depends(get_db)
# ):
#     """
#     Fetches popular YouTube videos for the Using Filters and returns them as JSON.
#     """
#     return fetch_youtube_videos(query, max_results, duration_category, min_views, min_subscribers, upload_date)

# @router.get("/video/{videoid}")
# def get_video_details(videoid: str):
#     """
#     Get Video For the Specific Video ID
#     """
#     video_data = fetch_video_by_id(videoid)
#     return video_data

# @router.get("/related_videos/{video_id}")
# def get_related_videos(
#     video_id: str,
#     max_results: int = Query(5, description="Number of related videos to return", ge=1, le=50),
#     db: Session = Depends(get_db)
# ):
#     """Get Related Video by the Specific Video"""
#     return fetch_related_videos(video_id, max_results)

# @router.post("/video/save/{video_id}")
# def save_video(
#     video_id: str, 
#     data: Optional[SaveVideoRequest] = Body(default=None),  
#     db: Session = Depends(get_db), 
#     user: User = Depends(get_current_user)
#     ):
#     """API endpoint to save a video by video ID."""
#     print(f"Saving video {video_id} for user {user.id}")

#     video_details = fetch_video_by_id(video_id)

#     if "error" in video_details:
#         raise HTTPException(status_code=404, detail="Video not found")

#     user = db.query(User).filter(User.id == user.id).first()
#     if not user:
#         raise HTTPException(status_code=404, detail="User not found")

#     existing_channel = db.query(Channel).filter_by(channel_id=video_details["channel_id"]).first()
    
#     if not existing_channel:
#         new_channel = Channel(
#             channel_id=video_details["channel_id"],
#             name=video_details["channel_name"],
#             total_subscribers=video_details["subscribers"]
#         )
#         db.add(new_channel)
#         db.commit()  

#     existing_video = db.query(Video).filter_by(video_id=video_id).first()

#     if not existing_video:
#         video_details["view_to_subscriber_ratio"] = calculate_view_to_subscriber_ratio(video_details["views"], video_details["subscribers"])
#         video_details["view_velocity"] = calculate_view_velocity(video_details)
#         video_details["engagement_rate"] = calculate_engagement_rate(video_details)

#         new_video = Video(
#             video_id=video_details["video_id"],
#             title=video_details["title"],
#             channel_id=video_details["channel_id"],
#             channel_name=video_details["channel_name"],
#             upload_date=video_details["upload_date"],
#             thumbnail=video_details["thumbnail"],
#             video_url=video_details["video_url"],
#             views=video_details["views"],
#             likes=video_details["likes"],
#             comments=video_details["comments"],
#             subscribers=video_details["subscribers"],
#             engagement_rate=video_details["engagement_rate"],
#             view_to_subscriber_ratio=video_details["view_to_subscriber_ratio"],
#             view_velocity=video_details["view_velocity"]
#         )

#         db.add(new_video)
#         db.commit()
#         db.refresh(new_video)
#         video = new_video  
#     else:
#         video = existing_video  

#     existing_entry = (
#         db.query(UserSavedVideo)
#         .filter(UserSavedVideo.user_id == user.id, UserSavedVideo.video_id == video_id)
#         .first()
#     )

#     if existing_entry:
#         raise HTTPException(status_code=400, detail="Video already saved")

#     saved_video = UserSavedVideo(user_id=user.id, video_id=video_id)
#     db.add(saved_video)
#     db.commit()
#     db.refresh(saved_video)

#     # Check and print incoming data
#     if data:
#         print(f"Incoming data: {data.note}")
#     else:
#         print("No data received.")

#     print(f"Saved video {video_id} successfully for user {user.id}!")

#     return {"message": "Video saved successfully!", "video_id": video_id}

# @router.get("/video/saved/")
# def get_saved_videos(
#     db: Session = Depends(get_db), 
#     user: User = Depends(get_current_user)
# ):
#     """Retrieve all non-deleted saved videos for the current user."""

#     saved_videos = (
#         db.query(Video)
#         .join(UserSavedVideo, Video.video_id == UserSavedVideo.video_id)
#         .filter(
#             UserSavedVideo.user_id == user.id,
#             UserSavedVideo.is_deleted == False  # Exclude soft-deleted videos
#         )
#         .all()
#     )

#     print(f"User {user.id} saved videos:", saved_videos)  

#     if not saved_videos:
#         return {"message": "You have no saved videos."}

#     return {
#         "saved_videos": [
#             {
#                 "video_id": video.video_id,
#                 "title": video.title,
#                 "channel_id": video.channel_id,
#                 "channel_name": video.channel_name,
#                 "upload_date": video.upload_date,
#                 "thumbnail": video.thumbnail,
#                 "video_url": video.video_url,
#                 "views": video.views,
#                 "likes": video.likes,
#                 "comments": video.comments,
#                 "subscribers": video.subscribers,
#                 "engagement_rate": video.engagement_rate,
#                 "view_to_subscriber_ratio": video.view_to_subscriber_ratio,
#                 "view_velocity": video.view_velocity,
#             }
#             for video in saved_videos
#         ]
#     }

# @router.delete("/video/save/{video_id}")
# def delete_saved_video(
#     video_id: str, 
#     db: Session = Depends(get_db), 
#     user: User = Depends(get_current_user)
# ):
#     """API endpoint to soft-delete a saved video by video ID."""
#     print(f"Soft-deleting saved video {video_id} for user {user.id}")

#     # Find the saved video that is not already deleted
#     existing_entry = (
#         db.query(UserSavedVideo)
#         .filter(
#             UserSavedVideo.user_id == user.id,
#             UserSavedVideo.video_id == video_id,
#             UserSavedVideo.is_deleted == False  # Only consider non-deleted records
#         )
#         .first()
#     )

#     if not existing_entry:
#         raise HTTPException(status_code=404, detail="Saved video not found for this user")

#     # Perform soft delete
#     existing_entry.is_deleted = True
#     db.commit()

#     print(f"Soft-deleted saved video {video_id} for user {user.id} successfully!")

#     return {
#         "message": f"Video with ID {video_id} has been marked as deleted from your saved videos."
#     }


from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
from database.db_connection import get_db
from database.models import Video, Channel, User, UserSavedVideo
from database.schemas import SaveVideoRequest
from functionality.current_user import get_current_user
from fastapi import APIRouter, Depends, Query, HTTPException, Body
from service.youtube_service import fetch_youtube_videos, fetch_video_by_id, fetch_homepage_videos, fetch_related_videos
from service.engagement_service import calculate_engagement_rate, calculate_view_to_subscriber_ratio, calculate_view_velocity

router = APIRouter()

class VideoSaveRequest(BaseModel):
    video_id: str
    title: str
    description: str

@router.get("/videos")
async def get_homepage_videos():
    """
    Fetches popular YouTube videos for the homepage and returns them as JSON.
    """
    try:
        videos = fetch_homepage_videos()
        return {"videos": videos}
    except Exception as e:
        print(f"Error fetching homepage videos: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch homepage videos")

@router.get("/search/")
def get_videos(
    query: str, 
    max_results: int = Query(10, description="Number of results to return", ge=1, le=50),
    duration_category: str = Query(None, description="Filter by duration: short, medium, long"),
    min_views: int = Query(None, description="Minimum views required"),
    min_subscribers: int = Query(None, description="Minimum subscriber count"),
    upload_date: str = Query(None, description="Filter by upload date: today, this week, this month, this year"),
    db: Session = Depends(get_db)
):
    """
    Fetches popular YouTube videos for the Using Filters and returns them as JSON.
    """
    try:
        return fetch_youtube_videos(query, max_results, duration_category, min_views, min_subscribers, upload_date)
    except Exception as e:
        print(f"Error in video search: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch videos")

@router.get("/video/{video_id}")
def get_video_details(video_id: str):
    """
    Get Video For the Specific Video ID
    """
    try:
        video_data = fetch_video_by_id(video_id)
        if "error" in video_data:
            raise HTTPException(status_code=404, detail="Video not found")
        return video_data
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching video {video_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve video details")

@router.get("/related_videos/{video_id}")
def get_related_videos(
    video_id: str,
    max_results: int = Query(5, ge=1, le=10),
    db: Session = Depends(get_db)
):
    """Get Related Video by the Specific Video"""
    try:
        return fetch_related_videos(video_id, max_results)
    except Exception as e:
        print(f"Error fetching related videos: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch related videos")

# @router.post("/video/save/{video_id}")
# def save_video(
#     video_id: str, 
#     # data: Optional[SaveVideoRequest] = Body(default=None),  
#     db: Session = Depends(get_db), 
#     user: User = Depends(get_current_user)
#     ):
#     """API endpoint to save a video by video ID."""
#     try:
#         print(f"Saving video {video_id} for user {user.id}")

#         # Fetch video details
#         video_details = fetch_video_by_id(video_id)
#         if "error" in video_details:
#             raise HTTPException(status_code=404, detail="Video not found")

#         # Get user from the database
#         user_in_db = db.query(User).filter(User.id == user.id).first()
#         if not user_in_db:
#             raise HTTPException(status_code=404, detail="User not found")

#         # Check if the channel exists, otherwise create it
#         existing_channel = db.query(Channel).filter_by(channel_id=video_details["channel_id"]).first()
#         if not existing_channel:
#             new_channel = Channel(
#                 channel_id=video_details["channel_id"],
#                 name=video_details["channel_name"],
#                 total_subscribers=video_details["subscribers"]
#             )
#             db.add(new_channel)
#             db.commit()

#         # Check if the video exists, otherwise create it
#         existing_video = db.query(Video).filter_by(video_id=video_id).first()
#         if not existing_video:
#             video_details["view_to_subscriber_ratio"] = calculate_view_to_subscriber_ratio(video_details["views"], video_details["subscribers"])
#             video_details["view_velocity"] = calculate_view_velocity(video_details)
#             video_details["engagement_rate"] = calculate_engagement_rate(video_details)

#             new_video = Video(
#                 video_id=video_details["video_id"],
#                 title=video_details["title"],
#                 channel_id=video_details["channel_id"],
#                 channel_name=video_details["channel_name"],
#                 upload_date=video_details["upload_date"],
#                 thumbnail=video_details["thumbnail"],
#                 video_url=video_details["video_url"],
#                 views=video_details["views"],
#                 likes=video_details["likes"],
#                 comments=video_details["comments"],
#                 subscribers=video_details["subscribers"],
#                 engagement_rate=video_details["engagement_rate"],
#                 view_to_subscriber_ratio=video_details["view_to_subscriber_ratio"],
#                 view_velocity=video_details["view_velocity"]
#             )

#             db.add(new_video)
#             db.commit()
#             db.refresh(new_video)
#             video = new_video
#         else:
#             video = existing_video

#         # Check if the video has already been saved by the user
#         existing_entry = (
#             db.query(UserSavedVideo)
#             .filter(UserSavedVideo.user_id == user.id, UserSavedVideo.video_id == video_id)
#             .first()
#         )
#         if existing_entry:
#             raise HTTPException(status_code=400, detail="Video already saved")

#         # Save the new user-video relationship
#         saved_video = UserSavedVideo(user_id=user.id, video_id=video_id)
#         db.add(saved_video)
#         db.commit()
#         db.refresh(saved_video)

#         # Check and print incoming data
        
#         print(f"Saved video {video_id} successfully for user {user.id}!")

#         return {"message": "Video saved successfully!", "video_id": video_id}

#     except HTTPException as e:
#         # Handle HTTPException (e.g., 404 not found, 400 bad request)
#         print(f"HTTP Exception occurred: {e.detail}")
#         raise e  # Re-raise the HTTPException

#     except Exception as e:
#         # Catch any other unexpected errors
#         print(f"An error occurred: {str(e)}")
#         raise HTTPException(status_code=500, detail="An internal server error occurred")

@router.post("/video/save/{video_id}")
def save_video(
    video_id: str,  
    db: Session = Depends(get_db), 
    user: User = Depends(get_current_user)
    ):
    """API endpoint to save a video by video ID."""
    try:
        print(f"Saving video {video_id} for user {user.id}")

        # Fetch video details
        video_details = fetch_video_by_id(video_id)
        if "error" in video_details:
            raise HTTPException(status_code=404, detail="Video not found")

        # Get user from the database
        user_in_db = db.query(User).filter(User.id == user.id).first()
        if not user_in_db:
            raise HTTPException(status_code=404, detail="User not found")

        # Check if the channel exists, otherwise create it
        existing_channel = db.query(Channel).filter_by(channel_id=video_details["channel_id"]).first()
        if not existing_channel:
            new_channel = Channel(
                channel_id=video_details["channel_id"],
                name=video_details["channel_name"],
                total_subscribers=video_details["subscribers"]
            )
            db.add(new_channel)
            db.commit()

        # Check if the video exists, otherwise create it
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
            video = new_video
        else:
            video = existing_video

        # Check if the video has already been saved by the user
        existing_entry = (
            db.query(UserSavedVideo)
            .filter(UserSavedVideo.user_id == user.id, UserSavedVideo.video_id == video_id)
            .first()
        )

        # If the video is soft deleted, remove the entry
        if existing_entry and existing_entry.is_deleted is not None:
            db.delete(existing_entry)
            db.commit()
            print(f"Soft-deleted entry for video {video_id} removed")

        # Check again if the video is saved by the user after soft delete (or if it was never saved)
        existing_entry = (
            db.query(UserSavedVideo)
            .filter(UserSavedVideo.user_id == user.id, UserSavedVideo.video_id == video_id)
            .first()
        )

        if existing_entry:
            raise HTTPException(status_code=400, detail="Video already saved")

        # Save the new user-video relationship
        saved_video = UserSavedVideo(user_id=user.id, video_id=video_id)
        db.add(saved_video)
        db.commit()
        db.refresh(saved_video)

        print(f"Saved video {video_id} successfully for user {user.id}!")

        return {"message": "Video saved successfully!", "video_id": video_id}

    except HTTPException as e:
        # Handle HTTPException (e.g., 404 not found, 400 bad request)
        print(f"HTTP Exception occurred: {e.detail}")
        raise e  # Re-raise the HTTPException

    except Exception as e:
        # Catch any other unexpected errors
        print(f"An error occurred: {str(e)}")
        raise HTTPException(status_code=500, detail="An internal server error occurred")

@router.get("/video/saved/")
def get_saved_videos(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Retrieve all non-deleted saved videos for the current user."""
    try:
        saved_videos = (
            db.query(Video)
            .join(UserSavedVideo, Video.video_id == UserSavedVideo.video_id)
            .filter(
                UserSavedVideo.user_id == user.id,
                UserSavedVideo.is_deleted == False
            )
            .all()
        )

        if not saved_videos:
            return {"message": "You have no saved videos."}

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
        print(f"Error fetching saved videos for user {user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch saved videos")

@router.delete("/video/save/{video_id}")
def delete_saved_video(
    video_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """API endpoint to soft-delete a saved video by video ID."""
    try:
        print(f"Soft-deleting saved video {video_id} for user {user.id}")

        existing_entry = (
            db.query(UserSavedVideo)
            .filter(
                UserSavedVideo.user_id == user.id,
                UserSavedVideo.video_id == video_id,
                UserSavedVideo.is_deleted == False
            )
            .first()
        )

        if not existing_entry:
            raise HTTPException(status_code=404, detail="Saved video not found for this user")

        existing_entry.is_deleted = True
        db.commit()

        print(f"Soft-deleted saved video {video_id} for user {user.id} successfully!")

        return {"message": f"Video with ID {video_id} has been marked as deleted from your saved videos."}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting saved video {video_id} for user {user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete saved video")
