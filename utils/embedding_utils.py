from langchain_ollama import OllamaEmbeddings
from utils.file_processing import split_into_chunks
from utils.logging_utils import setup_logging

logger = setup_logging()

embeddings = OllamaEmbeddings(model="mxbai-embed-large")
def json_to_embeddings(json_rows: list) -> tuple:
    """
    Generate embeddings for JSON rows using OpenAI's embedding model.

    Args:
        json_rows (list): List of JSON objects (dictionaries) representing data rows.

    Returns:
        tuple: Contains:
            - raw_data (list): Original JSON objects
            - embedding_vectors (list): Corresponding embedding vectors for each JSON object
    """
    
    raw_data = []
    embedding_vectors = []

    for row_json in json_rows:
        row_text = str(row_json)
        embedding = embeddings.embed_documents([row_text])[0]
        raw_data.append(row_json)
        embedding_vectors.append(embedding)
    
    return raw_data, embedding_vectors

def get_query_embedding(query_text: str, target_dimension: int = 3072) -> list:
    """
    Generate embedding for query text using OpenAI API.
    
    Args:
        query_text (str): The text to generate embeddings for
        target_dimension (int, optional): Target dimension for the embedding
        
    Returns:
        list: Vector embedding for the text
    """
    try:
        embedding = embeddings.embed_query(query_text)

        if target_dimension and len(embedding) != target_dimension:
            if target_dimension > len(embedding):
                repeat_times = target_dimension // len(embedding)
                remainder = target_dimension % len(embedding)
                embedding = embedding * repeat_times + embedding[:remainder]
            else:
                embedding = embedding[:target_dimension]
            
            logger.info(f"Adjusted embedding dimension from {len(embedding)} to {target_dimension}")
        
        return embedding
    except Exception as e:
        logger.error(f"Error generating query embedding: {str(e)}")
        raise

def get_txt_embedding(document_chunks):
    """
    Reads a text file, splits the text into chunks, and generates embeddings for each chunk using OpenAI.

    :param document_chunks: List of text chunks extracted from a document.
    :return: A tuple (chunks, embeddings) where:
        - chunks: List of text chunks.
        - embeddings: List of corresponding embedding vectors.
    """
    embeddings = []
    openai_embeddings = OllamaEmbeddings(model="mxbai-embed-large")

    for chunk in document_chunks:
        if not isinstance(chunk, str):
            chunk = str(chunk)
        response = openai_embeddings.embed_documents([chunk])
        embeddings.append(response[0])

    return document_chunks, embeddings 

def extract_metadata_urls_embeddings(json_rows: list) -> list:
    """
    Extract metadata, URLs, and embeddings from JSON API response, create txt files and generate embeddings.

    Args:
        json_rows (list): List of JSON objects (dictionaries) representing data rows.
        output_dir (str): Directory to store the .txt files.

    Returns:
        list: A list of dictionaries containing 'url', 'raw_data', and 'embedding'.
    """
    json_rows = json_rows.get("results")
    results = []

    for idx, row_json in enumerate(json_rows):
        url = row_json.get("url", "")
        raw_data = row_json.get("markdown", "").replace("\n", "")

        chunks = split_into_chunks(raw_data)
        document_chunks, embeddings = get_txt_embedding(chunks)
        
        results.append({
            "url": url,
            "raw_data": document_chunks,
            "embedding": embeddings
        })
    
    return results