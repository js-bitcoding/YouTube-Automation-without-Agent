from datetime import datetime, timezone
from utils.logging_utils import logger
def calculate_view_to_subscriber_ratio(views:int, subscribers:int):
    """
    Calculate the View-to-Subscriber ratio.

    This function computes the ratio of views to subscribers, rounding it to two decimal places.
    If the number of subscribers is zero or invalid, it returns 0 to avoid division by zero errors.
    
    Args:
        views (int or float): The total number of views.
        subscribers (int or float): The total number of subscribers.
    
    Returns:
        float: The calculated View-to-Subscriber ratio, rounded to two decimal places. 
               Returns 0 if there are no subscribers or if input values are invalid.

    Raises:
        ValueError, TypeError: If the input values are not convertible to integers.
    """
    try:
        views = int(views) if views is not None else 0
        subscribers = int(subscribers) if subscribers is not None else 0
        return round(views / subscribers, 2) if subscribers > 0 else 0
    except (ValueError, TypeError) as e:
        logger.error(f"Error calculating View-to-Subscriber ratio. Views: {views}, Subscribers: {subscribers}. Error: {e}")
        return 0

def calculate_view_velocity(video:int):
    """
    Estimate how fast a video is gaining views (views per day).

    This function calculates the average number of views a video has gained per day since it was uploaded.
    It takes into account the video’s current view count and the time elapsed since its upload date.

    Args:
        video (dict): A dictionary containing video details. It should include:
            - "views" (int or str): The total number of views the video has.
            - "upload_date" (str): The ISO 8601 format string representing the upload date of the video.

    Returns:
        float: The estimated views per day (rounded to two decimal places). Returns 0 if there is an error
               (e.g., invalid data or missing fields).

    Raises:
        ValueError, TypeError: If the values in the dictionary are not valid or can't be converted correctly.
    """
    try:
        views = int(video.get("views", 0))
        upload_date_str = video.get("upload_date", "")
        
        if not upload_date_str:
            return 0  
        
        upload_date = datetime.fromisoformat(upload_date_str.replace("Z", "+00:00"))
        days_since_upload = max((datetime.now(timezone.utc) - upload_date).days, 1)
        return round(views / days_since_upload, 2)
    except (ValueError, TypeError):
        return 0  

def calculate_engagement_rate(video:int):
    """
    Calculate the engagement rate for a video as the percentage of likes and comments relative to views.

    The engagement rate is calculated by summing the likes and comments on a video, dividing by the total
    views, and multiplying by 100 to get a percentage.

    Args:
        video (dict): A dictionary containing video details. It should include:
            - "likes" (int or str): The total number of likes the video has received.
            - "comments" (int or str): The total number of comments the video has received.
            - "views" (int or str): The total number of views the video has received. 

    Returns:
        float: The engagement rate as a percentage, rounded to two decimal places.
               Returns 0 if there is an error or if the views are zero.

    Raises:
        ValueError, TypeError: If the values in the dictionary are not valid or can't be converted correctly.
    """
    try:
        likes = int(video.get("likes", 0))
        comments = int(video.get("comments", 0))
        views = int(video.get("views", 1))  
        
        return round(((likes + comments) / views) * 100, 2) if views > 0 else 0
    except (ValueError, TypeError) as e:
        logger.error(f"Error calculating engagement rate. Video details: {video}. Error: {e}")
        return 0  
