from datetime import datetime, timezone

def calculate_view_to_subscriber_ratio(views, subscribers):
    """Calculate View-to-Subscriber Ratio."""
    try:
        views = int(views) if views is not None else 0
        subscribers = int(subscribers) if subscribers is not None else 0
        return round(views / subscribers, 2) if subscribers > 0 else 0  # Avoid division by zero
    except (ValueError, TypeError):
        return 0  

def calculate_view_velocity(video):
    """Estimate how fast a video is gaining views (views per day)."""
    try:
        views = int(video.get("views", 0))
        upload_date_str = video.get("upload_date", "")
        
        if not upload_date_str:
            return 0  
        
        upload_date = datetime.fromisoformat(upload_date_str.replace("Z", "+00:00"))
        days_since_upload = max((datetime.now(timezone.utc) - upload_date).days, 1)  # Avoid division by zero
        return round(views / days_since_upload, 2)
    except (ValueError, TypeError):
        return 0  

def calculate_engagement_rate(video):
    """Calculate the engagement rate (Likes + Comments) / Views * 100."""
    try:
        likes = int(video.get("likes", 0))
        comments = int(video.get("comments", 0))
        views = int(video.get("views", 1))  
        
        return round(((likes + comments) / views) * 100, 2) if views > 0 else 0
    except (ValueError, TypeError):
        return 0  
