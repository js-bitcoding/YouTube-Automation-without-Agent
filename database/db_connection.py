from config import DATABASE_URL
from database.models import Base
from sqlalchemy import create_engine
from utils.logging_utils import logger
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import  SQLAlchemyError, IntegrityError

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

def init_db():
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Tables initialized successfully.")
    except SQLAlchemyError as e:
        logger.error(f"Error during DB initialization: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during DB initialization: {str(e)}")
        raise

def get_db():
    db = None
    try:
        db = SessionLocal()
        yield db
    except IntegrityError as e:
        logger.error(f"Integrity error in DB session: {str(e)}")
        raise
    except SQLAlchemyError as e:
        logger.error(f"SQLAlchemy session error: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected DB session error: {str(e)}")
        raise
    finally:
        if db:
            db.close()
            logger.info("Database session closed.")