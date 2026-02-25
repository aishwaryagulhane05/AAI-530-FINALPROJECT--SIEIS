"""Entry point to run the SIEIS API server.

Usage:
    python -m src.app.api_server
    
Or with uvicorn directly:
    uvicorn src.app.api.main:app --host 0.0.0.0 --port 8000 --reload
"""

import uvicorn
from dotenv import load_dotenv

# Load .env before importing config
load_dotenv()

from src.app import config

if __name__ == "__main__":
    uvicorn.run(
        "src.app.api.main:app",
        host=config.API_HOST,
        port=config.API_PORT,
        reload=config.DEBUG,
        log_level=config.LOG_LEVEL.lower(),
    )
