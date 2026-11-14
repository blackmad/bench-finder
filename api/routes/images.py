"""Image serving and detection visualization endpoints."""

import os

from fastapi import APIRouter, Depends, HTTPException, Path, status
from fastapi.responses import FileResponse

from bench_finder.config import IMAGES_DIR
from bench_finder.models.enums import DetectionSource
from bench_finder.models.unified_models import (
    BenchCandidate,
    Detection,
    Image,
    ProcessedBench,
)
from bench_finder.services.database import BenchDatabase

from ..api_models import (
    ApiDetectionItem,
    BenchDetectionData,
    ImageListResponse,
    ImageResponse,
    ImageWithDetectionData,
    SegmentationData,
)
from ..dependencies import get_db
from ..helpers import EnhancedErrorResponse


router = APIRouter()


@router.get(
    "/images/{filename}",
    summary="Serve Bench Images",
    description="Serve bench images from the images directory",
    response_class=FileResponse,
    responses={
        404: {"model": EnhancedErrorResponse, "description": "Image not found"},
        500: {"model": EnhancedErrorResponse, "description": "Internal server error"},
    },
    tags=["images"],
)
async def serve_image(
    db: BenchDatabase = Depends(get_db),
    filename: str = Path(..., description="Image filename"),
) -> FileResponse:
    """Serve bench images from the configured storage backend (local or Firebase)."""
    try:
        with db.get_session() as session:
            image = session.query(Image).filter(Image.filename == filename).first()

            if image and image.firebase_url:
                from fastapi.responses import RedirectResponse

                return RedirectResponse(
                    url=image.firebase_url, status_code=status.HTTP_302_FOUND
                )

        images_path = os.path.abspath(IMAGES_DIR)
        file_path = os.path.join(images_path, filename)

        if not os.path.abspath(file_path).startswith(images_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Image not found"
            )

        if not os.path.exists(file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Image '{filename}' not found",
            )

        return FileResponse(
            file_path,
            media_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=3600"},
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to serve image: {e!s}",
        ) from e


@router.get(
    "/api/image/{image_id}/segmentation",
    summary="Get Detection Visualization Data",
    description="Get detection visualization data for a specific image (segmentation and bounding boxes)",
    response_model=SegmentationData,
    responses={
        404: {
            "model": EnhancedErrorResponse,
            "description": "Image not found",
        },
        500: {"model": EnhancedErrorResponse, "description": "Internal server error"},
    },
    tags=["images"],
)
async def get_image_segmentation(
    db: BenchDatabase = Depends(get_db),
    image_id: int = Path(..., ge=1, description="Image ID"),
) -> SegmentationData:
    """Get detection visualization data for a specific image."""
    try:
        with db.get_session() as session:
            from sqlalchemy.orm import joinedload

            image = (
                session.query(Image)
                .options(
                    joinedload(Image.detections).joinedload(Detection.detection_items)
                )
                .filter(Image.id == image_id)
                .first()
            )

            if not image:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Image with ID {image_id} not found",
                )

            detections = [d for d in image.detections if d.has_bench]

            if not detections:
                return SegmentationData(
                    filename=image.filename or "unknown",
                    detection_type="bounding_box",
                    detection_items=[],
                    image_shape=None,
                    segmentation_available=False,
                    bounding_box_available=False,
                    confidence_score=0.0,
                    source=DetectionSource.NONE,
                )

            all_detection_items = []
            max_confidence = 0.0
            detection_sources = set()
            has_segmentation = False
            has_bounding_box = False

            for detection in detections:
                for item in detection.detection_items:
                    bbox = None
                    if item.bbox:
                        if isinstance(item.bbox, dict):
                            from bench_finder.models.unified_models import BoundingBox

                            bbox = BoundingBox(**item.bbox)
                        else:
                            bbox = item.bbox

                    polygon = None
                    if item.polygon:
                        if isinstance(item.polygon, dict):
                            from bench_finder.models.unified_models import Polygon

                            polygon = Polygon(**item.polygon)
                        else:
                            polygon = item.polygon

                    detection_item = ApiDetectionItem(
                        detection_id=item.detection_id,
                        confidence=item.confidence,
                        bbox=bbox,
                        class_name=item.class_name,
                        polygon=polygon,
                    )
                    all_detection_items.append(detection_item)

                    if item.polygon:
                        has_segmentation = True
                    if item.bbox:
                        has_bounding_box = True

                max_confidence = max(max_confidence, detection.max_confidence or 0.0)
                detection_sources.add(detection.source)

            if has_segmentation and has_bounding_box:
                detection_type = "both"
            elif has_segmentation:
                detection_type = "segmentation"
            else:
                detection_type = "bounding_box"

            primary_source = DetectionSource.ROBOFLOW
            if detection_sources:
                best_detection = max(detections, key=lambda d: d.max_confidence or 0.0)
                primary_source = best_detection.source

            return SegmentationData(
                filename=image.filename or "unknown",
                detection_type=detection_type,
                detection_items=all_detection_items,
                image_shape=None,
                segmentation_available=has_segmentation,
                bounding_box_available=has_bounding_box,
                confidence_score=max_confidence,
                source=primary_source,
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve detection data: {e!s}",
        ) from e


@router.get(
    "/api/bench/{bench_id}/images",
    summary="Get Bench Images",
    description="Get all images for a specific bench with metadata",
    response_model=ImageListResponse,
    responses={
        404: {"model": EnhancedErrorResponse, "description": "Bench not found"},
        500: {"model": EnhancedErrorResponse, "description": "Internal server error"},
    },
    tags=["images"],
)
async def get_bench_images(
    db: BenchDatabase = Depends(get_db),
    bench_id: int = Path(..., ge=1, description="Bench ID"),
) -> ImageListResponse:
    """Get all images associated with a specific bench."""
    try:
        with db.get_session() as session:
            processed_bench = (
                session.query(ProcessedBench)
                .filter(ProcessedBench.id == bench_id)
                .first()
            )

            if not processed_bench:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"ProcessedBench with ID {bench_id} not found",
                )

            bench_candidate_id = processed_bench.bench_candidate_id

            is_postgresql = (
                session.bind is not None and session.bind.dialect.name == "postgresql"
            )
            capture_success_value = True if is_postgresql else 1

            images_query = (
                session.query(Image)
                .filter(
                    Image.bench_candidate_id == bench_candidate_id,
                    Image.capture_success == capture_success_value,
                )
                .order_by(Image.heading)
                .all()
            )

            images = []
            for image in images_query:
                image_response = ImageResponse(
                    id=image.id,
                    bench_id=bench_id,
                    heading=image.heading,
                    filepath=image.filepath,
                    filename=image.filename,
                    file_size=image.file_size,
                    capture_success=image.capture_success,
                    capture_error=image.capture_error,
                    created_at=image.created_at,
                )
                images.append(image_response)

            return ImageListResponse(images=images)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve bench images: {e!s}",
        ) from e


@router.get(
    "/api/bench/{bench_id}/detections",
    summary="Get Bench Detection Data",
    description="Get comprehensive detection data for a specific bench including all images and detection items",
    response_model=BenchDetectionData,
    responses={
        404: {"model": EnhancedErrorResponse, "description": "Bench not found"},
        500: {"model": EnhancedErrorResponse, "description": "Internal server error"},
    },
    tags=["images"],
)
async def get_bench_detections(
    db: BenchDatabase = Depends(get_db),
    bench_id: int = Path(..., ge=1, description="Bench ID"),
) -> BenchDetectionData:
    """Get comprehensive detection data for a specific bench."""
    try:
        with db.get_session() as session:
            from sqlalchemy.orm import joinedload

            processed_bench = (
                session.query(ProcessedBench)
                .filter(ProcessedBench.id == bench_id)
                .first()
            )

            if not processed_bench:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"ProcessedBench with ID {bench_id} not found",
                )

            bench_candidate_id = processed_bench.bench_candidate_id

            bench_candidate = (
                session.query(BenchCandidate)
                .filter(BenchCandidate.id == bench_candidate_id)
                .first()
            )

            if not bench_candidate:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"BenchCandidate with ID {bench_candidate_id} not found",
                )

            images_query = (
                session.query(Image)
                .options(
                    joinedload(Image.detections).joinedload(Detection.detection_items)
                )
                .filter(Image.bench_candidate_id == bench_candidate_id)
                .order_by(Image.heading)
                .all()
            )

            if not images_query:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No images found for bench ID {bench_id}",
                )

            images_data = []
            detection_sources = set()
            best_confidence = 0.0
            images_with_detections = 0

            for image in images_query:
                detection_items = []

                for detection in image.detections:
                    for item in detection.detection_items:
                        bbox = None
                        if item.bbox:
                            if isinstance(item.bbox, dict):
                                from bench_finder.models.unified_models import (
                                    BoundingBox,
                                )

                                bbox = BoundingBox(**item.bbox)
                            else:
                                bbox = item.bbox

                        polygon = None
                        if item.polygon:
                            if isinstance(item.polygon, dict):
                                from bench_finder.models.unified_models import Polygon

                                polygon = Polygon(**item.polygon)
                            else:
                                polygon = item.polygon

                        detection_item = ApiDetectionItem(
                            detection_id=item.detection_id,
                            confidence=item.confidence,
                            bbox=bbox,
                            class_name=item.class_name,
                            polygon=polygon,
                        )
                        detection_items.append(detection_item)

                        best_confidence = max(best_confidence, item.confidence)
                        detection_sources.add(detection.source)

                if detection_items:
                    images_with_detections += 1

                image_data = ImageWithDetectionData(
                    image_id=image.id,
                    filename=image.filename,
                    heading=image.heading,
                    capture_success=image.capture_success,
                    detection_items=detection_items,
                )
                images_data.append(image_data)

            return BenchDetectionData(
                bench_id=bench_id,
                bench_lat=bench_candidate.lat,
                bench_lng=bench_candidate.lng,
                total_images=len(images_data),
                images_with_detections=images_with_detections,
                best_confidence=best_confidence,
                detection_sources=list(detection_sources),
                images=images_data,
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve bench detection data: {e!s}",
        ) from e
