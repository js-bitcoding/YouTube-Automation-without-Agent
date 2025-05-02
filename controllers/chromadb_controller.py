"""
ChromaDB Controller Module

This module provides a controller class for interacting with ChromaDB, 
a vector database for storing and querying document embeddings.

Classes:
    ChromaDBController: Manages interactions with ChromaDB including adding, querying, 
                        and managing document embeddings and metadata.
"""
import os
import chromadb
from typing import List, Dict, Optional
from fastapi import HTTPException

from utils.logging_utils import setup_logging

logger = setup_logging()

class ChromaDBController:
    """
    A controller class for managing ChromaDB operations.

    This class provides methods for interacting with ChromaDB collections, including
    adding documents, querying embeddings, and managing file metadata.

    Attributes:
        host (str): The hostname where ChromaDB is running
        port (int): The port number for ChromaDB connection
        client (HttpClient): ChromaDB HTTP client instance
        collection: ChromaDB collection instance
    """
    def __init__(self, username: str, collection_name: str = None):
            """
            Initialize ChromaDB controller with user-specific collection
            """
            organization = username.split('@')[1] if '@' in username else 'default'

            db_path = f"./chroma_db/{organization}"
            print("db_path :: ", db_path)
            os.makedirs(db_path, exist_ok=True)
            
            self.client = chromadb.PersistentClient(path=db_path)

            if isinstance(collection_name, list):
                collection_name = collection_name[0]

            self.collection_name = collection_name

            if self.collection_name:
                self.collection = self.client.get_or_create_collection(name=self.collection_name)
            else:
                self.collection = None
        
    def list_collections(self, username: str):
        """
        List collections specific to a user based on their organization.
        """
        try:
            organization = username.split('@')[1] if '@' in username else 'default'
            db_path = f"./chroma_db/{organization}"

            user_client = chromadb.PersistentClient(path=db_path)

            collections = user_client.list_collections()
            return collections
        except Exception as e:
            logger.error(f"Failed to retrieve collections for {username}: {e}")
            raise HTTPException(
                status_code=500,
                detail={
                    "message": f"Failed to retrieve collections for {username}",
                    "reason": str(e)
                }
            )

    def add_items(self, embeddings: list, documents: list, metadatas: list, ids: list):
        """Add items to the collection"""
        self.collection.add(
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        
    def query_items(self, embedding: list) -> dict:
        """Query items from the collection"""
        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=10,
            include=["documents", "metadatas", "distances"]
        )
        return results

    def delete_items_by_filename(self, filename: str) -> str:
        """
        Delete all items from the collection with matching filename.

        Args:
            filename (str): Name of the file to delete

        Returns:
            str: Success or error message
        """
        try:
            filter_condition = {"filename": filename}
            
            self.collection.delete(where=filter_condition)
            return ({"message" : f"Items with filename '{filename}' deleted successfully."})
        except Exception as e:
            logger.error(f"Error deleting items with filename '{filename}': {e}")
            raise HTTPException(status_code=500,detail={"message": "Failed to delete items","reason": str(e)})
    
    def check_file_exists(self, file_path: str) -> bool:
        """
        Check if a file exists in the collection by comparing filenames.

        Args:
            file_path (str): The file path to check

        Returns:
            bool: True if the file exists, False otherwise
        """
        try:
            filename = os.path.basename(file_path)
            
            results = self.collection.get()
            
            if results and 'metadatas' in results:
                for metadata in results['metadatas']:
                    if metadata.get('filename') == filename:
                        return True
            return False
            
        except Exception as e:
            logger.error(f"Error checking file existence: {e}")
            raise HTTPException(status_code=500,detail={"message": "Failed to check file existence","reason": str(e)})

    def get_file_data(self, file_name: str) -> Optional[List[Dict]]:
        """
        Get metadata and document count for a specific file.

        Args:
            file_name (str): Name of the file to retrieve data for

        Returns:
            Optional[List[Dict]]: List containing file metadata and document count,
                                or None if file not found or error occurs
        """
        try:
            results =  self.collection.get(where={"filename": file_name})
            if results and 'metadatas' in results and 'documents' in results:
                metadata = [item for item in results['metadatas'] if item.get('filename') == file_name]
                document_count = len(results['documents'])
                filename = metadata[0].get('filename')
                file_type = metadata[0].get('type')
                is_external = metadata[0].get('is_external')
                return [{"filename": filename, "type": file_type, "document_count": document_count, "is_external": is_external}]
            return None
        except Exception as e:
            logger.error(f"Error retrieving file metadata and document count: {e}")
            raise HTTPException(status_code=500,detail={"message": "Failed to retrieve file metadata and document count","reason": str(e)})
    
    def get_all_file_data(self) -> Optional[List[Dict]]:
        """
        Get a summary of all files in the collection.

        Returns:
            Optional[List[Dict]]: List of dictionaries containing file summaries
                                (filename, type, document count) or None if error occurs
        """
        try:
            results = self.collection.get()
            
            if not results or 'metadatas' not in results or 'documents' not in results:
                raise HTTPException(status_code=500,detail={"message": "No documents found in the collection","reason": "No documents found in the collection"})
                
            if len(results['metadatas']) == 0:
                raise HTTPException(status_code=500,detail={"message": "Collection is empty","reason": "Collection is empty"})
                
            file_summaries = {}
            
            for metadata, document in zip(results['metadatas'], results['documents']):
                filename = metadata.get('filename')
                file_type = metadata.get('type')
                is_external = metadata.get('is_external')
                if filename not in file_summaries:
                    file_summaries[filename] = {'type': file_type, 'document_count': 0, 'is_external': is_external}
                file_summaries[filename]['document_count'] += 1
            
            summary_list = [
                {"filename": filename, "type": data['type'], "document_count": data['document_count'], "is_external": data['is_external']}
                for filename, data in file_summaries.items()
            ]
            
            return summary_list

        except Exception as e:
            logger.error(f"Error retrieving file summaries: {e}")
            raise HTTPException(status_code=500,detail={"message": "Failed to retrieve file summaries","reason": str(e)})

    def delete_items_by_filename(self, filename: str) -> str:
        """
        Delete all items from the collection with matching filename.

        Args:
            filename (str): Name of the file to delete

        Returns:
            str: Success or error message
        """
        try:
            filter_condition = {"filename": filename}
            
            self.collection.delete(where=filter_condition)
            return ({"message" : f"Items with filename '{filename}' deleted successfully."})
        except Exception as e:
            logger.error(f"Error deleting items with filename '{filename}': {e}")
            raise HTTPException(status_code=500,detail={"message": "Failed to delete items","reason": str(e)})

    def delete_collection(self, collection_name: str) -> Dict[str, str]:
        """
        Delete a collection from ChromaDB by its name.

        Args:
            collection_name (str): Name of the collection to delete

        Returns:
            Dict[str, str]: Response dictionary with success/error message
        """
        try:
            self.client.delete_collection(collection_name)
            return {"message": f"Collection '{collection_name}' deleted successfully"}
        except Exception as e:
            logger.error(f"Failed to delete collection '{collection_name}': {str(e)}")
            raise HTTPException(status_code=500,detail={"message": "Failed to delete collection","reason": str(e)})

    def delete_all_data(self, collection_name: str) -> Dict[str, str]:
        """
        Delete all data from the current collection.

        Returns:
            Dict[str, str]: Response dictionary with success/error message
        """
        try:
            self.client.delete_collection(name=self.collection_name)
            self.collection = self.client.create_collection(name=self.collection_name)
            return {"message": f"All data from collection '{collection_name}' deleted successfully"}
        except Exception as e:
            logger.error(f"Failed to delete all data from collection: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail={"message": "Failed to delete all data from collection", "reason": str(e)}
            )