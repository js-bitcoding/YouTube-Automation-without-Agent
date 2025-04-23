import logging

def setup_logging():
    """
    Sets up logging configuration for the application.

    Configures logging with INFO level, a standard format, and outputs logs to both the console and a file (`qa_system.log`).

    Returns:
        logging.Logger: The configured logger instance.
    """
    logger = logging.getLogger("YouTubeAutomation")
    logger.setLevel(logging.INFO)

    if not logger.hasHandlers():
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        file_handler = logging.FileHandler("YouTube_Automation.log")
        file_handler.setFormatter(formatter)

        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(stream_handler)

    return logger

logger = setup_logging()
