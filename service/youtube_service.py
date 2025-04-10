import requests
from config import YOUTUBE_API_KEY

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"

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
