#!/usr/bin/env python3
"""
Development server script for Bench Finder FastAPI application.
This script provides an easy way to start the server with auto-reload enabled.
"""

import sys
from pathlib import Path

import uvicorn


# Add the project root to Python path
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def main():
    """Start the development server with auto-reload."""
    print("🚀 Starting Bench Finder Development Server")
    print("📁 Project root:", project_root)
    print("🔄 Auto-reload: ENABLED")
    print("📚 API docs: http://localhost:8866/docs")
    print("🔄 Redoc: http://localhost:8866/redoc")
    print("=" * 60)
    print("💡 The server will automatically restart when you modify Python files")
    print("💡 Press Ctrl+C to stop the server")
    print("=" * 60)

    try:
        uvicorn.run(
            "api.fastapi_server:app",
            host="0.0.0.0",
            port=8866,
            reload=True,
            log_level="info",
            reload_dirs=["api", "bench_finder", "tools"],  # Watch these directories
            reload_includes=["*.py"],  # Only watch Python files
            reload_excludes=["*.pyc", "__pycache__", "*.log", "*.tmp"],  # Exclude these
            access_log=True,
        )
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
