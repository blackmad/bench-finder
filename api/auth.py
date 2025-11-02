"""
Authentication utilities for Supabase integration.
Provides helpers to verify Supabase JWT tokens and extract user information.
"""

import logging

from fastapi import Header, HTTPException, status
from supabase import Client, create_client

from bench_finder.config import (
    SUPABASE_ANON_KEY,
    SUPABASE_URL,
)


logger = logging.getLogger(__name__)

# Cache Supabase client instance
_supabase_client: Client | None = None


def get_supabase_client() -> Client | None:
    """Get or create Supabase client instance."""
    global _supabase_client  # noqa: PLW0603

    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        logger.warning(
            "Supabase credentials not configured - authentication features will be disabled"
        )
        return None

    if _supabase_client is None:
        try:
            _supabase_client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
            logger.info("Supabase client initialized successfully")
        except Exception:
            logger.exception("Failed to initialize Supabase client")
            return None

    return _supabase_client


def verify_token(token: str) -> dict | None:
    """
    Verify Supabase JWT token and return user information.

    Args:
        token: JWT token from Authorization header

    Returns:
        Dictionary with user information (user_id, email, etc.) or None if invalid
    """
    client = get_supabase_client()
    if not client:
        return None

    try:
        # Set the auth token and get user
        client.auth.set_session({"access_token": token, "refresh_token": ""})
        response = client.auth.get_user()
        if response.user:
            return {
                "user_id": response.user.id,
                "email": response.user.email,
                "metadata": response.user.user_metadata,
            }
    except Exception as e:
        logger.warning(f"Token verification failed: {e}")
        return None

    return None


async def get_current_user_optional(
    authorization: str | None = Header(None, alias="Authorization"),
) -> dict | None:
    """
    Extract and verify user from Authorization header (optional).
    Returns None if no token is provided or if token is invalid.

    Args:
        authorization: Authorization header value (Bearer <token>)

    Returns:
        User information dict or None
    """
    if not authorization:
        return None

    # Extract token from "Bearer <token>" format
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            return None
    except ValueError:
        return None

    return verify_token(token)


async def get_current_user(
    authorization: str | None = Header(None, alias="Authorization"),
) -> dict:
    """
    Extract and verify user from Authorization header (required).
    Raises HTTPException if token is missing or invalid.

    Args:
        authorization: Authorization header value (Bearer <token>)

    Returns:
        User information dict

    Raises:
        HTTPException: If authentication fails
    """
    user = await get_current_user_optional(authorization)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token.",
        )
    return user
