"""
Authentication utilities for Firebase integration.
Provides helpers to verify Firebase JWT tokens and extract user information.
"""

import logging

from fastapi import Header, HTTPException, status

from bench_finder.config import (
    FIREBASE_CREDENTIALS_BASE64,
    FIREBASE_CREDENTIALS_PATH,
)


logger = logging.getLogger(__name__)

# Firebase Admin SDK initialization
_firebase_app_initialized = False


def _initialize_firebase_admin() -> bool:
    """Initialize Firebase Admin SDK if not already initialized."""
    global _firebase_app_initialized  # noqa: PLW0603

    if _firebase_app_initialized:
        return True

    try:
        import firebase_admin
        from firebase_admin import credentials

        # Check if already initialized
        try:
            firebase_admin.get_app()
            _firebase_app_initialized = True
            return True
        except ValueError:
            # App not initialized yet, continue with initialization
            pass

        # Try to initialize with credentials
        cred = None

        # Option 1: Base64-encoded credentials (for Vercel/serverless)
        if FIREBASE_CREDENTIALS_BASE64:
            import base64
            import json

            creds_json = base64.b64decode(FIREBASE_CREDENTIALS_BASE64).decode("utf-8")
            creds_dict = json.loads(creds_json)
            cred = credentials.Certificate(creds_dict)
            logger.info("Firebase Admin SDK initialized with base64 credentials")

        # Option 2: Credentials file path
        elif FIREBASE_CREDENTIALS_PATH:
            cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
            logger.info(
                f"Firebase Admin SDK initialized with credentials from {FIREBASE_CREDENTIALS_PATH}"
            )

        # Option 3: Application Default Credentials (GCP environments)
        else:
            cred = credentials.ApplicationDefault()
            logger.info(
                "Firebase Admin SDK initialized with Application Default Credentials"
            )

        firebase_admin.initialize_app(cred)
        _firebase_app_initialized = True
        return True

    except Exception:
        logger.exception("Failed to initialize Firebase Admin SDK")
        return False


def verify_token(token: str) -> dict | None:
    """
    Verify Firebase JWT token and return user information.

    Args:
        token: JWT token from Authorization header

    Returns:
        Dictionary with user information (user_id, email, etc.) or None if invalid
    """
    if not _initialize_firebase_admin():
        logger.debug("Firebase Admin SDK not initialized - skipping token verification")
        return None

    try:
        from firebase_admin import auth

        # Verify the ID token
        decoded_token = auth.verify_id_token(token)

        return {
            "user_id": decoded_token.get("uid"),
            "email": decoded_token.get("email"),
            "metadata": {
                "name": decoded_token.get("name"),
                "picture": decoded_token.get("picture"),
                "email_verified": decoded_token.get("email_verified", False),
                "provider_id": decoded_token.get("firebase", {}).get(
                    "sign_in_provider"
                ),
            },
        }

    except Exception as e:
        logger.debug(f"Token verification failed: {e}")
        return None


def get_user_from_header(authorization: str | None) -> dict | None:
    """
    Extract and verify user from Authorization header (optional).
    Returns None if no token is provided or if token is invalid.

    Args:
        authorization: Authorization header value (Bearer <token>) or None

    Returns:
        User information dict or None
    """
    if not authorization:
        return None

    # Extract token from "Bearer <token>" format
    try:
        scheme, token = authorization.split(maxsplit=1)
        if scheme.lower() != "bearer":
            return None
    except ValueError:
        return None

    return verify_token(token)


async def get_current_user_optional(
    authorization: str | None = Header(None, alias="Authorization"),
) -> dict | None:
    """
    FastAPI dependency to extract and verify user from Authorization header (optional).
    Returns None if no token is provided or if token is invalid.

    Args:
        authorization: Authorization header value (Bearer <token>)

    Returns:
        User information dict or None
    """
    return get_user_from_header(authorization)


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
