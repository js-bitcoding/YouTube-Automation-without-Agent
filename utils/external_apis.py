import os
import httpx
import requests
from utils.file_processing import convert_image_to_base64, is_url
from utils.logging_utils import setup_logging
from fastapi import HTTPException

logger = setup_logging()

def get_image_description(image_path):
    """
    Sends an image (local file or remote URL) and a question to the AI model and retrieves the response.

    Args:
        image_path (str): Path to the image file or image URL.

    Returns:
        dict: A dictionary containing the AI response or an error message.
    """
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {os.environ.get('OPENAI_API_KEY')}"
        }

        if not os.environ.get('OPENAI_API_KEY'):
            logger.error("OPENAI_API_KEY not found in environment variables")
            raise ValueError("OPENAI_API_KEY not configured")

        if is_url(image_path):
            image_data = {
                "url": image_path,
                "detail": "auto"
            }
        else:
            try:
                base64_image = convert_image_to_base64(image_path)
                image_data = {
                    "url": f"data:image/jpeg;base64,{base64_image}",
                    "detail": "auto"
                }
            except Exception as e:
                logger.error(f"Failed to convert image to base64: {str(e)}")
                raise

        payload = {
            "model": "gpt-4o",
            "messages": [
                {"role": "system", "content": "Analyze the image and provide a detailed, in-depth description, including all visible objects, people, colors, the setting, and any relevant context or emotional tone."},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": image_data
                        }
                    ]
                }
            ],
            "max_completion_tokens": 3000
        }

        try:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions", 
                headers=headers, 
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            
        except requests.exceptions.Timeout:
            logger.error("Request to OpenAI API timed out")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to make request to OpenAI API: {str(e)}")
            raise

        try:
            response_data = response.json()
            image_description = response_data['choices'][0]['message']['content']
            logger.info("Successfully retrieved image description")
            return image_description
            
        except (KeyError, ValueError) as e:
            logger.error(f"Failed to parse OpenAI API response: {str(e)}")
            raise HTTPException(status_code=500,detail={"message": "Failed to parse response","reason": str(e)})
            
    except Exception as e:
        logger.error(f"Unexpected error in get_image_description: {str(e)}")
        raise HTTPException(status_code=500,detail={"message": "Unexpected error","reason": str(e)})

async def fetch_scraped_data(urls: list):
    """Send request to scraping service and return response.

    Args:
        urls (list): List of URLs to scrape.

    Returns:
        dict: JSON response from the scraping service.
    """
    try:
        async with httpx.AsyncClient(timeout=1000) as client:
            response = await client.post(
                "http://localhost:8081/scrape",
                json={"urls": urls},
            )

        if response.status_code == 200:
            try:
                return {"status": 200, "response": response.json()}
            except httpx.JSONDecodeError as e:
                logger.error(f"Invalid JSON response: {str(e)}")
                raise HTTPException(status_code=500,detail={"message": "Invalid JSON response","reason": str(e)})
        else:
            logger.error(f"Failed to fetch data. Status code: {response.status_code}")
            raise HTTPException(status_code=500,detail={"message": "Failed to fetch data","reason": "Failed to fetch data"})
    except Exception as e:
        logger.error(f"Error in fetch_scraped_data: {str(e)}")
        raise HTTPException(status_code=500,detail={"message": "Error in fetch_scraped_data","reason": str(e)})
