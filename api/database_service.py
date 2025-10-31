"""
API-specific database service layer.

This module contains database operations that return API response models.
It depends on both the core database service and API models, keeping the
circular dependency broken.
"""

import logging

from sqlalchemy import func

from api.api_models import (
    BenchWithDetections,
    DetectionResponse,
    ImageWithDetections,
    SearchResponse,
    SearchResults,
)
from bench_finder.models.unified_models import (
    BenchCandidate,
    Detection,
    Image,
    Search,
)
from bench_finder.services.database import BenchDatabase


logger = logging.getLogger(__name__)


class ApiDatabaseService:
    """API-specific database service for transforming database models to API models."""

    def __init__(self, db: BenchDatabase | None = None):
        """
        Initialize the API database service.

        Args:
            db: Optional BenchDatabase instance. If not provided, creates a new one.
        """
        self.db = db or BenchDatabase()

    def get_search_results(self, search_id: int) -> SearchResults | None:
        """
        Get comprehensive results for a search.

        Args:
            search_id: ID of the search

        Returns:
            SearchResults schema with search results and statistics
        """
        try:
            with self.db.get_session() as session:
                # Get search info
                search = session.query(Search).filter(Search.id == search_id).first()

                if not search:
                    return None

                # Get bench count
                bench_count = (
                    session.query(BenchCandidate)
                    .filter(BenchCandidate.search_id == search_id)
                    .count()
                )

                # Get image stats
                image_stats = (
                    session.query(
                        func.count(Image.id).label("total_images"),
                        func.sum(Image.capture_success).label("successful_images"),
                    )
                    .join(BenchCandidate, Image.bench_candidate_id == BenchCandidate.id)
                    .filter(BenchCandidate.search_id == search_id)
                    .first()
                )

                # Get detection stats
                detection_stats = (
                    session.query(
                        func.count(Detection.id).label("total_detections"),
                        func.sum(Detection.has_bench).label("images_with_benches"),
                        func.max(Detection.max_confidence).label("best_confidence"),
                    )
                    .join(Image, Detection.image_id == Image.id)
                    .join(BenchCandidate, Image.bench_candidate_id == BenchCandidate.id)
                    .filter(BenchCandidate.search_id == search_id)
                    .first()
                )

                return SearchResults(
                    search=SearchResponse(
                        id=search.id,
                        query=search.query,
                        start_lat=search.start_lat,
                        start_lng=search.start_lng,
                        search_radius=search.search_radius,
                        created_at=search.created_at,
                        completed_at=search.completed_at,
                        status=search.status,
                    ),
                    bench_count=bench_count,
                    total_images=image_stats.total_images if image_stats else 0,
                    successful_images=image_stats.successful_images
                    if image_stats
                    else 0,
                    total_detections=detection_stats.total_detections
                    if detection_stats
                    else 0,
                    images_with_benches=detection_stats.images_with_benches
                    if detection_stats
                    else 0,
                    best_confidence=detection_stats.best_confidence
                    if detection_stats
                    else 0.0,
                )

        except Exception:
            logger.exception("Error getting search results")
            return None

    def get_benches_with_detections(self, search_id: int) -> list[BenchWithDetections]:
        """
        Get all benches with their images and detections for a search.

        Args:
            search_id: ID of the search

        Returns:
            List of BenchWithDetections schemas with nested image and detection data
        """
        try:
            with self.db.get_session() as session:
                # Get all benches for this search with eagerly loaded relationships
                benches = (
                    session.query(BenchCandidate)
                    .filter(BenchCandidate.search_id == search_id)
                    .all()
                )

                result = []
                for bench in benches:
                    # Get images with their detections
                    images_with_detections = [
                        ImageWithDetections(
                            id=image.id,
                            bench_id=image.bench_candidate_id,
                            heading=image.heading,
                            filepath=image.filepath,
                            filename=image.filename,
                            file_size=image.file_size,
                            capture_success=image.capture_success,
                            capture_error=image.capture_error,
                            created_at=image.created_at,
                            detections=[
                                DetectionResponse(
                                    id=d.id,
                                    image_id=d.image_id,
                                    has_bench=d.has_bench,
                                    bench_count=d.bench_count,
                                    max_confidence=d.max_confidence,
                                    detection_success=d.detection_success,
                                    detection_error=d.detection_error,
                                    model_id=d.model_id,
                                    confidence_threshold=d.confidence_threshold,
                                    source=d.source,
                                    external_detection_id=d.external_detection_id,
                                    model_url=d.model_url,
                                    iou_threshold=d.iou_threshold,
                                    image_size=d.image_size,
                                    inference_time=d.inference_time,
                                    preprocess_time=d.preprocess_time,
                                    postprocess_time=d.postprocess_time,
                                    created_at=d.created_at,
                                    detection_items=d.detection_items,
                                )
                                for d in image.detections
                            ],
                        )
                        for image in bench.images
                    ]

                    bench_with_detections = BenchWithDetections(
                        id=bench.id,
                        search_id=bench.search_id,
                        provider_id=bench.provider_id,
                        lat=bench.lat,
                        lng=bench.lng,
                        tags=bench.tags or {},
                        source=bench.source,
                        external_id=bench.external_id,
                        created_at=bench.created_at,
                        images=images_with_detections,
                    )
                    result.append(bench_with_detections)

                return result

        except Exception:
            logger.exception("Error getting benches with detections")
            return []
