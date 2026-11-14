"""FastAPI dependency injection functions."""

from fastapi import Request

from bench_finder.services.database import BenchDatabase


# Configuration constants
DEFAULT_START_LAT = 52.3613577  # Amsterdam, Netherlands (matches actual data)
DEFAULT_START_LNG = 4.8666322
DEFAULT_MIN_CONFIDENCE = 0
PAGE_SIZE = 20


def get_db(request: Request) -> BenchDatabase:
    """
    FastAPI dependency to get database instance from app state.

    Initializes database if not already set (fallback for serverless environments
    like Vercel where lifespan startup might not run before first request).
    """
    if not hasattr(request.app.state, "db") or request.app.state.db is None:
        print("⚠️  Database not initialized in state, initializing now...")
        request.app.state.db = BenchDatabase()
        print("✅ Database initialized")
    return request.app.state.db
