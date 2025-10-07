#!/usr/bin/env python3
"""
Authentication middleware for FastAPI with Supabase JWT verification.
"""

import jwt
import os
from typing import Optional, Dict, Any
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase_client import supabase_service

# JWT configuration
JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET") or os.environ.get("SUPABASE_ANON_KEY")
JWT_ALGORITHM = "HS256"

# Security scheme
security = HTTPBearer(auto_error=False)

class AuthUser:
    """Represents an authenticated user."""
    def __init__(self, user_id: str, email: str, jwt_payload: Dict[str, Any]):
        self.id = user_id
        self.email = email
        self.jwt_payload = jwt_payload
        self.is_authenticated = True
    
    def __str__(self):
        return f"AuthUser(id={self.id}, email={self.email})"

def verify_jwt_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify a Supabase JWT token.
    
    Args:
        token: The JWT token to verify
        
    Returns:
        Decoded JWT payload if valid, None otherwise
    """
    if not token or not JWT_SECRET:
        return None
    
    try:
        # Remove 'Bearer ' prefix if present
        if token.startswith('Bearer '):
            token = token[7:]
        
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        
        # Verify the token is not expired and has required fields
        if 'sub' not in payload or 'email' not in payload:
            return None
            
        return payload
    except jwt.ExpiredSignatureError:
        print("JWT token has expired")
        return None
    except jwt.InvalidTokenError as e:
        print(f"Invalid JWT token: {e}")
        return None

async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[AuthUser]:
    """
    Get the current user from JWT token (optional - returns None if not authenticated).
    
    Args:
        credentials: HTTP authorization credentials
        
    Returns:
        AuthUser instance if authenticated, None otherwise
    """
    if not credentials:
        return None
    
    payload = verify_jwt_token(credentials.credentials)
    if not payload:
        return None
    
    return AuthUser(
        user_id=payload['sub'],
        email=payload['email'],
        jwt_payload=payload
    )

async def get_current_user_required(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> AuthUser:
    """
    Get the current user from JWT token (required - raises 401 if not authenticated).
    
    Args:
        credentials: HTTP authorization credentials
        
    Returns:
        AuthUser instance
        
    Raises:
        HTTPException: If not authenticated or token is invalid
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    payload = verify_jwt_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return AuthUser(
        user_id=payload['sub'],
        email=payload['email'],
        jwt_payload=payload
    )

async def get_user_profile(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Get user profile from Supabase.
    
    Args:
        user_id: The user's ID
        
    Returns:
        User profile data or None if not found
    """
    if not supabase_service:
        return None
    
    try:
        result = supabase_service.table('profiles').select('*').eq('id', user_id).single().execute()
        return result.data
    except Exception as e:
        print(f"Error fetching user profile: {e}")
        return None

# Dependency aliases for convenience
CurrentUser = Depends(get_current_user_required)
CurrentUserOptional = Depends(get_current_user_optional)