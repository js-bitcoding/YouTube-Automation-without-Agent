import uuid
import os
from fastapi import HTTPException, Depends
from datetime import datetime
from sqlalchemy.orm import Session
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any
import time
from langchain_chroma import Chroma

from controllers.chromadb_controller import ChromaDBController
from utils.embedding_utils import (
    get_txt_embedding,
    get_query_embedding,
)
from utils.file_processing import (
    process_text_file,
    process_pdf_to_text,
    process_doc_to_text
)
from database.models import YouTubeVideo, Document, timezone
from database.db_connection import get_db, SessionLocal
from utils.logging_utils import setup_logging
from service.script_service import fetch_transcript
from langchain_ollama import OllamaEmbeddings

embedding_function = OllamaEmbeddings(model="nomic-embed-text")
logger = setup_logging()

def get_controller(username: str, collection_name: str = None) -> ChromaDBController:
    """
    Get or create a ChromaDB controller for a specific user's collection
    
    Args:
        collection_name (str): Base collection name
        username (str): Username for creating user-specific collection
    
    Returns:
        ChromaDBController: Controller instance for the user's collection
    """
    if not collection_name and not username:
        logger.error(f"Invalid parameters: collection_name={collection_name}, username={username}")
        raise HTTPException(status_code=400, detail="Collection name or username is missing.")
    
    try:
        return ChromaDBController(username=username, collection_name=collection_name)
    except Exception as e:
        logger.error(f"Failed to get controller: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={"message": "Failed to get controller", "reason": str(e)}
        )

def handle_add_embedding(file_path: str, file_type: str, collection_name: str, username: str, summary: str = None):
    """
    Handles embedding generation and storage in ChromaDB.
 
    Args:
        file_path (str): Path to the file to be embedded
        file_type (str): Type of file ('image', 'text', 'excel', 'csv', 'pdf', 'doc')
        collection_name (str): Name of the ChromaDB collection to store embeddings
        summary (str, optional): Summary text for PDF or DOC files. Defaults to None.
 
    Returns:
        dict: Response containing either:
            - Success: {"message": "Embedding and document stored successfully", "id": item_id}
            - Error: {"error": error_message}
    """
    try:
        controller = get_controller(collection_name=collection_name, username=username)
        item_id = str(uuid.uuid4())
       
        try:
            if file_type == "txt":
                document_chunks = process_text_file(file_path)
                document_chunks, embedding = get_txt_embedding(document_chunks)
            elif file_type == "pdf":
                document_chunks = process_pdf_to_text(file_path, summary)
                document_chunks, embedding = get_txt_embedding(document_chunks)
            elif file_type == "docx" or file_type == "doc":
                document_chunks = process_doc_to_text(file_path, summary)
                document_chunks, embedding = get_txt_embedding(document_chunks)
            else:
                raise HTTPException(status_code=400,detail={"message": "Unsupported file type","reason": "The provided file type is not supported"})
        except HTTPException as e:
            raise e
        except Exception as e:
            logger.error(f"Error processing file: {str(e)}")
            raise HTTPException(status_code=500,detail={"message": "Error processing file","reason": str(e)})
        try:
            metadata = {
            "filename": file_path,
            "type": file_type,
            }
            documents = [str(doc) for doc in document_chunks]
            ids = [f"{item_id}_{i}" for i in range(len(document_chunks))]
            metadatas=[metadata for _ in document_chunks]
 
            response = controller.add_items(embedding, documents, metadatas, ids)

            new_doc = Document(
                filename=os.path.basename(file_path),
                content="\n".join(document_chunks),
                group_id=int(collection_name.split("_")[-1]),
                tone=None,
                style=None,
                created_at=timezone,
                is_deleted=False
            )
            db_session = SessionLocal()
            db_session.add(new_doc)
            db_session.commit()
            db_session.close()
            return {"message": "Embeddings and In database document stored successfully", "id": response}
        except HTTPException as e:
            raise e
        except Exception as e:
            logger.error(f"Error storing in ChromaDB: {str(e)}")
            raise HTTPException(status_code=500,detail={"message": "Error storing in ChromaDB","reason": str(e)})
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error initializing ChromaDB controller: {str(e)}")
        raise HTTPException(status_code=500,detail={"message": "Error initializing ChromaDB controller","reason": str(e)})
    
def handle_add_embedding_youtube(
        youtube_url: str, 
        collection_name: str, 
        username: str, 
        summary: str,
        group_id: int,
        db_session: Session = Depends(get_db),
        ):
    """
    Embeds a YouTube link into vector database collection.
    """
    try:
        extracted_text, error = fetch_transcript(youtube_url)

        if error:
            logger.error(f"Failed to fetch transcript: {error}")
            return {"error": error}

        if not extracted_text:
            logger.error(f"No transcript text extracted from YouTube URL: {youtube_url}")
            return {"error": "No transcript text extracted."}
        
        logger.info(f"Transcript length: {len(extracted_text)} characters")
        
        db = Chroma(
            persist_directory="chroma_data",
            collection_name=collection_name,
            embedding_function=embedding_function
        )

        try:
            collection = db.get_collection(name=collection_name)
            logger.info(f"Collection {collection_name} already exists in Chroma.")
        except Exception:
            logger.info(f"Collection {collection_name} not found, creating new collection.")
            db.create_collection(name=collection_name, metadata={"project": "group_data"})
            collection = db.get_collection(name=collection_name)

        logger.info(f"Attempting to add text to Chroma in collection: {collection_name}")
        collection.add(
            documents=[extracted_text],
            metadatas=[{
                "video_source": "youtube",
                "video_url": youtube_url,
                "uploaded_by": username,
                "video_summary": summary
            }],
            ids=[youtube_url]
        )
        logger.info(f"Successfully added YouTube content to Chroma: {youtube_url}")
        new_video = YouTubeVideo(
            url=youtube_url,
            transcript=extracted_text,
            tone=None,
            style=None,
            created_at=timezone,
            is_deleted=False,
            group_id=group_id
        )
        db_session.add(new_video)
        db_session.commit()

        logger.info(f"Transcript also saved in PostgreSQL for video: {youtube_url}")

        return {"success": True}
    
    except Exception as e:
        return {"error": str(e)}
        
def handle_query_embedding(
    query: str, 
    collection_names: List[str],
    username: str,
    num_results: int = 5,
    similarity_threshold: float = 0.5,
    timeout: float = 10.0
) -> List[Dict[str, Any]]:
    """
    Queries the stored embeddings in user-specific ChromaDB collections
    """
    if isinstance(collection_names, list) and len(collection_names) == 1:
        collection_names = collection_names[0] if isinstance(collection_names[0], str) else collection_names[0][0]
    if isinstance(collection_names, str):
        collection_names = [collection_names]

    try:
        target_dimension = 1536
        try:
            if collection_names:
                controller = get_controller(collection_name=collection_names[0], username=username)
                if hasattr(controller.collection, 'dimension'):
                    target_dimension = controller.collection.dimension
        except Exception as e:
            logger.warning(f"Could not determine collection dimension, using default: {str(e)}")

        question_embedding = get_query_embedding(query, target_dimension)
    except Exception as e:
        logger.error(f"Failed to generate query embedding: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail={"message": "Failed to generate query embedding", "reason": str(e)}
        )

    def query_single_collection(collection_name: str) -> Dict[str, Any]:
        try:
            controller = get_controller(collection_name=collection_name, username=username)
            results = controller.query_items(question_embedding)

            logger.debug(f"Raw results from ChromaDB: {results}")
            
            if not results or not isinstance(results, dict):
                logger.warning(f"Unexpected results format for collection {collection_name}: {results}")
                return {
                    "collection_name": collection_name,
                    "results": {
                        'ids': [[]],
                        'distances': [[]],
                        'metadatas': [[]],
                        'documents': [[]]
                    },
                    "error": "Empty or invalid results"
                }

            if 'distances' not in results or not results['distances']:
                logger.warning(f"No distances in results for collection {collection_name}")
                return {
                    "collection_name": collection_name,
                    "results": results,
                    "error": None
                }

            if not results['distances'][0]:
                return {
                    "collection_name": collection_name,
                    "results": results,
                    "error": None
                }

            filtered_indices = [
                i for i, distance in enumerate(results['distances'][0])
                if (1 - distance) >= similarity_threshold
            ]

            if not filtered_indices:
                logger.warning(f"No results passed similarity threshold {similarity_threshold}")
                return {
                    "collection_name": collection_name,
                    "results": results,
                    "error": None
                }

            return {
                "collection_name": collection_name,
                "results": results,
                "error": None
            }
        except Exception as e:
            logger.warning(f"Failed to query collection {collection_name}: {str(e)}")
            return {
                "collection_name": collection_name,
                "results": {
                    'ids': [[]],
                    'distances': [[]],
                    'metadatas': [[]],
                    'documents': [[]]
                },
                "error": str(e)
            }

    try:
        query_results = []
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=min(len(collection_names), 5)) as executor:
            future_to_collection = {
                executor.submit(query_single_collection, name): name 
                for name in collection_names
            }
            
            for future in as_completed(future_to_collection):
                if time.time() - start_time > timeout:
                    raise TimeoutError(f"Operation exceeded {timeout} seconds")
                
                result = future.result()
                if not result["error"]:
                    query_results.append(result)

        if not query_results:
            logger.warning("No results found in any collection")
            return []

        if len(query_results) == 1:
            return query_results

        try:
            sorted_results = sorted(
                query_results,
                key=lambda x: min(x['results']['distances'][0]) if (x['results'] and 
                                                                    'distances' in x['results'] and 
                                                                    x['results']['distances'] and 
                                                                    x['results']['distances'][0]) else float('inf'),
                reverse=False
            )
            return sorted_results
        except Exception as e:
            logger.warning(f"Failed to sort results: {str(e)}, returning unsorted")
            return query_results

    except TimeoutError as e:
        logger.error("Query timed out")
        raise HTTPException(
            status_code=408,
            detail={"message": "Query timed out", "reason": str(e)}
        )
    except Exception as e:
        logger.error(f"Failed to query ChromaDB: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={"message": "Failed to query ChromaDB", "reason": str(e)}
        )

def handle_check_filename_exists(file_path: str, collection_name: str, username: str) -> bool:
    """
    Checks if a file name already exists in the ChromaDB collection's metadata.

    Args:
        file_path (str): The file path to check
        collection_name (str): Name of the ChromaDB collection to check
        username (str): Username associated with the collection

    Returns:
        bool: True if the file exists, False otherwise
    """
    try:
        controller = get_controller(collection_name=collection_name, username=username)
        exists = controller.check_file_exists(file_path)
        return exists
    except Exception as e:
        logger.error(f"Error checking file existence for user {username}: {e}")
        raise HTTPException(status_code=500, detail={"message": "Failed to check file existence", "reason": str(e)})

def handle_get_file_data(collection_name: str, file_name: str, username: str):
    """
    Get all data for a specific file from the user's collection.

    Args:
        collection_name (str): Name of the ChromaDB collection
        file_name (str): Name of the file to retrieve data for
        username (str): Username associated with the collection

    Returns:
        dict: File data from the collection or error message if retrieval fails
    """
    try:
        controller = get_controller(collection_name=collection_name, username=username)
        result = controller.get_file_data(file_name)
        logger.info(f"Successfully retrieved data for file: {file_name} for user {username}")
        return result
    except Exception as e:
        logger.error(f"Error retrieving file data for {file_name} for user {username}: {str(e)}")
        raise HTTPException(status_code=500, detail={"message": "Failed to retrieve file data", "reason": str(e)})

def handle_get_all_file_data(collection_name: str, username: str):
    """
    Get all file data from the user's collection.

    Args:
        collection_name (str): Name of the ChromaDB collection
        username (str): Username associated with the collection

    Returns:
        dict: All file data from the collection or error message if retrieval fails
    """
    try:
        controller = get_controller(collection_name=collection_name, username=username)
        result = controller.get_all_file_data()
        logger.info(f"Successfully retrieved all file data from collection: {collection_name} for user {username}")
        return result
    except Exception as e:
        logger.error(f"Error retrieving all file data for user {username}: {str(e)}")
        raise HTTPException(status_code=500, detail={"message": "Failed to retrieve all file data", "reason": str(e)})

def handle_delete_file_data(collection_name: str, file_name: str, username: str):
    """
    Delete file data from the user's collection.

    Args:
        collection_name (str): Name of the ChromaDB collection
        file_name (str): Name of the file to delete
        username (str): Name of the user (for user-specific collections)

    Returns:
        dict: Response indicating success or failure of deletion
    """
    try:
        controller = get_controller(collection_name=collection_name, username=username)
        result = controller.delete_items_by_filename(file_name)
        logger.info(f"Successfully deleted file data for {file_name} in {collection_name} for user {username}")
        return result
    except Exception as e:
        logger.error(f"Error deleting file data for {file_name} in {collection_name} for user {username}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={"message": "Failed to delete file data", "reason": str(e)}
        )

def handle_delete_collection(collection_name: str, username: str) -> dict:
    """
    Handles the deletion of a user's ChromaDB collection.

    Args:
        collection_name (str): Name of the ChromaDB collection to delete.
        username (str): Username for user-specific collections.

    Returns:
        dict: Response containing either:
            - Success message confirming collection deletion
            - Error message if deletion fails
    """
    try:
        controller = get_controller(collection_name=collection_name, username=username)
        result = controller.delete_collection(collection_name)
        logger.info(f"Successfully deleted collection: {collection_name} for user {username}")
        return result
    except Exception as e:
        logger.error(f"Error deleting collection {collection_name} for user {username}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={"message": "Failed to delete collection", "reason": str(e)}
        )

def handle_get_collections(username: str) -> dict:
    """
    Retrieves the list of available collection names from ChromaDB.

    Args:
        collection_name (str): The name of the collection.
        username (str): The username for the collection.

    Returns:
        dict: Response containing the list of collections.
    """
    try:
        controller = get_controller(username=username)
        collections = controller.list_collections(username=username)
        collections_list = [collection.name for collection in collections]
        return {"collections": collections_list}
    except Exception as e:
        logger.error(f"Failed to retrieve collections: {str(e)}")
        raise HTTPException(status_code=500, detail={"message": "Failed to retrieve collections", "reason": str(e)})

def handle_delete_all_collection_data(collection_name: str, username: str) -> dict:
    """
    Deletes all data from the specified ChromaDB collection while keeping the collection itself.

    Args:
        collection_name (str): Name of the ChromaDB collection to clear
        username (str): Username associated with the collection

    Returns:
        dict: Response containing either:
            - Success message confirming data deletion
            - Error message if deletion fails
    """
    try:
        controller = get_controller(collection_name=collection_name, username=username)
        controller.delete_all_data(collection_name)
        logger.info(f"Successfully deleted all data from collection: {collection_name}")
        return {"message": f"All data deleted from collection {collection_name}"}
    except Exception as e:
        logger.error(f"Error deleting all data from collection {collection_name}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={"message": "Failed to delete collection data", "reason": str(e)}
        )

def handle_delete_collection(collection_name: str, username: str) -> dict:
    """
    Handles the deletion of a user's ChromaDB collection.

    Args:
        collection_name (str): Name of the ChromaDB collection to delete.
        username (str): Username for user-specific collections.

    Returns:
        dict: Response containing either:
            - Success message confirming collection deletion
            - Error message if deletion fails
    """
    try:
        controller = get_controller(collection_name=collection_name, username=username)
        result = controller.delete_collection(collection_name)
        logger.info(f"Successfully deleted collection: {collection_name} for user {username}")
        return result
    except Exception as e:
        logger.error(f"Error deleting collection {collection_name} for user {username}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={"message": "Failed to delete collection", "reason": str(e)}
        )

def handle_get_collections(username: str) -> dict:
    """
    Retrieves the list of available collection names from ChromaDB.

    Args:
        collection_name (str): The name of the collection.
        username (str): The username for the collection.

    Returns:
        dict: Response containing the list of collections.
    """
    try:
        controller = get_controller(username=username)
        collections = controller.list_collections(username=username)
        collections_list = [collection.name for collection in collections]
        return {"collections": collections_list}
    except Exception as e:
        logger.error(f"Failed to retrieve collections: {str(e)}")
        raise HTTPException(status_code=500, detail={"message": "Failed to retrieve collections", "reason": str(e)})

def handle_delete_all_collection_data(collection_name: str, username: str) -> dict:
    """
    Deletes all data from the specified ChromaDB collection while keeping the collection itself.

    Args:
        collection_name (str): Name of the ChromaDB collection to clear
        username (str): Username associated with the collection

    Returns:
        dict: Response containing either:
            - Success message confirming data deletion
            - Error message if deletion fails
    """
    try:
        controller = get_controller(collection_name=collection_name, username=username)
        controller.delete_all_data(collection_name)
        logger.info(f"Successfully deleted all data from collection: {collection_name}")
        return {"message": f"All data deleted from collection {collection_name}"}
    except Exception as e:
        logger.error(f"Error deleting all data from collection {collection_name}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={"message": "Failed to delete collection data", "reason": str(e)}
        )
    