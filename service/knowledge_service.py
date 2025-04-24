from sqlalchemy.orm import Session
from database.models import YouTubeVideo, Document

def upload_knowledge(db: Session, group_id: int, youtube_links: list, document_names: list):
    """
    Upload YouTube video links and document names to a specified group.

    This function processes and stores YouTube video links and document names associated with a particular group.

    Args:
        db (Session): The database session used to interact with the database.
        group_id (int): The ID of the group to which the videos and documents are associated.
        youtube_links (list): A list of YouTube video URLs to be uploaded.
        document_names (list): A list of document names to be uploaded.

    Returns:
        dict: A dictionary indicating the status of the upload, with a key "status" and value "uploaded".

    Raises:
        Exception: If there is an error in saving data to the database or any other unforeseen issue.
    """
    for link in youtube_links:
        db.add(YouTubeVideo(group_id=group_id, url=link))
    for name in document_names:
        db.add(Document(group_id=group_id, name=name))
    db.commit()
    return {"status": "uploaded"}