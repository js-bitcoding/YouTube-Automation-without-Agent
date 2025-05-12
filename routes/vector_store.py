from langchain_chroma import Chroma
from utils.logging_utils import logger
from fastapi import APIRouter, HTTPException
from langchain_ollama import OllamaEmbeddings
from database.schemas import CollectionResponseModel

router = APIRouter()

def get_chroma_connection(collection_name: str):
    try:
        ollama_embedding_model = "nomic-embed-text"
        vectorstore = Chroma(
            collection_name=collection_name,
            persist_directory="./chroma_db",
            embedding_function=OllamaEmbeddings(model=ollama_embedding_model)
        )
        return vectorstore
    except Exception as e:
        logger.error(f"Error connecting to Chroma DB: {str(e)}")
        raise HTTPException(status_code=500, detail="Error connecting to ChromaDB")

@router.get("/collections/{project_id}/{group_id}", response_model=CollectionResponseModel)
async def fetch_collection_by_group(project_id: int, group_id: int):
    try:
        collection_name = f"project_{project_id}_group_{group_id}"
        vectorstore = get_chroma_connection(collection_name)
        collection = vectorstore._collection.get()

        if not collection or not collection.get('ids'):
            logger.error(f"No data found for collection: {collection_name}")
            raise HTTPException(status_code=404, detail=f"Collection {collection_name} not found.")

        return CollectionResponseModel(
            ids=collection.get('ids', []),
            embeddings=collection.get('embeddings', []),
            documents=collection.get('documents', []),
            uris=collection.get('uris', []),
            data=collection.get('data', []),
            metadatas=collection.get('metadatas', []),
            included=collection.get('included', [])
        )
    except Exception as e:
        logger.error(f"Error fetching collection for project {project_id} and group {group_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Error fetching collection from ChromaDB")
