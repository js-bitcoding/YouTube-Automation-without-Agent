from functionality.current_user import get_current_user
from database.schemas import GetFileDataRequest, DeleteFileDataRequest
from utils.logging_utils import setup_logging
from fastapi import APIRouter, Depends, HTTPException
from handlers.chromadb_handlers import handle_check_filename_exists, handle_get_file_data, handle_get_all_file_data, handle_delete_file_data

logger = setup_logging()

file_router = APIRouter()

@file_router.get("/get_file_data")
async def get_file_data(
    request: GetFileDataRequest,
    user: dict = Depends(get_current_user)
):
    """Retrieve file data from the database.

    Args:
        collection_name (str, optional): Name of the collection to query. Defaults to "example_collection".
        file_name (str, optional): Specific file to retrieve data for. Defaults to "".
        request (GetFileDataRequest): Request model containing collection_name and file_name.
        user (dict): The authenticated user details.

    Returns:
        Dict: File data from the database or an error message.

    Raises:
        HTTPException: If the file doesn't exist in the database or another error occurs.
    """

    username = request.username
    
    if not username:
        logger.error("Username is missing in the request context.")
        raise HTTPException(status_code=400, detail="Invalid user. Username is missing.")

    collection_name = request.collection_name

    try:
        if request.file_name:
            file_name = request.file_name
            if not handle_check_filename_exists(file_name, collection_name, username):
                raise HTTPException(status_code=404, detail=f"File {file_name} not found in collection {collection_name}")
            response = handle_get_file_data(collection_name, file_name, username)
        else:
            response = handle_get_all_file_data(collection_name, username)

        if "error" in response:
            raise HTTPException(status_code=500, detail=response["error"])

        logger.info(f"Successfully retrieved file data from collection {collection_name} for user {username}")
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving file data from collection {collection_name} for user {username}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@file_router.delete("/delete_file_data")
async def delete_file_data(
    request: DeleteFileDataRequest,
    user: dict = Depends(get_current_user)
):
    """Delete file data from the database.

    Args:
        collection_name (str): Collection containing the file.
        file_name (str): Name of file to delete.

    Returns:
        Dict: Success message or error details.

    Raises:
        HTTPException: If the file doesn't exist in the database.
    """
    username = request.username
    collection_name = request.collection_name
    file_name = request.file_name

    if not username:
        raise HTTPException(status_code=400, detail="Invalid user. Username is missing.")

    try:
        if not handle_check_filename_exists(file_name, collection_name, username):
            logger.warning(f"File {file_name} not found in collection {collection_name} for user {username}")
            raise HTTPException(
                status_code=404,
                detail={"error": "File does not exist in database", "status_code": 404}
            )

        response = handle_delete_file_data(collection_name, file_name, username)
        logger.info(f"Successfully deleted file {file_name} for user {username}")

        return {"message": f"Successfully deleted file {file_name} from collection {collection_name} for user {username}", "status_code": 200}

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error deleting file data from collection {collection_name} for user {username}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={"error": str(e), "status_code": 500}
        )
