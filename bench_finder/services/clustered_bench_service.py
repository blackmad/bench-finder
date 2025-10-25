#!/usr/bin/env python3
"""
Clustered bench data service for API endpoints.

This module provides functionality to retrieve and serve clustered bench data
through the API, combining cluster information with individual bench details.
"""

import contextlib
import json
import logging
import math

from config import DATABASE_PATH
from core.clustering import BenchClusterer
from database import BenchDatabase

from api.api_models import (
    ClusteredBenchData,
    ClusteredBenchListResponse,
    ClusterInfo,
    PaginationInfo,
    WebBenchData,
)
from models.unified_models import (
    DataSource,
    DetectionSource,
)


logger = logging.getLogger(__name__)

# Configuration
DEFAULT_MIN_CONFIDENCE = 0.8
DEFAULT_START_LAT = 52.3613577  # Amsterdam, Netherlands
DEFAULT_START_LNG = 4.8666322
PAGE_SIZE = 20


def calculate_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Calculate the great circle distance between two points using Haversine formula.
    Returns distance in meters.
    """
    # Convert decimal degrees to radians
    lat1, lng1, lat2, lng2 = map(math.radians, [lat1, lng1, lat2, lng2])

    # Haversine formula
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))

    # Earth's radius in meters
    r = 6371000
    return c * r


class ClusteredBenchService:
    """Service for retrieving and serving clustered bench data."""

    def __init__(self, db_path: str | None = None):
        """
        Initialize the clustered bench service.

        Args:
            db_path: Path to the database (defaults to config DATABASE_PATH)
        """
        self.db_path = db_path or DATABASE_PATH
        self.clusterer = BenchClusterer(db_path=self.db_path)

    def _get_bench_details_by_ids(
        self, bench_ids: list[int]
    ) -> dict[int, WebBenchData]:
        """
        Get detailed bench information for a list of bench IDs.

        Args:
            bench_ids: List of bench IDs to retrieve

        Returns:
            Dictionary mapping bench_id to WebBenchData
        """
        if not bench_ids:
            return {}

        try:
            db = BenchDatabase(self.db_path)
            with db._get_connection() as conn:
                # Create placeholders for the IN clause
                placeholders = ",".join("?" for _ in bench_ids)

                query = f"""
                    SELECT
                        b.id, b.provider_id, b.lat, b.lng, b.tags, b.source, b.external_id,
                        COALESCE(rf_data.max_confidence, 0) as roboflow_confidence,
                        COALESCE(ul_data.max_confidence, 0) as ultralytics_confidence,
                        COALESCE(mp_data.max_confidence, 0) as mapillary_confidence,
                        COUNT(DISTINCT i.id) as image_count,
                        GROUP_CONCAT(DISTINCT i.filename) as image_filenames,
                        GROUP_CONCAT(DISTINCT i.id) as image_ids,
                        CASE
                            WHEN COALESCE(rf_data.max_confidence, 0) >= COALESCE(ul_data.max_confidence, 0) AND COALESCE(rf_data.max_confidence, 0) >= COALESCE(mp_data.max_confidence, 0)
                            THEN COALESCE(rf_data.max_confidence, 0)
                            WHEN COALESCE(ul_data.max_confidence, 0) >= COALESCE(mp_data.max_confidence, 0)
                            THEN COALESCE(ul_data.max_confidence, 0)
                            ELSE COALESCE(mp_data.max_confidence, 0)
                        END as best_confidence
                    FROM benches b
                    LEFT JOIN images i ON b.id = i.bench_id AND i.capture_success = 1
                    LEFT JOIN (
                        SELECT image_id, MAX(max_confidence) as max_confidence
                        FROM detections
                        WHERE has_bench = 1
                        GROUP BY image_id
                    ) rf_data ON i.id = rf_data.image_id
                    LEFT JOIN (
                        SELECT image_id, MAX(max_confidence) as max_confidence
                        FROM ultralytics_detections
                        WHERE has_bench = 1
                        GROUP BY image_id
                    ) ul_data ON i.id = ul_data.image_id
                    LEFT JOIN (
                        SELECT image_id, MAX(max_confidence) as max_confidence
                        FROM detections
                        WHERE has_bench = 1 AND source = 'mapillary'
                        GROUP BY image_id
                    ) mp_data ON i.id = mp_data.image_id
                    WHERE b.id IN ({placeholders})
                    GROUP BY b.id
                """

                rows = conn.execute(query, bench_ids).fetchall()

                bench_details = {}
                for row in rows:
                    # Parse tags if available
                    tags = {}
                    if row["tags"]:
                        with contextlib.suppress(json.JSONDecodeError):
                            tags = json.loads(row["tags"])

                    # Get image filenames and IDs
                    image_filenames = (
                        row["image_filenames"].split(",")
                        if row["image_filenames"]
                        else []
                    )
                    image_ids = (
                        [int(x) for x in row["image_ids"].split(",") if x]
                        if row["image_ids"]
                        else []
                    )

                    # Determine best confidence and detection type
                    roboflow_conf = row["roboflow_confidence"] or 0
                    ultralytics_conf = row["ultralytics_confidence"] or 0
                    mapillary_conf = row["mapillary_confidence"] or 0
                    best_confidence = max(
                        roboflow_conf, ultralytics_conf, mapillary_conf
                    )

                    # Determine detection type based on source and confidence
                    if row["source"] == DataSource.MAPILLARY:
                        detection_type = DetectionSource.MAPILLARY
                    elif (
                        ultralytics_conf > 0
                        and ultralytics_conf >= roboflow_conf * 0.95
                    ):
                        detection_type = DetectionSource.ULTRALYTICS
                    else:
                        detection_type = (
                            DetectionSource.ROBOFLOW
                            if roboflow_conf > ultralytics_conf
                            else DetectionSource.ULTRALYTICS
                        )

                    bench_data = WebBenchData(
                        id=row["id"],
                        provider_id=row["provider_id"],
                        lat=row["lat"],
                        lng=row["lng"],
                        tags=tags,
                        source=row["source"] or DataSource.OSM,
                        external_id=row["external_id"],
                        best_confidence=round(best_confidence, 3),
                        roboflow_confidence=round(roboflow_conf, 3),
                        ultralytics_confidence=round(ultralytics_conf, 3),
                        mapillary_confidence=round(mapillary_conf, 3),
                        detection_type=detection_type,
                        has_segmentation=ultralytics_conf > 0 or mapillary_conf > 0,
                        image_count=row["image_count"],
                        image_filenames=image_filenames,
                        image_ids=image_ids,
                        distance_meters=0,  # Will be calculated by caller
                        distance_km=0.0,  # Will be calculated by caller
                    )

                    bench_details[row["id"]] = bench_data

                return bench_details

        except Exception:
            logger.exception("Failed to get bench details")
            return {}

    def _build_clustered_bench_data(
        self, cluster_row: dict, reference_lat: float, reference_lng: float
    ) -> ClusteredBenchData | None:
        """
        Build ClusteredBenchData from database row and reference point.

        Args:
            cluster_row: Database row from clustered_benches table
            reference_lat: Reference latitude for distance calculations
            reference_lng: Reference longitude for distance calculations

        Returns:
            ClusteredBenchData object or None if error
        """
        try:
            # Parse cluster data
            bench_ids = json.loads(cluster_row["bench_ids"])
            sources = json.loads(cluster_row["sources"])

            # Get detailed bench information
            bench_details = self._get_bench_details_by_ids(bench_ids)

            if not bench_details:
                logger.warning(
                    f"No bench details found for cluster {cluster_row['id']}"
                )
                return None

            # Calculate distances for all benches
            all_benches = []
            representative_bench = None

            for bench_id in bench_ids:
                if bench_id not in bench_details:
                    logger.warning(f"Bench {bench_id} not found in details")
                    continue

                bench = bench_details[bench_id]

                # Calculate distance from reference point
                distance = calculate_distance(
                    reference_lat, reference_lng, bench.lat, bench.lng
                )
                bench.distance_meters = round(distance)
                bench.distance_km = round(distance / 1000, 2)

                # Add clustering information to the bench
                bench.cluster_id = cluster_row["id"]
                bench.cluster_center_lat = cluster_row["center_lat"]
                bench.cluster_center_lng = cluster_row["center_lng"]
                bench.cluster_bench_count = cluster_row["bench_count"]
                bench.cluster_max_distance_meters = cluster_row["max_distance_meters"]
                bench.is_cluster_representative = (
                    bench_id == cluster_row["best_bench_id"]
                )

                all_benches.append(bench)

                # Find the representative bench
                if bench_id == cluster_row["best_bench_id"]:
                    representative_bench = bench

            if not representative_bench and all_benches:
                # Fallback: use the first bench if best_bench_id not found
                representative_bench = all_benches[0]
                representative_bench.is_cluster_representative = True
                logger.warning(
                    f"Best bench ID {cluster_row['best_bench_id']} not found in cluster {cluster_row['id']}, using fallback"
                )

            if not representative_bench:
                logger.error(
                    f"No representative bench found for cluster {cluster_row['id']}"
                )
                return None

            # Create cluster info
            cluster_info = ClusterInfo(
                cluster_id=cluster_row["id"],
                center_lat=cluster_row["center_lat"],
                center_lng=cluster_row["center_lng"],
                bench_count=cluster_row["bench_count"],
                max_distance_meters=cluster_row["max_distance_meters"],
                avg_confidence=cluster_row["avg_confidence"],
                sources=sources,
                created_at=cluster_row["created_at"],
                updated_at=cluster_row["updated_at"],
            )

            # Calculate distance to cluster center
            cluster_distance = calculate_distance(
                reference_lat,
                reference_lng,
                cluster_row["center_lat"],
                cluster_row["center_lng"],
            )

            return ClusteredBenchData(
                cluster=cluster_info,
                representative_bench=representative_bench,
                all_benches=all_benches,
                distance_to_cluster_center=cluster_distance,
            )

        except Exception:
            logger.exception("Failed to build clustered bench data")
            return None

    def get_clustered_benches_filtered(
        self,
        page: int = 0,
        page_size: int = PAGE_SIZE,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
        start_lat: float = DEFAULT_START_LAT,
        start_lng: float = DEFAULT_START_LNG,
        source_filter: str | None = None,
        sort_by: str = "distance",
    ) -> ClusteredBenchListResponse:
        """
        Get clustered benches with filtering and pagination.

        Args:
            page: Page number (0-based)
            page_size: Items per page
            min_confidence: Minimum confidence threshold
            start_lat: Reference latitude for distance calculations
            start_lng: Reference longitude for distance calculations
            source_filter: Optional source filter ('osm', 'mapillary')
            sort_by: Sort criteria ('distance', 'confidence', 'images', 'recent')

        Returns:
            ClusteredBenchListResponse with paginated results
        """
        try:
            db = BenchDatabase(self.db_path)
            with db._get_connection() as conn:
                # Build WHERE clause for filtering
                where_conditions = ["cb.avg_confidence >= ?"]
                query_params = [min_confidence]

                if source_filter:
                    where_conditions.append("cb.sources LIKE ?")
                    query_params.append(f'%"{source_filter}"%')

                where_clause = " AND ".join(where_conditions)

                # Determine sorting clause
                if sort_by == "confidence":
                    order_clause = "cb.avg_confidence DESC, cb.id"
                elif sort_by == "images":
                    # For clusters, we'll use bench_count as a proxy for image richness
                    order_clause = "cb.bench_count DESC, cb.avg_confidence DESC, cb.id"
                elif sort_by == "recent":
                    order_clause = "cb.id DESC"
                else:  # distance (default)
                    # Calculate distance from reference point to cluster center
                    order_clause = f"((cb.center_lat - {start_lat}) * (cb.center_lat - {start_lat}) + (cb.center_lng - {start_lng}) * (cb.center_lng - {start_lng})) ASC, cb.avg_confidence DESC"

                # Get total count
                count_query = f"""
                    SELECT COUNT(*) as total
                    FROM clustered_benches cb
                    WHERE {where_clause}
                """
                total_count = conn.execute(count_query, query_params).fetchone()[
                    "total"
                ]

                # Get paginated results
                offset = page * page_size
                data_query = f"""
                    SELECT *
                    FROM clustered_benches cb
                    WHERE {where_clause}
                    ORDER BY {order_clause}
                    LIMIT ? OFFSET ?
                """

                rows = conn.execute(
                    data_query, [*query_params, page_size, offset]
                ).fetchall()

                # Build clustered bench data
                clustered_benches = []
                for row in rows:
                    clustered_data = self._build_clustered_bench_data(
                        row, start_lat, start_lng
                    )
                    if clustered_data:
                        clustered_benches.append(clustered_data)

                # Create pagination info
                pagination = PaginationInfo(
                    page=page,
                    page_size=page_size,
                    total_count=total_count,
                    total_pages=math.ceil(total_count / page_size),
                    has_next=(page + 1) * page_size < total_count,
                )

                # Get clustering metadata
                clustering_stats = self.clusterer.get_clustering_stats()
                clustering_info = {
                    "clustering_enabled": True,
                    "clustering_distance_meters": clustering_stats[
                        "clustering_distance_meters"
                    ],
                    "total_clusters": clustering_stats["total_clusters"],
                    "total_benches": clustering_stats["total_benches"],
                    "clustered_benches": clustering_stats["clustered_benches"],
                }

                return ClusteredBenchListResponse(
                    clustered_benches=clustered_benches,
                    pagination=pagination,
                    clustering_info=clustering_info,
                )

        except Exception as e:
            logger.exception("Failed to get clustered benches")
            # Return empty response on error
            return ClusteredBenchListResponse(
                clustered_benches=[],
                pagination=PaginationInfo(
                    page=0,
                    page_size=page_size,
                    total_count=0,
                    total_pages=0,
                    has_next=False,
                ),
                clustering_info={"clustering_enabled": False, "error": str(e)},
            )

    def get_clustered_benches_in_bbox(
        self,
        north: float,
        south: float,
        east: float,
        west: float,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
        source_filter: str | None = None,
        sort_by: str = "distance",
        limit: int = 200,
    ) -> ClusteredBenchListResponse:
        """
        Get clustered benches within a bounding box.

        Args:
            north: Northern latitude boundary
            south: Southern latitude boundary
            east: Eastern longitude boundary
            west: Western longitude boundary
            min_confidence: Minimum confidence threshold
            source_filter: Optional source filter
            sort_by: Sort criteria
            limit: Maximum results to return

        Returns:
            ClusteredBenchListResponse with results in bbox
        """
        try:
            # Calculate center point for distance calculations
            center_lat = (north + south) / 2
            center_lng = (east + west) / 2

            db = BenchDatabase(self.db_path)
            with db._get_connection() as conn:
                # Build WHERE clause
                where_conditions = [
                    "cb.avg_confidence >= ?",
                    "cb.center_lat BETWEEN ? AND ?",
                    "cb.center_lng BETWEEN ? AND ?",
                ]
                query_params = [min_confidence, south, north, west, east]

                if source_filter:
                    where_conditions.append("cb.sources LIKE ?")
                    query_params.append(f'%"{source_filter}"%')

                where_clause = " AND ".join(where_conditions)

                # Determine sorting
                if sort_by == "confidence":
                    order_clause = "cb.avg_confidence DESC, cb.id"
                elif sort_by == "images":
                    order_clause = "cb.bench_count DESC, cb.avg_confidence DESC, cb.id"
                elif sort_by == "recent":
                    order_clause = "cb.id DESC"
                else:  # distance
                    order_clause = f"((cb.center_lat - {center_lat}) * (cb.center_lat - {center_lat}) + (cb.center_lng - {center_lng}) * (cb.center_lng - {center_lng})) ASC, cb.avg_confidence DESC"

                # Get results within bounding box
                query = f"""
                    SELECT *
                    FROM clustered_benches cb
                    WHERE {where_clause}
                    ORDER BY {order_clause}
                    LIMIT ?
                """

                rows = conn.execute(query, [*query_params, limit]).fetchall()

                # Build clustered bench data
                clustered_benches = []
                for row in rows:
                    clustered_data = self._build_clustered_bench_data(
                        row, center_lat, center_lng
                    )
                    if clustered_data:
                        clustered_benches.append(clustered_data)

                # Create simple pagination (no pages for bbox queries)
                pagination = PaginationInfo(
                    page=0,
                    page_size=len(clustered_benches),
                    total_count=len(clustered_benches),
                    total_pages=1,
                    has_next=False,
                )

                clustering_info = {
                    "clustering_enabled": True,
                    "bbox": {
                        "north": north,
                        "south": south,
                        "east": east,
                        "west": west,
                    },
                    "center_lat": center_lat,
                    "center_lng": center_lng,
                }

                return ClusteredBenchListResponse(
                    clustered_benches=clustered_benches,
                    pagination=pagination,
                    clustering_info=clustering_info,
                )

        except Exception as e:
            logger.exception("Failed to get clustered benches in bbox")
            return ClusteredBenchListResponse(
                clustered_benches=[],
                pagination=PaginationInfo(
                    page=0, page_size=0, total_count=0, total_pages=0, has_next=False
                ),
                clustering_info={"clustering_enabled": False, "error": str(e)},
            )

    def is_clustering_available(self) -> bool:
        """
        Check if clustering data is available.

        Returns:
            True if clusters exist in the database
        """
        try:
            stats = self.clusterer.get_clustering_stats()
            return stats["total_clusters"] > 0
        except Exception:
            logger.exception("Failed to check clustering availability")
            return False
