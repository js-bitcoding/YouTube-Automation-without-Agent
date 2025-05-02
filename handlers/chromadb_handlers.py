# import uuid
# from fastapi import HTTPException
# from dotenv import load_dotenv
# from concurrent.futures import ThreadPoolExecutor, as_completed
# from typing import List, Dict, Any
# import time

# from controllers.chromadb_controller import ChromaDBController

# from utils.embedding_utils import (
#     get_txt_embedding,
#     get_query_embedding,
#     json_to_embeddings,
#     extract_metadata_urls_embeddings
# )
# from utils.file_processing import (
#     process_text_file,
#     split_into_chunks,
#     excel_to_json,
#     extract_urls_scraped_data,
#     save_html_to_text,
#     process_pdf_to_text,
#     process_doc_to_text
# )
# from utils.logging_utils import setup_logging

# load_dotenv(override=True)

# logger = setup_logging()

# def get_controller(username: str, collection_name: str = None) -> ChromaDBController:
#     """
#     Get or create a ChromaDB controller for a specific user's collection
    
#     Args:
#         collection_name (str): Base collection name
#         username (str): Username for creating user-specific collection
    
#     Returns:
#         ChromaDBController: Controller instance for the user's collection
#     """
#     if not collection_name and not username:
#         logger.error(f"Invalid parameters: collection_name={collection_name}, username={username}")
#         raise HTTPException(status_code=400, detail="Collection name or username is missing.")
    
#     try:
#         return ChromaDBController(username=username, collection_name=collection_name)
#     except Exception as e:
#         logger.error(f"Failed to get controller: {str(e)}")
#         raise HTTPException(
#             status_code=500,
#             detail={"message": "Failed to get controller", "reason": str(e)}
#         )

# def handle_add_embedding(file_path: str, file_type: str, collection_name: str, username: str, summary: str = None):
#     """
#     Handles embedding generation and storage in ChromaDB.
 
#     Args:
#         file_path (str): Path to the file to be embedded
#         file_type (str): Type of file ('image', 'text', 'excel', 'csv', 'pdf', 'doc')
#         collection_name (str): Name of the ChromaDB collection to store embeddings
#         summary (str, optional): Summary text for PDF or DOC files. Defaults to None.
 
#     Returns:
#         dict: Response containing either:
#             - Success: {"message": "Embedding and document stored successfully", "id": item_id}
#             - Error: {"error": error_message}
#     """
#     try:
#         controller = get_controller(collection_name=collection_name, username=username)
#         item_id = str(uuid.uuid4())
       
#         try:
#             if file_type == "txt":
#                 document_chunks = process_text_file(file_path)
#                 document_chunks, embedding = get_txt_embedding(document_chunks)
#             elif file_type == "csv" or file_type == "xlsx":
#                 json_data = excel_to_json(file_path)
#                 document_chunks, embedding = json_to_embeddings(json_data)
#             elif file_type == "pdf":
#                 document_chunks = process_pdf_to_text(file_path, summary)
#                 document_chunks, embedding = get_txt_embedding(document_chunks)
#             elif file_type == "docx" or file_type == "doc":
#                 document_chunks = process_doc_to_text(file_path, summary)
#                 document_chunks, embedding = get_txt_embedding(document_chunks)
#             else:
#                 raise HTTPException(status_code=400,detail={"message": "Unsupported file type","reason": "The provided file type is not supported"})
#         except HTTPException as e:
#             raise e
#         except Exception as e:
#             logger.error(f"Error processing file: {str(e)}")
#             raise HTTPException(status_code=500,detail={"message": "Error processing file","reason": str(e)})
#         try:
#             metadata = {
#             "filename": file_path,
#             "type": file_type,
#             }
#             documents = [str(doc) for doc in document_chunks]
#             ids = [f"{item_id}_{i}" for i in range(len(document_chunks))]
#             metadatas=[metadata for _ in document_chunks]
 
#             response = controller.add_items(embedding, documents, metadatas, ids)
           
#             return {"message": "Embedding and document stored successfully", "id": response}
#         except HTTPException as e:
#             raise e
#         except Exception as e:
#             logger.error(f"Error storing in ChromaDB: {str(e)}")
#             raise HTTPException(status_code=500,detail={"message": "Error storing in ChromaDB","reason": str(e)})
#     except HTTPException as e:
#         raise e
#     except Exception as e:
#         logger.error(f"Error initializing ChromaDB controller: {str(e)}")
#         raise HTTPException(status_code=500,detail={"message": "Error initializing ChromaDB controller","reason": str(e)})
    
# # async def handle_scraped_data_embedding(urls, collection_name):
# #     """
# #     Fetch scraped data, generate embeddings, and store them URL-wise in ChromaDB.

# #     Args:
# #         urls (list): List of URLs to fetch data from
# #         collection_name (str): Name of the ChromaDB collection

# #     Returns:
# #         dict: Response containing either:
# #             - Success: {"message": "Embeddings and documents stored successfully"}
# #             - Error: {"error": error_message}
# #     """
# #     try:
# #         controller = get_controller(collection_name=collection_name)
# #         file_type = "web_scrap"
# #         response = await fetch_scraped_data(urls)
# #     except Exception as e:
# #         raise HTTPException(
# #             status_code=500,
# #             detail={"message": "Failed to initialize scraping","reason": f"Error fetching scraped data: {str(e)}"})

# #     if response.get("status") != 200:
# #         raise HTTPException(status_code=response.get("status", 500),detail={"message": "Scraping service error","reason": response.get("error", "Unknown error occurred during scraping")})

# #     try:
# #         json_response = response.get("response")
# #         metadata_urls_embeddings = extract_metadata_urls_embeddings(json_response)
        
# #         raw_data_list, embeddings_list, extracted_urls = [], [], []
        
# #         for item in metadata_urls_embeddings:
# #             raw_data_list.append(item["raw_data"])
# #             embeddings_list.append(item["embedding"])
# #             extracted_urls.append(item["url"])

# #         stored_items = []
# #         for url, raw_data, embedding in zip(extracted_urls, raw_data_list, embeddings_list):
# #             item_id = str(uuid.uuid4())
# #             response = controller.add_item(item_id, url, file_type, raw_data, embedding)
# #             if "error" in response:
# #                 raise HTTPException(status_code=500,detail={"message": "Failed to store scraped data","reason": response["error"]})
# #             stored_items.append(response)
        
# #         page_urls, image_urls = extract_urls_scraped_data(json_response)
        
# #         for url in page_urls:
# #             item_id = str(uuid.uuid4())
# #             logger.info(f"Processing URL: {url}")
# #             extracted_text = await save_html_to_text(url)
# #             if extracted_text:
# #                 text_chunk = split_into_chunks(extracted_text)
# #                 document_chunks, embedding = get_txt_embedding(text_chunk)
# #                 is_external = collection_name.lower() not in url.lower()
# #                 response = controller.add_item(item_id, url, "page_url", document_chunks, embedding, is_external)
# #                 if "error" in response:
# #                     raise HTTPException(status_code=500,detail={"message": "Failed to store page URL data","reason": response["error"]})

# #         for url in image_urls:
# #             item_id = str(uuid.uuid4())
# #             logger.info(f"Processing Image: {url}")
# #             try:
# #                 image_description = get_image_description(url)
# #                 image_description_chunk = split_into_chunks(image_description)
# #                 document_chunks, embedding = get_txt_embedding(image_description_chunk)
# #                 is_external = collection_name.lower() not in url.lower()
# #                 response = controller.add_item(item_id, url, "image_url", document_chunks, embedding, is_external)
# #                 if "error" in response:
# #                     raise HTTPException(status_code=500,detail={"message": "Failed to store image data","reason": response["error"]})
# #             except Exception as e:
# #                 logger.warning(f"Failed to process image {url}: {str(e)}")
# #                 continue

# #         return {"message": "Embeddings and documents stored successfully"}
        
# #     except HTTPException as e:
# #         raise e
# #     except Exception as e:
# #         raise HTTPException(status_code=500,detail={"message": "Failed to process and store data","reason": str(e)})
        
# def handle_query_embedding(
#     query: str, 
#     collection_names: List[str],
#     username: str,
#     num_results: int = 5,
#     similarity_threshold: float = 0.5,
#     timeout: float = 10.0
# ) -> List[Dict[str, Any]]:
#     """
#     Queries the stored embeddings in user-specific ChromaDB collections
#     """
#     if isinstance(collection_names, list) and len(collection_names) == 1:
#         collection_names = collection_names[0] if isinstance(collection_names[0], str) else collection_names[0][0]
#     if isinstance(collection_names, str):
#         collection_names = [collection_names]

#     try:
#         target_dimension = 1536
#         try:
#             if collection_names:
#                 controller = get_controller(collection_name=collection_names[0], username=username)
#                 if hasattr(controller.collection, 'dimension'):
#                     target_dimension = controller.collection.dimension
#         except Exception as e:
#             logger.warning(f"Could not determine collection dimension, using default: {str(e)}")

#         question_embedding = get_query_embedding(query, target_dimension)
#     except Exception as e:
#         logger.error(f"Failed to generate query embedding: {str(e)}")
#         raise HTTPException(
#             status_code=500, 
#             detail={"message": "Failed to generate query embedding", "reason": str(e)}
#         )

#     def query_single_collection(collection_name: str) -> Dict[str, Any]:
#         try:
#             controller = get_controller(collection_name=collection_name, username=username)
#             results = controller.query_items(question_embedding)

#             logger.debug(f"Raw results from ChromaDB: {results}")
            
#             if not results or not isinstance(results, dict):
#                 logger.warning(f"Unexpected results format for collection {collection_name}: {results}")
#                 return {
#                     "collection_name": collection_name,
#                     "results": {
#                         'ids': [[]],
#                         'distances': [[]],
#                         'metadatas': [[]],
#                         'documents': [[]]
#                     },
#                     "error": "Empty or invalid results"
#                 }

#             if 'distances' not in results or not results['distances']:
#                 logger.warning(f"No distances in results for collection {collection_name}")
#                 return {
#                     "collection_name": collection_name,
#                     "results": results,
#                     "error": None
#                 }

#             if not results['distances'][0]:
#                 return {
#                     "collection_name": collection_name,
#                     "results": results,
#                     "error": None
#                 }

#             filtered_indices = [
#                 i for i, distance in enumerate(results['distances'][0])
#                 if (1 - distance) >= similarity_threshold
#             ]

#             if not filtered_indices:
#                 logger.warning(f"No results passed similarity threshold {similarity_threshold}")
#                 return {
#                     "collection_name": collection_name,
#                     "results": results,
#                     "error": None
#                 }

#             return {
#                 "collection_name": collection_name,
#                 "results": results,
#                 "error": None
#             }
#         except Exception as e:
#             logger.warning(f"Failed to query collection {collection_name}: {str(e)}")
#             return {
#                 "collection_name": collection_name,
#                 "results": {
#                     'ids': [[]],
#                     'distances': [[]],
#                     'metadatas': [[]],
#                     'documents': [[]]
#                 },
#                 "error": str(e)
#             }

#     try:
#         query_results = []
#         start_time = time.time()
        
#         with ThreadPoolExecutor(max_workers=min(len(collection_names), 5)) as executor:
#             future_to_collection = {
#                 executor.submit(query_single_collection, name): name 
#                 for name in collection_names
#             }
            
#             for future in as_completed(future_to_collection):
#                 if time.time() - start_time > timeout:
#                     raise TimeoutError(f"Operation exceeded {timeout} seconds")
                
#                 result = future.result()
#                 if not result["error"]:
#                     query_results.append(result)

#         if not query_results:
#             logger.warning("No results found in any collection")
#             return []

#         if len(query_results) == 1:
#             return query_results

#         try:
#             sorted_results = sorted(
#                 query_results,
#                 key=lambda x: min(x['results']['distances'][0]) if (x['results'] and 
#                                                                     'distances' in x['results'] and 
#                                                                     x['results']['distances'] and 
#                                                                     x['results']['distances'][0]) else float('inf'),
#                 reverse=False
#             )
#             return sorted_results
#         except Exception as e:
#             logger.warning(f"Failed to sort results: {str(e)}, returning unsorted")
#             return query_results

#     except TimeoutError as e:
#         logger.error("Query timed out")
#         raise HTTPException(
#             status_code=408,
#             detail={"message": "Query timed out", "reason": str(e)}
#         )
#     except Exception as e:
#         logger.error(f"Failed to query ChromaDB: {str(e)}")
#         raise HTTPException(
#             status_code=500,
#             detail={"message": "Failed to query ChromaDB", "reason": str(e)}
#         )

# def handle_check_filename_exists(file_path: str, collection_name: str, username: str) -> bool:
#     """
#     Checks if a file name already exists in the ChromaDB collection's metadata.

#     Args:
#         file_path (str): The file path to check
#         collection_name (str): Name of the ChromaDB collection to check
#         username (str): Username associated with the collection

#     Returns:
#         bool: True if the file exists, False otherwise
#     """
#     try:
#         controller = get_controller(collection_name=collection_name, username=username)
#         exists = controller.check_file_exists(file_path)
#         return exists
#     except Exception as e:
#         logger.error(f"Error checking file existence for user {username}: {e}")
#         raise HTTPException(status_code=500, detail={"message": "Failed to check file existence", "reason": str(e)})

# def handle_get_file_data(collection_name: str, file_name: str, username: str):
#     """
#     Get all data for a specific file from the user's collection.

#     Args:
#         collection_name (str): Name of the ChromaDB collection
#         file_name (str): Name of the file to retrieve data for
#         username (str): Username associated with the collection

#     Returns:
#         dict: File data from the collection or error message if retrieval fails
#     """
#     try:
#         controller = get_controller(collection_name=collection_name, username=username)
#         result = controller.get_file_data(file_name)
#         logger.info(f"Successfully retrieved data for file: {file_name} for user {username}")
#         return result
#     except Exception as e:
#         logger.error(f"Error retrieving file data for {file_name} for user {username}: {str(e)}")
#         raise HTTPException(status_code=500, detail={"message": "Failed to retrieve file data", "reason": str(e)})

# def handle_get_all_file_data(collection_name: str, username: str):
#     """
#     Get all file data from the user's collection.

#     Args:
#         collection_name (str): Name of the ChromaDB collection
#         username (str): Username associated with the collection

#     Returns:
#         dict: All file data from the collection or error message if retrieval fails
#     """
#     try:
#         controller = get_controller(collection_name=collection_name, username=username)
#         result = controller.get_all_file_data()
#         logger.info(f"Successfully retrieved all file data from collection: {collection_name} for user {username}")
#         return result
#     except Exception as e:
#         logger.error(f"Error retrieving all file data for user {username}: {str(e)}")
#         raise HTTPException(status_code=500, detail={"message": "Failed to retrieve all file data", "reason": str(e)})

# def handle_delete_file_data(collection_name: str, file_name: str, username: str):
#     """
#     Delete file data from the user's collection.

#     Args:
#         collection_name (str): Name of the ChromaDB collection
#         file_name (str): Name of the file to delete
#         username (str): Name of the user (for user-specific collections)

#     Returns:
#         dict: Response indicating success or failure of deletion
#     """
#     try:
#         controller = get_controller(collection_name=collection_name, username=username)
#         result = controller.delete_items_by_filename(file_name)
#         logger.info(f"Successfully deleted file data for {file_name} in {collection_name} for user {username}")
#         return result
#     except Exception as e:
#         logger.error(f"Error deleting file data for {file_name} in {collection_name} for user {username}: {str(e)}")
#         raise HTTPException(
#             status_code=500,
#             detail={"message": "Failed to delete file data", "reason": str(e)}
#         )

# def handle_delete_collection(collection_name: str, username: str) -> dict:
#     """
#     Handles the deletion of a user's ChromaDB collection.

#     Args:
#         collection_name (str): Name of the ChromaDB collection to delete.
#         username (str): Username for user-specific collections.

#     Returns:
#         dict: Response containing either:
#             - Success message confirming collection deletion
#             - Error message if deletion fails
#     """
#     try:
#         controller = get_controller(collection_name=collection_name, username=username)
#         result = controller.delete_collection(collection_name)
#         logger.info(f"Successfully deleted collection: {collection_name} for user {username}")
#         return result
#     except Exception as e:
#         logger.error(f"Error deleting collection {collection_name} for user {username}: {str(e)}")
#         raise HTTPException(
#             status_code=500,
#             detail={"message": "Failed to delete collection", "reason": str(e)}
#         )

# def handle_get_collections(username: str) -> dict:
#     """
#     Retrieves the list of available collection names from ChromaDB.

#     Args:
#         collection_name (str): The name of the collection.
#         username (str): The username for the collection.

#     Returns:
#         dict: Response containing the list of collections.
#     """
#     try:
#         controller = get_controller(username=username)
#         collections = controller.list_collections(username=username)
#         # collections_list = [str(collection) for collection in collections]
#         collections_list = [collection.name for collection in collections]
#         return {"collections": collections_list}
#         # return {"collections": collections}
#     except Exception as e:
#         logger.error(f"Failed to retrieve collections: {str(e)}")
#         raise HTTPException(status_code=500, detail={"message": "Failed to retrieve collections", "reason": str(e)})

# def handle_delete_all_collection_data(collection_name: str, username: str) -> dict:
#     """
#     Deletes all data from the specified ChromaDB collection while keeping the collection itself.

#     Args:
#         collection_name (str): Name of the ChromaDB collection to clear
#         username (str): Username associated with the collection

#     Returns:
#         dict: Response containing either:
#             - Success message confirming data deletion
#             - Error message if deletion fails
#     """
#     try:
#         controller = get_controller(collection_name=collection_name, username=username)
#         controller.delete_all_data(collection_name)
#         logger.info(f"Successfully deleted all data from collection: {collection_name}")
#         return {"message": f"All data deleted from collection {collection_name}"}
#     except Exception as e:
#         logger.error(f"Error deleting all data from collection {collection_name}: {str(e)}")
#         raise HTTPException(
#             status_code=500,
#             detail={"message": "Failed to delete collection data", "reason": str(e)}
#         )


import chromadb
from langchain_community.vectorstores import Chroma

def initialize_chroma_collection(project_id: int, group_id: int, documents: list):
    """
    Creates a Chroma vector store collection from input documents and stores it in the Chroma database.

    Args:
        project_id (int): The ID of the project to create a collection for.
        group_id (int): The ID of the group to create a collection for.
        documents (list): List of raw document strings to be indexed.

    Returns:
        vectorstore: The Chroma vector store object.
    """
    try:
        # Initialize the Chroma client
        client = chromadb.Client()

        # Create a collection name based on project_id and group_id
        collection_name = f"project_{project_id}_group_{group_id}"

        # If the collection doesn't exist, create it
        if collection_name not in client.list_collections():
            collection = client.create_collection(name=collection_name)
        else:
            collection = client.get_collection(name=collection_name)

        # Split the documents into smaller chunks and insert them into the collection
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,  # Adjust chunk size as needed
            chunk_overlap=100  # Adjust overlap as needed
        )

        all_chunks = []
        for doc in documents:
            chunks = splitter.create_documents([doc])
            all_chunks.extend(chunks)

        # Create the Chroma vector store from the documents
        vectorstore = Chroma.from_documents(
            documents=all_chunks,
            embedding=ollama_embeddings,
            collection=collection
        )
        
        # Persist the collection and vector store
        vectorstore.persist()
        logger.info(f"Vectorstore for group {group_id} created and stored in Chroma collection.")

        return vectorstore

    except Exception as e:
        logger.error(f"Error initializing Chroma collection: {str(e)}")
        raise HTTPException(status_code=500, detail="Error initializing Chroma collection")
