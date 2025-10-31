"""
Vercel serverless function entrypoint for FastAPI application.
This file imports the FastAPI app from fastapi_server and exposes it for Vercel.
"""

import sys
from pathlib import Path


# Add the project root to Python path so imports work correctly
project_root = Path(__file__).parent.parent
project_root_str = str(project_root)
if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)

# Import the FastAPI app using absolute import
# This works because we added the project root to sys.path
try:
    from api.fastapi_server import app
except ImportError:
    # Fallback: try relative import if absolute fails
    from .fastapi_server import app

# Export the app for Vercel
__all__ = ["app"]
