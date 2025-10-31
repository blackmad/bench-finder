"""
Mapillary service for integrating bench detections with the existing database.
"""

import logging
from threading import Lock

from mapillary_client import MapillaryBenchDetector
from mapillary_client import MapillaryDetection as MapillaryDetectionAPI
from mapillary_client import MapillaryImage as MapillaryImageAPI
from schemas import (
    BenchListResponse,
    PaginationInfo,
    SourceStatistics,
    WebBenchData,
)
from sqlalchemy import func
from sqlalchemy.orm import Session

from bench_finder.models.enums import DataSource
from bench_finder.models.unified_models import (
    BenchCandidate,
    Detection,
    Image,
    Search,
    create_database_engine,
    create_database_session,
)


logger = logging.getLogger(__name__)


class MapillaryBenchService:
    """Service for managing Mapillary bench detections."""

    def __init__(
        self,
        database_path: str,
        mapillary_access_token: str,
        images_dir: str = "images",
    ):
        """
        Initialize Mapillary service.

        Args:
            database_path: Path to SQLite database
            mapillary_access_token: Mapillary API access token
            images_dir: Directory to store downloaded images
        """
        self.engine = create_database_engine(database_path=database_path)
        self.images_dir = images_dir
        self.mapillary_client = MapillaryBenchDetector(
            mapillary_access_token, images_dir
        )

    def get_session(self) -> Session:
        """Get database session."""
        return create_database_session(self.engine)

    def _get_or_create_mapillary_search(
        self, session: Session, center_lat: float, center_lng: float, radius_meters: int
    ) -> int:
        """Get or create a dummy search entry for Mapillary benches."""
        # Look for an existing Mapillary search
        existing_search = (
            session.query(Search)
            .filter(
                Search.query == "Mapillary API",
                Search.start_lat == center_lat,
                Search.start_lng == center_lng,
                Search.search_radius == radius_meters,
            )
            .first()
        )

        if existing_search:
            return existing_search.id

        # Create a new dummy search for this Mapillary query
        dummy_search = Search(
            query="Mapillary API",
            start_lat=center_lat,
            start_lng=center_lng,
            search_radius=radius_meters,
            status="completed",  # Mark as completed since Mapillary API calls are immediate
        )
        session.add(dummy_search)
        session.flush()  # Get the ID

        logger.info(
            f"Created dummy search entry {dummy_search.id} for Mapillary benches"
        )
        return dummy_search.id

    def search_and_store_benches(
        self,
        center_lat: float,
        center_lng: float,
        radius_meters: int = 1000,
        limit: int = 1000,
    ) -> BenchListResponse:
        """
        Search for bench detections and store them in the database.

        Args:
            center_lat: Center latitude
            center_lng: Center longitude
            radius_meters: Search radius in meters
            limit: Maximum number of images to fetch

        Returns:
            BenchListResponse with found detections
        """
        logger.info(
            f"Searching Mapillary for benches around {center_lat}, {center_lng} within {radius_meters}m"
        )

        # Fetch from Mapillary API
        api_images = self.mapillary_client.search_benches_by_location(
            center_lat, center_lng, radius_meters
        )

        # Download images for the bench detections
        logger.info(
            f"Downloading images for {len(api_images)} Mapillary images with bench detections"
        )
        download_results = self.mapillary_client.download_images_for_benches(api_images)
        download_success_map = {
            r["image_id"]: r for r in download_results if r.get("success", False)
        }

        # Store in database as benches
        stored_benches = []
        with self.get_session() as session:
            try:
                # Get or create a dummy search entry for Mapillary benches
                dummy_search_id = self._get_or_create_mapillary_search(
                    session, center_lat, center_lng, radius_meters
                )

                for api_image in api_images:
                    # Get download result for this image
                    download_result = download_success_map.get(api_image.image_id)

                    for api_detection in api_image.detections:
                        try:
                            db_bench = self._store_mapillary_bench(
                                session,
                                api_image,
                                api_detection,
                                center_lat,
                                center_lng,
                                dummy_search_id,
                                download_result,
                            )
                            if db_bench:
                                stored_benches.append(db_bench)
                        except Exception as bench_error:
                            logger.warning(
                                f"Failed to store bench from image {api_image.image_id}: {bench_error}"
                            )
                            continue  # Skip this bench and continue with others

                session.commit()
                logger.info(
                    f"Successfully committed {len(stored_benches)} Mapillary benches"
                )

            except Exception:
                logger.exception("Error during Mapillary bench storage, rolling back")
                session.rollback()
                raise

        # Create pagination info
        pagination = PaginationInfo(
            page=0,
            page_size=len(stored_benches),
            total_count=len(stored_benches),
            total_pages=1,
            has_next=False,
        )

        response = BenchListResponse(benches=stored_benches, pagination=pagination)

        logger.info(f"Stored {len(stored_benches)} benches from Mapillary detections")
        return response

    def _store_mapillary_bench(
        self,
        session: Session,
        api_image: MapillaryImageAPI,
        api_detection: MapillaryDetectionAPI,
        center_lat: float,
        center_lng: float,
        search_id: int,
        download_result: dict | None = None,
    ) -> WebBenchData | None:
        """Store a Mapillary detection as a bench in the database."""
        try:
            # Check if bench already exists (by external_id)
            existing_bench = (
                session.query(BenchCandidate)
                .filter(
                    BenchCandidate.external_id == api_image.image_id,
                    BenchCandidate.source == DataSource.MAPILLARY,
                )
                .first()
            )

            if existing_bench:
                # Calculate distance for existing bench
                distance = self._calculate_distance(
                    center_lat, center_lng, existing_bench.lat, existing_bench.lng
                )
                return self._bench_to_web_data(existing_bench, distance)

            # Create new bench from Mapillary detection
            db_bench = BenchCandidate(
                search_id=search_id,  # Use dummy search ID for Mapillary benches
                provider_id=api_image.image_id,  # Use image_id as provider_id for Mapillary
                lat=api_image.coordinates[1],  # API returns [lng, lat]
                lng=api_image.coordinates[0],
                tags={
                    "mapillary_image_id": api_image.image_id,
                    "detection_value": api_detection.value,
                },
                source=DataSource.MAPILLARY,
                external_id=api_image.image_id,
            )
            session.add(db_bench)
            session.flush()  # Get the ID

            # Create image entry for the Mapillary image
            if download_result and download_result.get("success", False):
                # Use downloaded image info
                db_image = Image(
                    bench_candidate_id=db_bench.id if db_bench.id is not None else 0,
                    heading=0,  # We don't have heading info from Mapillary detections
                    filepath=download_result["filepath"],
                    filename=download_result["filename"],
                    file_size=download_result["file_size"],
                    capture_success=True,
                    capture_error=None,
                )
            else:
                # Create dummy image entry if download failed
                db_image = Image(
                    bench_candidate_id=db_bench.id if db_bench.id is not None else 0,
                    heading=0,
                    filepath=None,
                    filename=None,
                    file_size=None,
                    capture_success=False,
                    capture_error=download_result.get("error", "Image download failed")
                    if download_result
                    else "No download attempted",
                )
            session.add(db_image)
            session.flush()

            # Store the detection
            db_detection = Detection(
                image_id=db_image.id,
                has_bench=True,
                bench_count=1,
                max_confidence=api_detection.confidence,
                detections=[
                    {
                        "detection_id": api_detection.detection_id,
                        "value": api_detection.value,
                        "geometry_encoded": api_detection.geometry_encoded,
                        "geometry_decoded": api_detection.geometry_decoded,
                    }
                ],
                detection_success=True,
                detection_error=None,
                model_id="mapillary",
                confidence_threshold=0.0,  # Mapillary doesn't use thresholds
                source=DataSource.MAPILLARY,
                external_detection_id=api_detection.detection_id,
            )
            session.add(db_detection)

            # Calculate distance and convert to WebBenchData
            distance = self._calculate_distance(
                center_lat, center_lng, db_bench.lat, db_bench.lng
            )

            # Prepare image info for WebBenchData
            image_filenames = (
                [download_result["filename"]]
                if download_result and download_result.get("success")
                else []
            )
            image_ids = [db_image.id]

            return self._bench_to_web_data(
                db_bench, distance, image_filenames, image_ids
            )

        except Exception:
            logger.exception(f"Error storing Mapillary bench {api_image.image_id}")
            return None

    def _calculate_distance(
        self, lat1: float, lng1: float, lat2: float, lng2: float
    ) -> float:
        """Calculate distance between two points in meters."""
        import math

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

    def _bench_to_web_data(
        self,
        bench: BenchCandidate,
        distance: float,
        image_filenames: list[str] | None = None,
        image_ids: list[int] | None = None,
    ) -> WebBenchData:
        """Convert a Bench model to WebBenchData schema."""
        return WebBenchData(
            id=bench.id,
            provider_id=bench.provider_id,
            lat=bench.lat,
            lng=bench.lng,
            tags=bench.tags or {},
            source=bench.source,
            external_id=bench.external_id,
            best_confidence=1.0 if bench.source == "mapillary" else 0.0,
            roboflow_confidence=0.0,
            ultralytics_confidence=0.0,
            mapillary_confidence=1.0 if bench.source == "mapillary" else 0.0,
            detection_type="mapillary" if bench.source == "mapillary" else "unknown",
            has_segmentation=bench.source == "mapillary",  # Mapillary has geometry
            image_count=len(image_filenames) if image_filenames else 1,
            image_filenames=image_filenames or [],
            image_ids=image_ids or [],
            distance_meters=round(distance),
            distance_km=round(distance / 1000, 2),
        )

    def get_detection_statistics(
        self,
        center_lat: float | None = None,
        center_lng: float | None = None,
        radius_meters: int | None = None,
        source: DataSource | None = None,
    ) -> SourceStatistics:
        """
        Get statistics about stored bench detections.

        Args:
            center_lat: Optional center latitude for area-specific stats
            center_lng: Optional center longitude for area-specific stats
            radius_meters: Optional radius for area-specific stats
            source: Filter by source ('osm' or 'mapillary'), None for all

        Returns:
            Statistics about the detections
        """
        with self.get_session() as session:
            query = session.query(BenchCandidate)

            # Apply source filter
            if source:
                query = query.filter(BenchCandidate.source == source)

            # Apply location filter if provided
            if all([center_lat, center_lng, radius_meters]):
                radius_deg = radius_meters / 111000
                query = query.filter(
                    BenchCandidate.lat >= center_lat - radius_deg,
                    BenchCandidate.lat <= center_lat + radius_deg,
                    BenchCandidate.lng >= center_lng - radius_deg,
                    BenchCandidate.lng <= center_lng + radius_deg,
                )

            # Get bench count
            total_benches = query.count()

            # Get detection count from the same benches
            bench_ids = [b.id for b in query.all()]
            detection_count = 0
            if bench_ids:
                detection_count = (
                    session.query(Detection)
                    .join(Image)
                    .filter(
                        Image.bench_candidate_id.in_(bench_ids),
                        Detection.has_bench is True,
                    )
                    .count()
                )

            # Calculate unique locations (rounded to ~100m precision)
            location_stats = (
                session.query(
                    func.round(BenchCandidate.lat, 3).label("lat_bucket"),
                    func.round(BenchCandidate.lng, 3).label("lng_bucket"),
                )
                .filter(BenchCandidate.id.in_(bench_ids) if bench_ids else False)
                .distinct()
                .all()
            )

            unique_locations = len(location_stats)

            # Estimate coverage area (very rough approximation)
            coverage_area = 0.0
            if unique_locations > 0:
                # Each location bucket is roughly 0.001 degrees = ~100m
                # Area per bucket ≈ 0.01 km²
                coverage_area = unique_locations * 0.01

            return SourceStatistics(
                source=source or "all",
                total_benches=total_benches,
                total_detections=detection_count,
                avg_detections_per_bench=detection_count / max(total_benches, 1),
                unique_locations=unique_locations,
                coverage_area_km2=coverage_area,
            )

    def get_bench_by_mapillary_id(self, mapillary_image_id: str) -> WebBenchData | None:
        """
        Get a bench by its Mapillary image ID.

        Args:
            mapillary_image_id: Mapillary image ID

        Returns:
            WebBenchData or None if not found
        """
        with self.get_session() as session:
            bench = (
                session.query(BenchCandidate)
                .filter(
                    BenchCandidate.external_id == mapillary_image_id,
                    BenchCandidate.source == DataSource.MAPILLARY,
                )
                .first()
            )

            if bench:
                # Use bench location as center for distance calculation
                return self._bench_to_web_data(bench, 0.0)

            return None


def create_mapillary_service(
    database_path: str, mapillary_access_token: str
) -> MapillaryBenchService:
    """Create a Mapillary service instance."""
    return MapillaryBenchService(database_path, mapillary_access_token)


# --- Singleton helpers -----------------------------------------------------
_mapillary_service_singleton: MapillaryBenchService | None = None
_singleton_lock: Lock = Lock()


def initialize_mapillary_service(
    database_path: str,
    mapillary_access_token: str,
    images_dir: str = "images",
) -> MapillaryBenchService:
    """Initialize or return the singleton Mapillary service.

    Thread-safe. Subsequent calls return the same instance.
    """
    global _mapillary_service_singleton  # noqa: PLW0603
    if _mapillary_service_singleton is not None:
        return _mapillary_service_singleton

    with _singleton_lock:
        if _mapillary_service_singleton is None:
            _mapillary_service_singleton = MapillaryBenchService(
                database_path, mapillary_access_token, images_dir
            )
    return _mapillary_service_singleton


def get_mapillary_service() -> MapillaryBenchService | None:
    """Get the singleton Mapillary service if initialized, else None."""
    return _mapillary_service_singleton


def reset_mapillary_service_for_testing() -> None:
    """Reset the singleton (intended for tests)."""
    global _mapillary_service_singleton  # noqa: PLW0603
    with _singleton_lock:
        _mapillary_service_singleton = None
