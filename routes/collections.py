from functionality.current_user import get_current_user
from fastapi import APIRouter, Depends
from utils.logging_utils import setup_logging
from fastapi import APIRouter, Depends, HTTPException
from database.schemas import DeleteAllCollectionDataRequest
from handlers.chromadb_handlers import handle_delete_all_collection_data, handle_delete_collection, handle_get_collections

logger = setup_logging()

collection_router = APIRouter()

@collection_router.get("/get_collections")
async def get_collections(
    username: str, 
    user: dict = Depends(get_current_user)
    ):
    """
    Retrieve the list of available collections from the database.
    """
    return handle_get_collections(username)

@collection_router.delete("/clear_collection")
async def clear_collection(
    request: DeleteAllCollectionDataRequest,
    user: dict = Depends(get_current_user)
):
    """
    Deletes all data from the specified collection.

    Args:
        request (DeleteAllCollectionDataRequest): Request object containing the collection name and username.
        user (dict, optional): Authenticated user information retrieved via dependency injection.

    Returns:
        HTTPException: HTTP response indicating success or failure.

    Raises:
        HTTPException: If an error occurs during deletion.
    """
    try:
        collection_name = request.collection_name
        username = request.username
        response = handle_delete_all_collection_data(collection_name, username)
        logger.info(f"Successfully deleted all data from collection {collection_name}")
        return HTTPException(status_code=200, detail={"message": f"Successfully deleted all data from collection {collection_name}", "status_code": 200})
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error deleting data from collection {collection_name}: {str(e)}")
        raise HTTPException(status_code=500, detail={"error": str(e), "status_code": 500})
    
@collection_router.delete("/delete_collection")
async def delete_collection(
    collection_name: str,
    username: str,
    user: dict = Depends(get_current_user)
):
    """Delete an entire collection from the database.

    Args:
        collection_name (str): Name of the collection to delete.
        user (dict): User information extracted from authentication.

    Returns:
        dict: Response dictionary containing success or error message.
        HTTPException: Response dictionary containing either:
            - {"message": str}: Success message if collection was deleted
            - {"error": str}: Error message if deletion failed

    Raises:
        HTTPException: If there's an error during collection deletion.
    """

    if not username:
        raise HTTPException(status_code=400, detail="Invalid user. Username is missing.")

    try:
        response = handle_delete_collection(collection_name, username)
        logger.info(f"Successfully deleted collection {collection_name} for user {username}")

        return {"message": f"Successfully deleted collection {collection_name} for user {username}", "status_code": 200}
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error deleting collection {collection_name} for user {username}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={"error": str(e), "status_code": 500}
        )
