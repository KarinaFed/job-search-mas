"""Initialize database script."""
from models.database import init_db
from loguru import logger

if __name__ == "__main__":
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")

