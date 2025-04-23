from sqlalchemy.orm import Session
from database.models import YouTubeVideo, Document

def upload_knowledge(db: Session, group_id: int, youtube_links: list, document_names: list):
    for link in youtube_links:
        db.add(YouTubeVideo(group_id=group_id, url=link))
    for name in document_names:
        db.add(Document(group_id=group_id, name=name))
    db.commit()
    return {"status": "uploaded"}