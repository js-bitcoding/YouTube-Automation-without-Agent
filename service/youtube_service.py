import os
import re
import requests
from typing import List, Dict, Optional,Union
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from service.engagement_service import (
    calculate_view_to_subscriber_ratio,
    calculate_view_velocity,
    calculate_engagement_rate,
)
from config import YOUTUBE_API_KEY
from database.models import Video, timezone
from utils.logging_utils import logger

BASE_URL = "https://www.googleapis.com/youtube/v3"
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

def fetch_video_thumbnails(keyword: str) -> List[Dict[str, str]]:
    """
    Fetch the thumbnails of YouTube videos based on a search keyword.

    Args:
        keyword (str): The search keyword for YouTube video titles.

    Returns:
        list: A list of dictionaries containing video ID, title, and thumbnail URL for each video found.
    """
    try:
        params = {
            "part": "snippet",
            "q": keyword,
            "maxResults": 10,
            "type": "video",
            "key": YOUTUBE_API_KEY
        }
        
        response = requests.get(YOUTUBE_SEARCH_URL, params=params)
        response.raise_for_status()
        response_data = response.json()
        logger.info("YouTube API Response:", response_data)
        
        videos = []
        for item in response_data.get("items", []):
            video_id = item["id"]["videoId"]
            snippet = item["snippet"]
            
            if "shorts" not in snippet["title"].lower():
                videos.append({
                    "video_id": video_id,
                    "title": snippet["title"],
                    "thumbnail_url": snippet["thumbnails"]["high"]["url"]
                })
        
        return videos
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        return []
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return []

def get_published_after(filter_option: str) -> Optional[str]:
    """
    Convert a filter option (e.g., 'today', 'this week') into an ISO 8601 datetime string.

    Args:
        filter_option (str): The filter option for the publication date (e.g., 'today', 'this week').

    Returns:
        str: An ISO 8601 datetime string representing the start of the specified period (e.g., '2025-04-25T00:00:00Z').
             Returns None if the filter option is invalid.
    """
    try:
        now = timezone

        if filter_option == "today":
            return now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + "Z"
        elif filter_option == "this week":
            start_of_week = now - timedelta(days=now.weekday())
            return start_of_week.replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + "Z"
        elif filter_option == "this month":
            start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            return start_of_month.isoformat() + "Z"
        elif filter_option == "this year":
            start_of_year = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            return start_of_year.isoformat() + "Z"
        
        return None
    except Exception as e:
        logger.error(f"Error in processing filter option: {e}")
        return None 

def fetch_youtube_videos(query: str, 
    max_results: int = 10, 
    duration_category: Optional[str] = None, 
    min_views: Optional[int] = None, 
    min_subscribers: Optional[int] = None, 
    upload_date: Optional[str] = None):
    """Fetch YouTube videos with optional filters, excluding Shorts (videos under 60 seconds)."""
    
    try:
        if not YOUTUBE_API_KEY:
            raise ValueError("YouTube API Key is missing. Check your .env file.")

        search_url = f"{BASE_URL}/search"
        search_params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": max_results,
            "key": YOUTUBE_API_KEY,
        }

        if upload_date:
            published_after = get_published_after(upload_date)
            if published_after:
                search_params["publishedAfter"] = published_after

        if duration_category:
            search_params["videoDuration"] = duration_category  

        search_response = requests.get(search_url, params=search_params)
        search_response.raise_for_status()
        response_data = search_response.json()

        videos = []
        video_ids = []
        channel_ids = []

        for item in response_data.get("items", []):
            video_id = item["id"]["videoId"]
            channel_id = item["snippet"]["channelId"]
            upload_date = item["snippet"]["publishedAt"]
            title = item["snippet"]["title"]
            thumbnail_url = item["snippet"]["thumbnails"]["high"]["url"]

            if "shorts" in title.lower():
                continue  

            videos.append({
                "video_id": video_id,
                "title": title,
                "channel_id": channel_id,
                "channel_name": item["snippet"]["channelTitle"],
                "upload_date": upload_date,
                "thumbnail": thumbnail_url,
                "video_url": f"https://www.youtube.com/watch?v={video_id}"
            })
            video_ids.append(video_id)
            channel_ids.append(channel_id)

        if not video_ids:
            return []

        stats_url = f"{BASE_URL}/videos"
        stats_params = {
            "part": "statistics,contentDetails",
            "id": ",".join(video_ids),
            "key": YOUTUBE_API_KEY
        }
        stats_response = requests.get(stats_url, params=stats_params)
        stats_response.raise_for_status()
        stats_data = stats_response.json()

        filtered_videos = []

        for i, item in enumerate(stats_data.get("items", [])):
            stats = item.get("statistics", {})
            duration_str = item.get("contentDetails", {}).get("duration", "PT0S")
            video_duration = parse_duration_to_seconds(duration_str)  
            logger.info(f"Video ID: {video_ids[i]} | Duration: {video_duration} seconds")

            if video_duration == 0:
                continue

            if video_duration < 240: 
                video_duration_label = "short"
            elif video_duration <= 1200:  
                video_duration_label = "medium"
            else:  
                video_duration_label = "long"

            if duration_category and duration_category != video_duration_label:
                continue  

            videos[i]["views"] = int(stats.get("viewCount", 0))
            videos[i]["likes"] = int(stats.get("likeCount", 0))
            videos[i]["comments"] = int(stats.get("commentCount", 0))
            videos[i]["duration"] = video_duration
            videos[i]["videoDuration"] = video_duration_label  

            channels_url = f"{BASE_URL}/channels"
            channels_params = {
                "part": "statistics",
                "id": ",".join(set(channel_ids)),
                "key": YOUTUBE_API_KEY
            }
            channels_response = requests.get(channels_url, params=channels_params)
            channels_response.raise_for_status()
            channels_data = channels_response.json()

            channel_subscribers = {item["id"]: int(item["statistics"].get("subscriberCount", 0)) 
                                for item in channels_data.get("items", [])}

            video = videos[i]
            video["subscribers"] = channel_subscribers.get(video["channel_id"], 0)
            video["view_to_subscriber_ratio"] = calculate_view_to_subscriber_ratio(video["views"], video["subscribers"])
            video["view_velocity"] = calculate_view_velocity(video)
            video["engagement_rate"] = calculate_engagement_rate(video)

            clicks = video["likes"]
            impressions = video["views"]
            video["ctr"] = calculate_ctr(clicks, impressions)

            filtered_videos.append(videos[i])

        filtered_videos.sort(key=lambda x: (x["view_to_subscriber_ratio"], x["view_velocity"], x["engagement_rate"]), reverse=True)
        store_videos_in_db(filtered_videos)  
        return filtered_videos
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        return []
    except Exception as e:
        logger.error(f"An unexpected error occurred while fetching videos: {e}")
        return []


def calculate_ctr(clicks: int, impressions: int) -> float:
    """
    Calculate the Click-Through Rate (CTR) as a percentage.

    Args:
        clicks (int): Number of clicks.
        impressions (int): Number of impressions.

    Returns:
        float: The CTR as a percentage, rounded to 2 decimal places.
              Returns 0 if impressions are 0.
    """
    try:
        if impressions == 0:
            return 0  
        return round((clicks / impressions) * 100, 2)
    except Exception as e:
        logger.error(f"Error calculating CTR: {e}")
        return 0

def parse_duration_to_seconds(duration: str) -> int:
    """
    Convert an ISO 8601 duration string (e.g., 'PT1H2M30S') into total seconds.

    Args:
        duration (str): Duration in ISO 8601 format.

    Returns:
        int: Total duration in seconds.
    """ 
    try:
        logger.info(f"Raw Duration String: {duration}")
        pattern = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")
        match = pattern.match(duration)
        if not match:
            return 0

        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)

        total_seconds = hours * 3600 + minutes * 60 + seconds 
        logger.info(f"Parsed Duration (Seconds): {total_seconds}") 
        
        return total_seconds
    except Exception as e:
        logger.error(f"Error parsing duration: {e}")
        return 0

def store_videos_in_db(videos: List[Dict[str, Union[str, int, float]]]) -> None:
    """
    Store a list of video dictionaries in the database if not already present.

    Args:
        videos (list): List of video data dictionaries.
    """
    try:
        for video in videos:
            existing_video = session.query(Video).filter_by(video_id=video["video_id"]).first()
            if existing_video:
                continue

            new_video = Video(
                video_id=video["video_id"],
                title=video["title"],
                channel_id=video["channel_id"],
                channel_name=video["channel_name"],
                upload_date=video["upload_date"],
                thumbnail=video["thumbnail"],
                video_url=video["video_url"],
                views=video["views"],
                likes=video["likes"],
                comments=video["comments"],
                subscribers=video["subscribers"],
                view_to_subscriber_ratio=video["view_to_subscriber_ratio"],
                view_velocity=video["view_velocity"],
                engagement_rate=video["engagement_rate"]
            )

            try:
                session.add(new_video)
                session.commit()
            except IntegrityError:
                session.rollback()
    except Exception as e:
        logger.error(f"Error storing videos in the database: {e}")


def fetch_video_by_id(video_id: str) -> Dict[str, Union[str, int]]:
    """
    Retrieve details for a YouTube video by ID, including stats and channel info.

    Args:
        video_id (int): YouTube video ID.

    Returns:
        dict: Video and channel details or error message.

    Raises:
        ValueError: If API key is missing.
    """
    try:
        if not YOUTUBE_API_KEY:
            raise ValueError("YouTube API Key is missing. Check your .env file.")

        url = f"{BASE_URL}/videos"
        params = {
            "part": "snippet,statistics,contentDetails",
            "id": video_id,
            "key": YOUTUBE_API_KEY
        }

        response = requests.get(url, params=params)
        response.raise_for_status()
        response_data = response.json()

        if "items" not in response_data or not response_data["items"]:
            return {"error": "Video not found"}

        item = response_data["items"][0]

        stats = item.get("statistics", {})
        duration_str = item.get("contentDetails", {}).get("duration", "PT0S")
        video_duration = parse_duration_to_seconds(duration_str)

        channel_id = item["snippet"]["channelId"]
        channel_url = f"{BASE_URL}/channels"
        channel_params = {
            "part": "statistics",
            "id": channel_id,
            "key": YOUTUBE_API_KEY
        }
        
        channel_response = requests.get(channel_url, params=channel_params)
        channel_response.raise_for_status()
        channel_data = channel_response.json()

        subscribers = 0  

        if "items" in channel_data and channel_data["items"]:
            subscribers = int(channel_data["items"][0]["statistics"].get("subscriberCount", 0))

        video_details = {
            "video_id": video_id,
            "title": item["snippet"]["title"],
            "description": item["snippet"]["description"],
            "channel_id": channel_id,
            "channel_name": item["snippet"]["channelTitle"],
            "upload_date": item["snippet"]["publishedAt"],
            "thumbnail": item["snippet"]["thumbnails"]["high"]["url"],
            "video_url": f"https://www.youtube.com/watch?v={video_id}",
            "views": int(stats.get("viewCount", 0)),
            "likes": int(stats.get("likeCount", 0)),
            "comments": int(stats.get("commentCount", 0)),
            "duration": video_duration,
            "subscribers": subscribers  
        }

        return video_details
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        return {"error": "Request failed"}
    except Exception as e:
        logger.error(f"An unexpected error occurred while fetching video by ID: {e}")
        return {"error": "An unexpected error occurred"}