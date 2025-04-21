import logging

def setup_logging():
    """
    Sets up logging configuration for the application.

    Configures logging with INFO level, a standard format, and outputs logs to both the console and a file (`qa_system.log`).

    Returns:
        logging.Logger: The configured logger instance.
    """

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('YouTube_Automation.log')
        ]
    )

    return logging.getLogger(__name__)

logger = setup_logging()

logger.info(f"This is Information Message")
logger.warning(f"This is Warning Message")
logger.error(f"This is Error Message")