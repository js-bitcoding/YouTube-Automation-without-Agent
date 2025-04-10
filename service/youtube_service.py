import os
import re
import requests
from database.models import Video
from config import YOUTUBE_API_KEY
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError
from service.engagement_service import (
    calculate_view_to_subscriber_ratio,
    calculate_view_velocity,
    calculate_engagement_rate,
)

BASE_URL = "https://www.googleapis.com/youtube/v3"
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

def fetch_video_thumbnails(keyword):
    params = {
        "part": "snippet",
        "q": keyword,
        "maxResults": 10,
        "type": "video",
        "key": YOUTUBE_API_KEY
    }
    
    response = requests.get(YOUTUBE_SEARCH_URL, params=params).json()
    print("YouTube API Response:", response)
    videos = []
    
    for item in response.get("items", []):
        video_id = item["id"]["videoId"]
        snippet = item["snippet"]
        
        if "shorts" not in snippet["title"].lower():
            videos.append({
                "video_id": video_id,
                "title": snippet["title"],
                "thumbnail_url": snippet["thumbnails"]["high"]["url"]
            })
    
    return videos

def get_published_after(filter_option):
    """Convert filter option into an ISO 8601 datetime string."""
    now = datetime.utcnow()

    if filter_option == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + "Z"
    elif filter_option == "this week":
        start_of_week = now - timedelta(days=now.weekday())  # Monday of this week
        return start_of_week.replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + "Z"
    elif filter_option == "this month":
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return start_of_month.isoformat() + "Z"
    elif filter_option == "this year":
        start_of_year = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        return start_of_year.isoformat() + "Z"
    
    return None 

def fetch_youtube_videos(query, max_results=10, duration_category=None, min_views=None, min_subscribers=None, upload_date=None):
    """Fetch YouTube videos with optional filters, excluding Shorts (videos under 60 seconds)."""
    
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

    search_response = requests.get(search_url, params=search_params).json()
    videos = []
    video_ids = []
    channel_ids = []

    for item in search_response.get("items", []):
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
    stats_response = requests.get(stats_url, params=stats_params).json()

    filtered_videos = []
    
    for i, item in enumerate(stats_response.get("items", [])):
        stats = item.get("statistics", {})
        duration_str = item.get("contentDetails", {}).get("duration", "PT0S")
        video_duration = parse_duration_to_seconds(duration_str)

        print(f"Video ID: {video_ids[i]} | Duration: {video_duration} seconds")  

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
        videos[i]["videoDuration"] = video_duration_label  #

        channels_url = f"{BASE_URL}/channels"
        channels_params = {
            "part": "statistics",
            "id": ",".join(set(channel_ids)),
            "key": YOUTUBE_API_KEY
        }
        channels_response = requests.get(channels_url, params=channels_params).json()

        channel_subscribers = {item["id"]: int(item["statistics"].get("subscriberCount", 0)) 
                               for item in channels_response.get("items", [])}

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

def calculate_ctr(clicks, impressions):
    """Calculate the CTR (Click-Through Rate)."""
    if impressions == 0:
        return 0  
    return round((clicks / impressions) * 100, 2)

def parse_duration_to_seconds(duration):
    """Convert ISO 8601 duration (e.g., PT1H2M30S) to total seconds."""
    print("Raw Duration String:", duration)  
    
    pattern = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")
    match = pattern.match(duration)
    if not match:
        return 0

    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)

    total_seconds = hours * 3600 + minutes * 60 + seconds
    print("Parsed Duration (Seconds):", total_seconds)  
    
    return total_seconds

if __name__ == "__main__":
    query = "football"
    results = fetch_youtube_videos(query, duration_category="medium")  
    print("\nFinal Results:")
    for video in results:
        print(f"{video['title']} | Duration: {video['duration']}s | Views: {video['views']}")

def store_videos_in_db(videos):
    """Store fetched videos in the database."""
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
            print(f"Video {video['video_id']} already exists in the database.")

def fetch_video_by_id(video_id):
    """Fetch details for a single video using its video ID."""
    if not YOUTUBE_API_KEY:
        raise ValueError("YouTube API Key is missing. Check your .env file.")

    url = f"{BASE_URL}/videos"
    params = {
        "part": "snippet,statistics,contentDetails",
        "id": video_id,
        "key": YOUTUBE_API_KEY
    }

    response = requests.get(url, params=params).json()

    if "items" not in response or not response["items"]:
        return {"error": "Video not found"}

    item = response["items"][0]
    
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
    
    channel_response = requests.get(channel_url, params=channel_params).json()
    subscribers = 0  

    if "items" in channel_response and channel_response["items"]:
        subscribers = int(channel_response["items"][0]["statistics"].get("subscriberCount", 0))

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
