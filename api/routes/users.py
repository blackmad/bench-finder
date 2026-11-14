"""User interaction endpoints: ratings, statuses, comments, user-data."""

from datetime import UTC, datetime

from fastapi import APIRouter, Body, Depends, HTTPException, Path, status

from bench_finder.models.enums import BenchUserStatus
from bench_finder.models.unified_models import (
    BenchCandidate,
    BenchComment,
    BenchRating,
    BenchUserStatusRecord,
)
from bench_finder.services.database import BenchDatabase

from ..api_models import (
    BenchUserDataResponse,
    BenchUserStatusRequest,
    BenchUserStatusResponse,
    CommentRequest,
    CommentResponse,
    ErrorResponse,
    RatingRequest,
    RatingResponse,
)
from ..auth import get_current_user, get_current_user_optional
from ..dependencies import get_db


router = APIRouter()


@router.post(
    "/api/benches/{bench_id}/rating",
    summary="Rate a Bench",
    description="Rate a bench from 1 to 5. Requires authentication. Updates existing rating if user has already rated.",
    response_model=RatingResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"model": ErrorResponse, "description": "Authentication required"},
        404: {"model": ErrorResponse, "description": "Bench not found"},
    },
    tags=["benches"],
)
async def rate_bench(
    db: BenchDatabase = Depends(get_db),
    bench_id: int = Path(..., description="Bench candidate ID"),
    rating_data: RatingRequest = Body(...),
    user: dict = Depends(get_current_user),
) -> RatingResponse:
    """Rate a bench. Updates existing rating if user has already rated this bench."""
    user_id = user["user_id"]

    try:
        with db.get_session() as session:
            bench = session.query(BenchCandidate).filter_by(id=bench_id).first()
            if not bench:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Bench with ID {bench_id} not found",
                )

            existing_rating = (
                session.query(BenchRating)
                .filter_by(bench_candidate_id=bench_id, user_id=user_id)
                .first()
            )

            if existing_rating:
                existing_rating.rating = rating_data.rating
                existing_rating.updated_at = datetime.now(UTC)
                session.commit()
                session.refresh(existing_rating)
                return RatingResponse(
                    id=existing_rating.id,
                    bench_candidate_id=existing_rating.bench_candidate_id,
                    user_id=existing_rating.user_id,
                    rating=existing_rating.rating,
                    created_at=existing_rating.created_at,
                    updated_at=existing_rating.updated_at,
                )
            else:
                rating = BenchRating(
                    bench_candidate_id=bench_id,
                    user_id=user_id,
                    rating=rating_data.rating,
                )
                session.add(rating)
                session.commit()
                session.refresh(rating)
                return RatingResponse(
                    id=rating.id,
                    bench_candidate_id=rating.bench_candidate_id,
                    user_id=rating.user_id,
                    rating=rating.rating,
                    created_at=rating.created_at,
                    updated_at=rating.updated_at,
                )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to rate bench: {e!s}",
        ) from e


@router.delete(
    "/api/benches/{bench_id}/rating",
    summary="Remove Rating",
    description="Remove user's rating for a bench. Requires authentication.",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"model": ErrorResponse, "description": "Authentication required"},
        404: {"model": ErrorResponse, "description": "Rating not found"},
    },
    tags=["benches"],
)
async def delete_rating(
    db: BenchDatabase = Depends(get_db),
    bench_id: int = Path(..., description="Bench candidate ID"),
    user: dict = Depends(get_current_user),
) -> None:
    """Remove user's rating for a bench."""
    user_id = user["user_id"]

    try:
        with db.get_session() as session:
            rating = (
                session.query(BenchRating)
                .filter_by(bench_candidate_id=bench_id, user_id=user_id)
                .first()
            )
            if not rating:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Rating not found",
                )

            session.delete(rating)
            session.commit()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete rating: {e!s}",
        ) from e


@router.post(
    "/api/benches/{bench_id}/status",
    summary="Set Bench Status",
    description="Mark a bench as 'been', 'want_to_go', or 'favorite'. Requires authentication.",
    response_model=BenchUserStatusResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid status"},
        401: {"model": ErrorResponse, "description": "Authentication required"},
        404: {"model": ErrorResponse, "description": "Bench not found"},
    },
    tags=["benches"],
)
async def set_bench_status(
    db: BenchDatabase = Depends(get_db),
    bench_id: int = Path(..., description="Bench candidate ID"),
    status_data: BenchUserStatusRequest = Body(...),
    user: dict = Depends(get_current_user),
) -> BenchUserStatusResponse:
    """Set a status marker for a bench (been, want_to_go, favorite)."""

    try:
        bench_status = BenchUserStatus(status_data.status.lower())
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Must be one of: {', '.join([s.value for s in BenchUserStatus])}",
        ) from e

    user_id = user["user_id"]

    try:
        with db.get_session() as session:
            bench = session.query(BenchCandidate).filter_by(id=bench_id).first()
            if not bench:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Bench with ID {bench_id} not found",
                )

            existing_status = (
                session.query(BenchUserStatusRecord)
                .filter_by(
                    bench_candidate_id=bench_id,
                    user_id=user_id,
                    status=bench_status,
                )
                .first()
            )

            if existing_status:
                existing_status.updated_at = datetime.now(UTC)
                session.commit()
                session.refresh(existing_status)
                return BenchUserStatusResponse(
                    id=existing_status.id,
                    bench_candidate_id=existing_status.bench_candidate_id,
                    user_id=existing_status.user_id,
                    status=existing_status.status.value,
                    created_at=existing_status.created_at,
                    updated_at=existing_status.updated_at,
                )
            else:
                status_record = BenchUserStatusRecord(
                    bench_candidate_id=bench_id,
                    user_id=user_id,
                    status=bench_status,
                )
                session.add(status_record)
                session.commit()
                session.refresh(status_record)
                return BenchUserStatusResponse(
                    id=status_record.id,
                    bench_candidate_id=status_record.bench_candidate_id,
                    user_id=status_record.user_id,
                    status=status_record.status.value,
                    created_at=status_record.created_at,
                    updated_at=status_record.updated_at,
                )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set bench status: {e!s}",
        ) from e


@router.delete(
    "/api/benches/{bench_id}/status/{status_value}",
    summary="Remove Bench Status",
    description="Remove a status marker for a bench. Requires authentication.",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid status"},
        401: {"model": ErrorResponse, "description": "Authentication required"},
        404: {"model": ErrorResponse, "description": "Status not found"},
    },
    tags=["benches"],
)
async def remove_bench_status(
    db: BenchDatabase = Depends(get_db),
    bench_id: int = Path(..., description="Bench candidate ID"),
    status_value: str = Path(..., description="Status to remove"),
    user: dict = Depends(get_current_user),
) -> None:
    """Remove a status marker for a bench."""

    try:
        bench_status = BenchUserStatus(status_value.lower())
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Must be one of: {', '.join([s.value for s in BenchUserStatus])}",
        ) from e

    user_id = user["user_id"]

    try:
        with db.get_session() as session:
            status_record = (
                session.query(BenchUserStatusRecord)
                .filter_by(
                    bench_candidate_id=bench_id,
                    user_id=user_id,
                    status=bench_status,
                )
                .first()
            )
            if not status_record:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Status not found",
                )

            session.delete(status_record)
            session.commit()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove bench status: {e!s}",
        ) from e


@router.post(
    "/api/benches/{bench_id}/comments",
    summary="Add Comment",
    description="Add a comment to a bench. Requires authentication.",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"model": ErrorResponse, "description": "Authentication required"},
        404: {"model": ErrorResponse, "description": "Bench not found"},
    },
    tags=["benches"],
)
async def add_comment(
    db: BenchDatabase = Depends(get_db),
    bench_id: int = Path(..., description="Bench candidate ID"),
    comment_data: CommentRequest = Body(...),
    user: dict = Depends(get_current_user),
) -> CommentResponse:
    """Add a comment to a bench."""
    user_id = user["user_id"]

    try:
        with db.get_session() as session:
            bench = session.query(BenchCandidate).filter_by(id=bench_id).first()
            if not bench:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Bench with ID {bench_id} not found",
                )

            comment = BenchComment(
                bench_candidate_id=bench_id,
                user_id=user_id,
                comment=comment_data.comment,
            )
            session.add(comment)
            session.commit()
            session.refresh(comment)
            return CommentResponse(
                id=comment.id,
                bench_candidate_id=comment.bench_candidate_id,
                user_id=comment.user_id,
                comment=comment.comment,
                created_at=comment.created_at,
                updated_at=comment.updated_at,
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add comment: {e!s}",
        ) from e


@router.get(
    "/api/benches/{bench_id}/user-data",
    summary="Get Bench User Data",
    description="Get user-specific data for a bench (rating, statuses, comments) and aggregated data. Optional authentication.",
    response_model=BenchUserDataResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Bench not found"},
    },
    tags=["benches"],
)
async def get_bench_user_data(
    db: BenchDatabase = Depends(get_db),
    bench_id: int = Path(..., description="Bench candidate ID"),
    user: dict | None = Depends(get_current_user_optional),
) -> BenchUserDataResponse:
    """Get user-specific data for a bench including ratings, statuses, and comments."""
    user_id = user["user_id"] if user else None

    try:
        with db.get_session() as session:
            from sqlalchemy import func

            bench = session.query(BenchCandidate).filter_by(id=bench_id).first()
            if not bench:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Bench with ID {bench_id} not found",
                )

            user_rating = None
            if user_id:
                rating = (
                    session.query(BenchRating)
                    .filter_by(bench_candidate_id=bench_id, user_id=user_id)
                    .first()
                )
                if rating:
                    user_rating = RatingResponse(
                        id=rating.id,
                        bench_candidate_id=rating.bench_candidate_id,
                        user_id=rating.user_id,
                        rating=rating.rating,
                        created_at=rating.created_at,
                        updated_at=rating.updated_at,
                    )

            user_statuses = []
            if user_id:
                statuses = (
                    session.query(BenchUserStatusRecord)
                    .filter_by(bench_candidate_id=bench_id, user_id=user_id)
                    .all()
                )
                user_statuses = [
                    BenchUserStatusResponse(
                        id=s.id,
                        bench_candidate_id=s.bench_candidate_id,
                        user_id=s.user_id,
                        status=s.status.value,
                        created_at=s.created_at,
                        updated_at=s.updated_at,
                    )
                    for s in statuses
                ]

            comments = (
                session.query(BenchComment)
                .filter_by(bench_candidate_id=bench_id)
                .order_by(BenchComment.created_at.desc())
                .all()
            )
            user_comments = [
                CommentResponse(
                    id=c.id,
                    bench_candidate_id=c.bench_candidate_id,
                    user_id=c.user_id,
                    comment=c.comment,
                    created_at=c.created_at,
                    updated_at=c.updated_at,
                )
                for c in comments
            ]

            rating_stats = (
                session.query(
                    func.avg(BenchRating.rating).label("avg_rating"),
                    func.count(BenchRating.id).label("total_ratings"),
                )
                .filter_by(bench_candidate_id=bench_id)
                .first()
            )

            average_rating = (
                float(rating_stats.avg_rating) if rating_stats.avg_rating else None
            )
            total_ratings = rating_stats.total_ratings or 0

            return BenchUserDataResponse(
                bench_candidate_id=bench_id,
                user_rating=user_rating,
                user_statuses=user_statuses,
                user_comments=user_comments,
                average_rating=average_rating,
                total_ratings=total_ratings,
                total_comments=len(user_comments),
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get bench user data: {e!s}",
        ) from e
