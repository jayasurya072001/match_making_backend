import logging
import sys
from app.core.config import settings

def setup_logging():
    logging_format = "[%(asctime)s] %(levelname)s in %(module)s: %(message)s"
    
    logging.basicConfig(
        level=settings.LOG_LEVEL,
        format=logging_format,
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Set logger for third-party libraries
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("fastapi").setLevel(logging.INFO)
