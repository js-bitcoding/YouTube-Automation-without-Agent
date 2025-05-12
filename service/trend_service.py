from sqlalchemy.orm import Session
from utils.logging_utils import logger
from service.utils import extract_keywords
from database.models import Video,TrendingTopic
from sqlalchemy.dialects.postgresql import insert

def detect_trending_topics(videos:list, db: Session):
    """Detects trending keywords from video titles and stores them in the database."""
    trending_topics = {}

    for video in videos:
        video_id = video["video_id"]

        existing_video = db.query(Video).filter(Video.video_id == video_id).first()
        if not existing_video:
            logger.info(f"Skipping trending topic for video_id {video_id} as it does not exist in 'videos' table.")
            continue  

        keywords = extract_keywords(video["title"])
        for keyword in keywords:
            if keyword in trending_topics:
                trending_topics[keyword]["count"] += 1
            else:
                trending_topics[keyword] = {"count": 1, "video_id": video_id}

    for keyword, data in trending_topics.items():
        stmt = (
            insert(TrendingTopic)
            .values(video_id=data["video_id"], keyword=keyword, count=data["count"])  
            .on_conflict_do_update(
                index_elements=["keyword"],
                set_={"count": data["count"]}
            )
        )
        db.execute(stmt)

    db.commit()
    return sorted(trending_topics.items(), key=lambda x: x[1]["count"], reverse=True)
