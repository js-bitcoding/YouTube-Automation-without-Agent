import os
from functionality.current_user import get_current_user
from utils.logging_utils import setup_logging
from utils.file_processing import  save_base64_file
from fastapi import APIRouter, Depends, HTTPException
from database.schemas import VectorDataStoreRequest
from handlers.chromadb_handlers import handle_check_filename_exists, handle_add_embedding

logger = setup_logging()

router = APIRouter()

@router.post("/vector_data_store")
async def store_vector_data(
    request: VectorDataStoreRequest, 
    user: dict = Depends(get_current_user)
    ):
    """
    Stores a document as a vector embedding and uploads it to a storage system.

    Args:
        request (VectorDataStoreRequest): Request object containing the document (Base64), filename, collection name, username, and summary.
        user (dict, optional): Authenticated user information retrieved via dependency injection.

    Returns:
        dict: A dictionary containing:
            - "message" (str): Confirmation that the document was stored successfully.
            - "filename" (str): The name of the stored document.
            - "collection_name" (str): The collection where the document was stored.

    Raises:
        HTTPException: If file processing, uploading, or embedding creation fails.
    """

    summary = request.summary
    try:
        if handle_check_filename_exists(request.filename, request.collection_name, request.username):
            logger.warning(f"File {request.filename} already exists in collection {request.collection_name}")
 
        success = save_base64_file(request.document, request.filename)        
        if not success:
                raise HTTPException(status_code=500,detail={"message": "File processing failed","reason": "Failed to save base64 file"})  
        try:
            file_extension = os.path.splitext(request.filename)[1].lower().lstrip(".")
 
            response = handle_add_embedding(request.filename, file_extension, request.collection_name, request.username, summary)
 
            if "error" in response:
                raise HTTPException(status_code=500,detail={"message": "Embedding creation failed","reason": response["error"]})
        except HTTPException as e:
                raise e
        except Exception as e:
            logger.error(f"Error adding embedding to file {request.filename} in collection {request.collection_name}: {str(e)}")
            raise HTTPException(status_code=500,detail={"message": "Embedding creation failed","reason": str(e)})
        os.remove(request.filename)
        return {
            "message": "Document stored successfully",
            "filename": request.filename,
            "collection_name": request.collection_name
        }
 
    except Exception as e:
        logger.error(f"Failed to store document: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={"message": "Failed to store document", "reason": str(e)}
        )
