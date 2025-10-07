#!/usr/bin/env python3
"""
FastAPI endpoints for Supabase user data operations.
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, status, Query, Path, Body
from pydantic import BaseModel, Field
from auth_middleware import AuthUser, CurrentUser, CurrentUserOptional
from supabase_client import supabase_service

# Create router for user-related endpoints
router = APIRouter(prefix="/api/v1/user", tags=["user"])

# Pydantic models for request/response
class FavoriteResponse(BaseModel):
    id: str
    user_id: str
    bench_id: int
    created_at: str

class CommentResponse(BaseModel):
    id: str
    user_id: str
    bench_id: int
    content: str
    created_at: str
    updated_at: str

class CommentRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=500)

class BenchStatusResponse(BaseModel):
    id: str
    user_id: str
    bench_id: int
    status: str
    created_at: str
    updated_at: str

class BenchStatusRequest(BaseModel):
    status: str = Field(..., pattern="^(want_to_go|been_there)$")

class MissingBenchReportResponse(BaseModel):
    id: str
    user_id: str
    lat: float
    lng: float
    description: Optional[str]
    image_url: Optional[str]
    status: str
    created_at: str
    updated_at: str

class MissingBenchReportRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    description: Optional[str] = Field(None, max_length=500)
    image_url: Optional[str] = None

class IssueReportResponse(BaseModel):
    id: str
    user_id: str
    bench_id: int
    issue_type: str
    description: str
    image_url: Optional[str]
    status: str
    created_at: str
    updated_at: str

class IssueReportRequest(BaseModel):
    issue_type: str = Field(..., pattern="^(damaged|missing|inappropriate|other)$")
    description: str = Field(..., min_length=1, max_length=1000)
    image_url: Optional[str] = None

# Favorites endpoints
@router.get("/favorites", response_model=List[FavoriteResponse])
async def get_user_favorites(current_user: AuthUser = CurrentUser):
    """Get all favorites for the current user."""
    try:
        result = supabase_service.table('bench_favorites').select('*').eq('user_id', current_user.id).order('created_at', desc=True).execute()
        return result.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching favorites: {str(e)}")

@router.post("/favorites/{bench_id}", response_model=FavoriteResponse)
async def add_favorite(
    bench_id: int = Path(..., description="ID of the bench to favorite"),
    current_user: AuthUser = CurrentUser
):
    """Add a bench to user's favorites."""
    try:
        result = supabase_service.table('bench_favorites').insert({
            'user_id': current_user.id,
            'bench_id': bench_id
        }).execute()
        
        if not result.data:
            raise HTTPException(status_code=400, detail="Failed to add favorite")
        
        return result.data[0]
    except Exception as e:
        if "duplicate key" in str(e).lower():
            raise HTTPException(status_code=409, detail="Bench already favorited")
        raise HTTPException(status_code=500, detail=f"Error adding favorite: {str(e)}")

@router.delete("/favorites/{bench_id}")
async def remove_favorite(
    bench_id: int = Path(..., description="ID of the bench to unfavorite"),
    current_user: AuthUser = CurrentUser
):
    """Remove a bench from user's favorites."""
    try:
        result = supabase_service.table('bench_favorites').delete().eq('user_id', current_user.id).eq('bench_id', bench_id).execute()
        return {"message": "Favorite removed successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error removing favorite: {str(e)}")

# Comments endpoints
@router.get("/comments", response_model=List[CommentResponse])
async def get_user_comments(current_user: AuthUser = CurrentUser):
    """Get all comments by the current user."""
    try:
        result = supabase_service.table('bench_comments').select('*').eq('user_id', current_user.id).order('created_at', desc=True).execute()
        return result.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching comments: {str(e)}")

@router.post("/comments/{bench_id}", response_model=CommentResponse)
async def add_comment(
    bench_id: int = Path(..., description="ID of the bench to comment on"),
    comment_data: CommentRequest = Body(...),
    current_user: AuthUser = CurrentUser
):
    """Add a comment to a bench."""
    try:
        result = supabase_service.table('bench_comments').insert({
            'user_id': current_user.id,
            'bench_id': bench_id,
            'content': comment_data.content.strip()
        }).execute()
        
        if not result.data:
            raise HTTPException(status_code=400, detail="Failed to add comment")
        
        return result.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error adding comment: {str(e)}")

@router.put("/comments/{comment_id}", response_model=CommentResponse)
async def update_comment(
    comment_id: str = Path(..., description="ID of the comment to update"),
    comment_data: CommentRequest = Body(...),
    current_user: AuthUser = CurrentUser
):
    """Update a comment (only by the comment author)."""
    try:
        result = supabase_service.table('bench_comments').update({
            'content': comment_data.content.strip()
        }).eq('id', comment_id).eq('user_id', current_user.id).execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Comment not found or not authorized")
        
        return result.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating comment: {str(e)}")

@router.delete("/comments/{comment_id}")
async def delete_comment(
    comment_id: str = Path(..., description="ID of the comment to delete"),
    current_user: AuthUser = CurrentUser
):
    """Delete a comment (only by the comment author)."""
    try:
        result = supabase_service.table('bench_comments').delete().eq('id', comment_id).eq('user_id', current_user.id).execute()
        return {"message": "Comment deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting comment: {str(e)}")

# Bench status endpoints
@router.get("/status", response_model=List[BenchStatusResponse])
async def get_user_bench_status(
    status_filter: Optional[str] = Query(None, pattern="^(want_to_go|been_there)$", description="Filter by status"),
    current_user: AuthUser = CurrentUser
):
    """Get user's bench status records."""
    try:
        query = supabase_service.table('bench_status').select('*').eq('user_id', current_user.id)
        
        if status_filter:
            query = query.eq('status', status_filter)
        
        result = query.order('updated_at', desc=True).execute()
        return result.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching bench status: {str(e)}")

@router.post("/status/{bench_id}", response_model=BenchStatusResponse)
async def set_bench_status(
    bench_id: int = Path(..., description="ID of the bench"),
    status_data: BenchStatusRequest = Body(...),
    current_user: AuthUser = CurrentUser
):
    """Set status for a bench (want_to_go or been_there)."""
    try:
        result = supabase_service.table('bench_status').upsert({
            'user_id': current_user.id,
            'bench_id': bench_id,
            'status': status_data.status
        }, on_conflict='user_id,bench_id').execute()
        
        if not result.data:
            raise HTTPException(status_code=400, detail="Failed to set bench status")
        
        return result.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error setting bench status: {str(e)}")

@router.delete("/status/{bench_id}")
async def clear_bench_status(
    bench_id: int = Path(..., description="ID of the bench"),
    current_user: AuthUser = CurrentUser
):
    """Clear status for a bench."""
    try:
        result = supabase_service.table('bench_status').delete().eq('user_id', current_user.id).eq('bench_id', bench_id).execute()
        return {"message": "Bench status cleared successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error clearing bench status: {str(e)}")

# Missing bench reports endpoints
@router.get("/missing-reports", response_model=List[MissingBenchReportResponse])
async def get_user_missing_reports(current_user: AuthUser = CurrentUser):
    """Get all missing bench reports by the current user."""
    try:
        result = supabase_service.table('missing_bench_reports').select('*').eq('user_id', current_user.id).order('created_at', desc=True).execute()
        return result.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching missing reports: {str(e)}")

@router.post("/missing-reports", response_model=MissingBenchReportResponse)
async def create_missing_report(
    report_data: MissingBenchReportRequest = Body(...),
    current_user: AuthUser = CurrentUser
):
    """Create a missing bench report."""
    try:
        result = supabase_service.table('missing_bench_reports').insert({
            'user_id': current_user.id,
            'lat': report_data.lat,
            'lng': report_data.lng,
            'description': report_data.description,
            'image_url': report_data.image_url
        }).execute()
        
        if not result.data:
            raise HTTPException(status_code=400, detail="Failed to create missing report")
        
        return result.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating missing report: {str(e)}")

# Issue reports endpoints
@router.get("/issue-reports", response_model=List[IssueReportResponse])
async def get_user_issue_reports(current_user: AuthUser = CurrentUser):
    """Get all issue reports by the current user."""
    try:
        result = supabase_service.table('bench_issue_reports').select('*').eq('user_id', current_user.id).order('created_at', desc=True).execute()
        return result.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching issue reports: {str(e)}")

@router.post("/issue-reports/{bench_id}", response_model=IssueReportResponse)
async def create_issue_report(
    bench_id: int = Path(..., description="ID of the bench to report"),
    report_data: IssueReportRequest = Body(...),
    current_user: AuthUser = CurrentUser
):
    """Create an issue report for a bench."""
    try:
        result = supabase_service.table('bench_issue_reports').insert({
            'user_id': current_user.id,
            'bench_id': bench_id,
            'issue_type': report_data.issue_type,
            'description': report_data.description.strip(),
            'image_url': report_data.image_url
        }).execute()
        
        if not result.data:
            raise HTTPException(status_code=400, detail="Failed to create issue report")
        
        return result.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating issue report: {str(e)}")

# Public endpoints (don't require authentication)
@router.get("/bench/{bench_id}/comments", response_model=List[CommentResponse])
async def get_bench_comments(
    bench_id: int = Path(..., description="ID of the bench"),
    current_user: Optional[AuthUser] = CurrentUserOptional
):
    """Get all comments for a specific bench."""
    try:
        result = supabase_service.table('bench_comments').select('*').eq('bench_id', bench_id).order('created_at', asc=True).execute()
        return result.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching bench comments: {str(e)}")

@router.get("/bench/{bench_id}/status-counts")
async def get_bench_status_counts(
    bench_id: int = Path(..., description="ID of the bench"),
    current_user: Optional[AuthUser] = CurrentUserOptional
):
    """Get status counts for a specific bench."""
    try:
        want_to_go_result = supabase_service.table('bench_status').select('id', count='exact').eq('bench_id', bench_id).eq('status', 'want_to_go').execute()
        been_there_result = supabase_service.table('bench_status').select('id', count='exact').eq('bench_id', bench_id).eq('status', 'been_there').execute()
        
        return {
            "want_to_go": want_to_go_result.count or 0,
            "been_there": been_there_result.count or 0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching status counts: {str(e)}")