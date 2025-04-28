import re
import os
import base64
import pandas as pd
from aiohttp import ClientSession, ClientTimeout, TCPConnector
from langchain_community.document_loaders import AsyncHtmlLoader, PyPDFLoader, Docx2txtLoader
from langchain_community.document_transformers import Html2TextTransformer
from langchain_experimental.text_splitter import SemanticChunker
from langchain_ollama import OllamaEmbeddings
from doc2docx import convert
from fastapi import HTTPException
from dotenv import load_dotenv
load_dotenv()

from utils.logging_utils import setup_logging

logger = setup_logging()

def convert_image_to_base64(image_path: str) -> str:
    """
    Convert an image file to a base64 encoded string.

    Args:
        image_path (str): Path to the image file to be converted.

    Returns:
        str: Base64 encoded string representation of the image.

    Raises:
        FileNotFoundError: If the image file does not exist.
        IOError: If there are issues reading the image file.
    """
    try:
        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            logger.debug(f"Successfully converted image to base64: {image_path}")
            return encoded_string
    except FileNotFoundError:
        logger.error(f"Image file not found: {image_path}")
        raise HTTPException(status_code=500,detail={"message": "Image file not found","reason": str(e)})
    except IOError as e:
        logger.error(f"Error reading image file {image_path}: {str(e)}")
        raise HTTPException(status_code=500,detail={"message": "Error reading image file","reason": str(e)})

def split_into_chunks(text: str, summary:str = None) -> list:
    """
    Split text into chunks based on semantic similarity.
 
    Args:
        text (str): Input text to be split.
        openai_api_key (str, optional): OpenAI API key for embeddings.
                                       If None, uses environment variable.
 
    Returns:
        list: List of text chunks based on semantic similarity.
 
    Raises:
        HTTPException: If an error occurs during chunking.
    """
    try:
        print("Embedding in process")
        embeddings = OllamaEmbeddings(model="mxbai-embed-large")
       
        text_splitter = SemanticChunker(
            embeddings,  
        )

        docs = text_splitter.create_documents([text])

        chunks = [doc.page_content for doc in docs]
 
        if summary:
            chunks.append([f"{summary}\n\n{chunk}" for chunk in chunks])
       
        logger.debug(f"Text split into {len(chunks)} semantic chunks")
        return chunks
       
    except Exception as e:
        logger.error(f"Error splitting text into semantic chunks: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Error splitting text into semantic chunks",
                "reason": str(e)
            }
        )
    
def process_text_file(file_path: str) -> list:
    """
    Read and process a text file into chunks.

    Args:
        file_path (str): Path to the text file.

    Returns:
        list: List of text chunks from the file.

    Raises:
        FileNotFoundError: If the text file does not exist.
        IOError: If there are issues reading the text file.
        UnicodeDecodeError: If the file encoding is not UTF-8.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            text = file.read()
        chunks = split_into_chunks(text.strip())
        logger.info(f"Successfully processed text file: {file_path}")
        return chunks
    except FileNotFoundError:
        logger.error(f"Text file not found: {file_path}")
        raise HTTPException(status_code=500,detail={"message": "Text file not found","reason": str(e)})
    except (IOError, UnicodeDecodeError) as e:
        logger.error(f"Error processing text file {file_path}: {str(e)}")
        raise HTTPException(status_code=500,detail={"message": "Error processing text file","reason": str(e)})

def excel_to_json(file_path: str) -> list:
    """
    Read an Excel file and convert it to JSON format row by row.

    Args:
        file_path (str): Path to the Excel file.

    Returns:
        list: List of dictionaries, where each dictionary represents a row from the Excel file.
            Limited to first 5 rows after removing empty rows and columns.

    Raises:
        FileNotFoundError: If the Excel file does not exist.
        pd.errors.EmptyDataError: If the Excel file is empty.
        Exception: For other pandas-related errors during file processing.
    """
    try:
        if file_path.endswith(".xlsx"):
            df = pd.read_excel(file_path)
        elif file_path.endswith(".csv"):
            df = pd.read_csv(file_path)
        else:
            raise ValueError("Unsupported file type")
        
        if df.empty:
            logger.warning(f"Excel file is empty: {file_path}")
            return []
        
        df = df.dropna(axis=1, how='all')
        df = df.dropna(axis=0, how='all')
        df = df.head(500)
        
        json_data = df.apply(lambda row: row.to_dict(), axis=1).tolist()
        logger.info(f"Successfully converted Excel file to JSON: {file_path}")
        return json_data
    except FileNotFoundError:
        logger.error(f"Excel file not found: {file_path}")
        raise HTTPException(status_code=500,detail={"message": "Excel file not found","reason": str(e)})
    except pd.errors.EmptyDataError:
        logger.error(f"Excel file is empty or corrupted: {file_path}")
        raise HTTPException(status_code=500,detail={"message": "Excel file is empty or corrupted","reason": str(e)})
    except Exception as e:
        logger.error(f"Error processing Excel file {file_path}: {str(e)}")
        raise HTTPException(status_code=500,detail={"message": "Error processing Excel file","reason": str(e)})

async def fetch_html(url):
    """Fetches HTML from a given URL asynchronously, handling large headers."""
    try:
        timeout = ClientTimeout(total=30)
        connector = TCPConnector(limit_per_host=5, enable_cleanup_closed=True)
        
        async with ClientSession(timeout=timeout, connector=connector) as session:
            async with session.get(url, headers={"User-Agent": "Mozilla/5.0"}) as response:
                return await response.text()
    except Exception as e:
        logger.error(f"Error fetching HTML from {url}: {str(e)}")
        raise HTTPException(status_code=500,detail={"message": "Error fetching HTML from {url}","reason": str(e)})

def extract_urls_scraped_data(json_data):
    """
    Extracts webpage and image URLs from scraped JSON data.

    Args:
        json_data (dict): The JSON object containing scraped data, expected to have a "results" key with markdown content.

    Returns:
        tuple: A set of extracted webpage URLs and a set of extracted image URLs.

    Raises:
        HTTPException: If an error occurs during URL extraction.
    """

    try:
        url_pattern = re.compile(r"https?://[^\s\)\]\"]+")

        image_pattern = re.compile(r"https?://[^\s\)\]\"]+\.(?:jpg|jpeg|png|webp|gif|bmp|tiff)(?:\?.*)?$", re.IGNORECASE)

        page_urls = set()
        image_urls = set()

        for result in json_data.get("results", []):
            markdown_text = result.get("markdown", "")
            extracted_urls = url_pattern.findall(markdown_text)

            for url in extracted_urls:
                if image_pattern.match(url) and not url.endswith('.svg'):
                    image_urls.add(url)
                elif not url.endswith('.svg'):
                    page_urls.add(url)

        return page_urls, image_urls
    except Exception as e:
        logger.error(f"Error extracting URLs from scraped data: {str(e)}")
        raise HTTPException(status_code=500,detail={"message": "Error extracting URLs from scraped data","reason": str(e)})

async def save_html_to_text(url):
    """Fetches and converts HTML to text asynchronously."""
    try:
        loader = AsyncHtmlLoader([url])
        docs = await loader.aload()
        
        html2text = Html2TextTransformer()
        docs_transformed = html2text.transform_documents(docs)

        if docs_transformed:
            extracted_text = docs_transformed[0].page_content.replace("\n", " ")
            logger.info(f"Extracted text from {url}: {extracted_text[:200]}...")  # Preview first 200 chars
            return extracted_text
        raise HTTPException(status_code=500,detail={"message": "Error saving HTML to text","reason": str(e)})
    except Exception as e:
        logger.error(f"Error saving HTML to text: {str(e)}")
        raise HTTPException(status_code=500,detail={"message": "Error saving HTML to text","reason": str(e)})

def is_url(image_path):
    """
    Checks if the given image_path is a URL.

    Args:
        image_path (str): The input path or URL.

    Returns:
        bool: True if image_path is a URL, otherwise False.
    """
    try:
        url_pattern = re.compile(r"^https?:\/\/")
        return bool(url_pattern.match(image_path))
    except Exception as e:
        logger.error(f"Error checking if image_path is a URL: {str(e)}")
        raise HTTPException(status_code=500,detail={"message": "Error checking if image_path is a URL","reason": str(e)})

def process_pdf_to_text(file_path: str, summary: str = None) -> list:
    """
    Process a PDF file and return a list of text chunks.
    """
    try:
        loader = PyPDFLoader(file_path)
        docs = loader.load()
        combined_text = "\n".join(doc.page_content for doc in docs)
        return split_into_chunks(combined_text, summary)
    except Exception as e:
        logger.error(f"Error processing PDF file {file_path}: {str(e)}")
        raise HTTPException(status_code=500,detail={"message": "Error processing PDF file","reason": str(e)})

def process_doc_to_text(file_path: str, summary: str = None) -> list:
    """
    Process a DOC/DOCX file and return a list of text chunks.
 
    Args:
        file_path (str): Path to the DOC/DOCX file.
 
    Returns:
        list: List of text chunks from the file.
 
    Raises:
        FileNotFoundError: If the document file does not exist.
        Exception: If there are issues processing the document file.
    """
    try:
        file_extension = file_path.split(".")[-1]
        if file_extension == "doc":
            convert(file_path, file_path.replace(".doc", ".docx"))
            loader = Docx2txtLoader(file_path.replace(".doc", ".docx"))
        else:
            loader = Docx2txtLoader(file_path)
        docs = loader.load()
        combined_text = "\n".join(doc.page_content for doc in docs)
        chunks = split_into_chunks(combined_text, summary)
        logger.info(f"Successfully processed document file: {file_path}")
       
        if file_extension == "doc":
            os.remove(file_path.replace(".doc", ".docx"))
        return chunks
    except FileNotFoundError:
        logger.error(f"Document file not found: {file_path}")
        raise HTTPException(status_code=500,detail={"message": "Document file not found","reason": str(e)})
    except Exception as e:
        logger.error(f"Error processing document file {file_path}: {str(e)}")
        if file_extension == "doc" and os.path.exists(file_path.replace(".doc", ".docx")):
            os.remove(file_path.replace(".doc", ".docx"))
        raise HTTPException(status_code=500,detail={"message": "Error processing document file","reason": str(e)})
    
def save_base64_file(base64_data: str, file_path: str):
    """Decode and save a base64-encoded file."""
    try:
        file_bytes = base64.b64decode(base64_data)
        with open(file_path, "wb") as f:
            f.write(file_bytes)
        return True
    except Exception as e:
        logger.error(f"Failed to decode and save file: {str(e)}")
        raise HTTPException(status_code=500,detail={"message": "Failed to decode and save file","reason": str(e)})

def convert_file_to_base64(file_path: str) -> str:
    """
    Convert any file to a base64 encoded string.

    Args:
        file_path (str): Path to the file to be converted.

    Returns:
        str: Base64 encoded string representation of the file.

    Raises:
        FileNotFoundError: If the file does not exist.
        IOError: If there are issues reading the file.
    """
    try:
        with open(file_path, "rb") as file:
            return base64.b64encode(file.read()).decode("utf-8")
    except FileNotFoundError:
        raise FileNotFoundError(f"File not found: {file_path}")
    except IOError as e:
        raise IOError(f"Error reading file {file_path}: {str(e)}")