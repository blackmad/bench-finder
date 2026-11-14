"""Bench listing, detail, bbox, and random endpoints."""

import logging
import math

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from bench_finder.models.enums import DataSource, DetectionSource
from bench_finder.models.unified_models import (
    BenchCandidate,
    Detection,
    DetectionItem,
    Image,
    ProcessedBench,
    ReverseGeocode,
)
from bench_finder.services.database import BenchDatabase

from ..api_models import (
    ApiDetectionItem,
    BboxBenchResponse,
    BenchListResponse,
    BenchMode,
    PaginationInfo,
    StructuredAddress,
    WebBenchData,
)
from ..dependencies import (
    DEFAULT_MIN_CONFIDENCE,
    DEFAULT_START_LAT,
    DEFAULT_START_LNG,
    PAGE_SIZE,
    get_db,
)
from ..helpers import (
    EnhancedErrorResponse,
    _safe_convert_source,
    build_image_urls,
    calculate_distance,
    get_bench_by_id,
    sort_images_by_best,
)


logger = logging.getLogger(__name__)

router = APIRouter()


async def get_high_confidence_benches_filtered(
    db: BenchDatabase,
    page: int = 0,
    page_size: int = PAGE_SIZE,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    start_lat: float = DEFAULT_START_LAT,
    start_lng: float = DEFAULT_START_LNG,
    sort_by: str = "distance",
    mode: BenchMode = BenchMode.BENCHES,
    include_detection_data: bool = False,
    source: DataSource | None = DataSource.OSM,
) -> BenchListResponse:
    """
    Get benches with configurable detection modes from all sources using SQLAlchemy ORM.
    Optimized to minimize joins and GROUP BYs using subqueries.
    """
    try:
        with db.get_session() as session:
            from sqlalchemy import case, func
            from sqlalchemy.orm import aliased
            from sqlalchemy.types import String as SAString

            is_postgresql = (
                session.bind is not None and session.bind.dialect.name == "postgresql"
            )
            if is_postgresql:
                def concat_func(expr):
                    return func.array_to_string(
                        func.array_agg(func.distinct(expr)), ","
                    )
                capture_success_value = True
            else:
                def concat_func(expr):
                    return func.group_concat(func.distinct(expr))
                capture_success_value = 1

            total_count_base = session.query(ProcessedBench.id)
            total_count_base = total_count_base.join(
                BenchCandidate,
                ProcessedBench.bench_candidate_id == BenchCandidate.id,
            )

            if source is not None:
                total_count_base = total_count_base.filter(
                    BenchCandidate.source == source
                )

            if mode == BenchMode.BENCHES:
                total_count_base = total_count_base.outerjoin(
                    Detection, ProcessedBench.best_detection_id == Detection.id
                ).filter(
                    ProcessedBench.detection_status == "detected",
                    func.coalesce(Detection.max_confidence, 0.0) >= min_confidence,
                )
            elif mode == BenchMode.NO_BENCH:
                total_count_base = total_count_base.filter(
                    ProcessedBench.detection_status == "no_bench"
                )

            total_count = total_count_base.count()

            image_subquery = (
                session.query(
                    Image.bench_candidate_id,
                    func.count(func.distinct(Image.id)).label("image_count"),
                    concat_func(Image.filename).label("image_filenames"),
                    concat_func(func.cast(Image.id, SAString)).label("image_ids"),
                )
                .filter(Image.capture_success == capture_success_value)
                .group_by(Image.bench_candidate_id)
                .subquery()
            )
            img_subq = aliased(image_subquery)

            segmentation_subquery = (
                session.query(
                    DetectionItem.detection_id,
                    func.max(
                        case(
                            (DetectionItem.__table__.c.polygon.isnot(None), 1), else_=0
                        )
                    ).label("has_segmentation"),
                )
                .group_by(DetectionItem.detection_id)
                .subquery()
            )
            seg_subq = aliased(segmentation_subquery)

            query = (
                session.query(
                    ProcessedBench.id.label("processed_bench_id"),
                    BenchCandidate.id.label("bench_candidate_id"),
                    BenchCandidate.provider_id,
                    BenchCandidate.lat,
                    BenchCandidate.lng,
                    BenchCandidate.tags,
                    BenchCandidate.source,
                    BenchCandidate.external_id,
                    func.coalesce(Detection.max_confidence, 0.0).label(
                        "best_confidence"
                    ),
                    func.coalesce(Detection.source, DetectionSource.NONE).label(
                        "detection_source"
                    ),
                    func.coalesce(img_subq.c.image_count, 0).label("image_count"),
                    func.coalesce(img_subq.c.image_filenames, "").label(
                        "image_filenames"
                    ),
                    func.coalesce(img_subq.c.image_ids, "").label("image_ids"),
                    ProcessedBench.detection_status,
                    ProcessedBench.best_image_id,
                    Detection.id.label("best_detection_id"),
                    func.coalesce(seg_subq.c.has_segmentation, 0).label(
                        "has_segmentation"
                    ),
                )
                .join(
                    BenchCandidate,
                    ProcessedBench.bench_candidate_id == BenchCandidate.id,
                )
                .outerjoin(Detection, ProcessedBench.best_detection_id == Detection.id)
                .outerjoin(img_subq, BenchCandidate.id == img_subq.c.bench_candidate_id)
                .outerjoin(seg_subq, Detection.id == seg_subq.c.detection_id)
            )

            if source is not None:
                query = query.filter(BenchCandidate.source == source)

            if mode == BenchMode.BENCHES:
                query = query.filter(
                    ProcessedBench.detection_status == "detected",
                    func.coalesce(Detection.max_confidence, 0.0) >= min_confidence,
                )
            elif mode == BenchMode.NO_BENCH:
                query = query.filter(ProcessedBench.detection_status == "no_bench")

            if sort_by == "confidence":
                query = query.order_by(
                    func.coalesce(Detection.max_confidence, 0.0).desc(),
                    ProcessedBench.id,
                )
            elif sort_by == "images":
                query = query.order_by(
                    func.coalesce(img_subq.c.image_count, 0).desc(),
                    func.coalesce(Detection.max_confidence, 0.0).desc(),
                    ProcessedBench.id,
                )
            elif sort_by == "recent":
                query = query.order_by(ProcessedBench.id.desc())
            else:  # distance (default)
                distance_expr = (BenchCandidate.lat - start_lat) * (
                    BenchCandidate.lat - start_lat
                ) + (BenchCandidate.lng - start_lng) * (BenchCandidate.lng - start_lng)
                query = query.order_by(
                    distance_expr.asc(),
                    func.coalesce(Detection.max_confidence, 0.0).desc(),
                )

            offset = page * page_size
            results = query.offset(offset).limit(page_size).all()

            reverse_geocode_map = {}
            if results:
                bench_candidate_ids_for_rg = [r.bench_candidate_id for r in results]
                reverse_geocodes = (
                    session.query(ReverseGeocode)
                    .filter(
                        ReverseGeocode.bench_candidate_id.in_(
                            bench_candidate_ids_for_rg
                        )
                    )
                    .all()
                )
                for rg in reverse_geocodes:
                    reverse_geocode_map[rg.bench_candidate_id] = rg

            images_map = {}
            if results:
                all_image_ids = set()
                for result in results:
                    image_ids_str = result.image_ids or ""
                    if image_ids_str:
                        all_image_ids.update(
                            int(x) for x in image_ids_str.split(",") if x
                        )
                if all_image_ids:
                    images = (
                        session.query(Image).filter(Image.id.in_(all_image_ids)).all()
                    )
                    images_map = {img.id: img for img in images}

            best_bbox_map = {}
            if results:
                best_detection_ids = [
                    r.best_detection_id
                    for r in results
                    if r.best_detection_id is not None
                ]
                if best_detection_ids:
                    best_bbox_query = (
                        session.query(
                            DetectionItem.detection_id,
                            DetectionItem.bbox,
                        )
                        .filter(DetectionItem.detection_id.in_(best_detection_ids))
                        .order_by(
                            DetectionItem.detection_id, DetectionItem.confidence.desc()
                        )
                        .all()
                    )
                    seen_detection_ids = set()
                    for detection_id, bbox_data in best_bbox_query:
                        if detection_id not in seen_detection_ids and bbox_data:
                            seen_detection_ids.add(detection_id)
                            if isinstance(bbox_data, dict):
                                from bench_finder.models.unified_models import (
                                    BoundingBox,
                                )

                                best_bbox_map[detection_id] = BoundingBox(**bbox_data)
                            else:
                                best_bbox_map[detection_id] = bbox_data

            detection_items_map = {}
            if include_detection_data:
                bench_candidate_ids = [r.bench_candidate_id for r in results]
                if bench_candidate_ids:
                    detection_items_query = (
                        session.query(
                            DetectionItem,
                            Image.bench_candidate_id,
                        )
                        .join(Detection, DetectionItem.detection_id == Detection.id)
                        .join(Image, Detection.image_id == Image.id)
                        .filter(Image.bench_candidate_id.in_(bench_candidate_ids))
                        .order_by(DetectionItem.confidence.desc())
                        .all()
                    )
                    for item, bc_id in detection_items_query:
                        if bc_id not in detection_items_map:
                            detection_items_map[bc_id] = []
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
                        detection_items_map[bc_id].append(
                            ApiDetectionItem(
                                detection_id=item.detection_id,
                                confidence=item.confidence,
                                bbox=bbox,
                                class_name=item.class_name,
                                polygon=polygon,
                            )
                        )

            benches = []
            for result in results:
                bench_candidate_id = result.bench_candidate_id
                best_confidence = result.best_confidence or 0.0
                detection_source = result.detection_source or DetectionSource.NONE

                image_filenames_str = result.image_filenames or ""
                image_ids_str = result.image_ids or ""
                image_filenames = (
                    image_filenames_str.split(",") if image_filenames_str else []
                )
                image_ids = (
                    [int(x) for x in image_ids_str.split(",") if x]
                    if image_ids_str
                    else []
                )

                image_filenames, image_ids = sort_images_by_best(
                    image_filenames, image_ids, result.best_image_id
                )

                images_for_bench = [
                    images_map[img_id] for img_id in image_ids if img_id in images_map
                ]
                image_urls = build_image_urls(images_for_bench, image_ids)

                has_segmentation = bool(result.has_segmentation)

                distance = calculate_distance(
                    start_lat, start_lng, result.lat, result.lng
                )

                detection_items = (
                    detection_items_map.get(bench_candidate_id)
                    if include_detection_data
                    else None
                )

                best_bbox = (
                    best_bbox_map.get(result.best_detection_id)
                    if result.best_detection_id
                    else None
                )

                reverse_geocode = None
                rg = reverse_geocode_map.get(bench_candidate_id)
                if rg:
                    reverse_geocode = StructuredAddress(
                        formatted_address=rg.formatted_address,
                        street_number=rg.street_number,
                        street_name=rg.street_name,
                        city=rg.city,
                        state=rg.state,
                        postal_code=rg.postal_code,
                        country=rg.country,
                    )

                roboflow_confidence = 0.0
                ultralytics_confidence = 0.0
                mapillary_confidence = 0.0
                if detection_source == DetectionSource.ROBOFLOW:
                    roboflow_confidence = best_confidence
                elif detection_source == DetectionSource.ULTRALYTICS:
                    ultralytics_confidence = best_confidence
                elif detection_source == DetectionSource.MAPILLARY:
                    mapillary_confidence = best_confidence

                bench_data = WebBenchData(
                    id=result.processed_bench_id,
                    provider_id=result.provider_id,
                    lat=result.lat,
                    lng=result.lng,
                    tags=result.tags or {},
                    source=_safe_convert_source(result.source),
                    external_id=result.external_id,
                    bench_found=result.detection_status == "detected",
                    best_confidence=round(best_confidence, 3),
                    roboflow_confidence=round(roboflow_confidence, 3),
                    ultralytics_confidence=round(ultralytics_confidence, 3),
                    mapillary_confidence=round(mapillary_confidence, 3),
                    detection_type=detection_source,
                    has_segmentation=has_segmentation,
                    image_count=result.image_count or 0,
                    image_filenames=image_filenames,
                    image_ids=image_ids,
                    image_urls=image_urls,
                    best_image_id=result.best_image_id,
                    best_detection_id=result.best_detection_id,
                    best_bbox=best_bbox,
                    distance_meters=round(distance),
                    distance_km=round(distance / 1000, 2),
                    reverse_geocode=reverse_geocode,
                    detection_items=detection_items,
                )

                benches.append(bench_data)

            pagination = PaginationInfo(
                page=page,
                page_size=page_size,
                total_count=total_count,
                total_pages=math.ceil(total_count / page_size),
                has_next=(page + 1) * page_size < total_count,
            )

            return BenchListResponse(benches=benches, pagination=pagination)

    except Exception as e:
        print(f"Error getting high confidence benches: {e}")
        import traceback

        traceback.print_exc()
        return BenchListResponse(
            benches=[],
            pagination=PaginationInfo(
                page=0,
                page_size=page_size,
                total_count=0,
                total_pages=0,
                has_next=False,
            ),
        )


def _get_bbox_filtered_bench_candidate_ids(
    session: Session, south: float, north: float, west: float, east: float
) -> list[int] | None:
    """
    Get bench_candidate IDs within bounding box using spatial index if available.

    Returns None if spatial index is not available, indicating fallback to regular filtering.
    Returns list of IDs if spatial query succeeds.
    """
    try:
        is_postgresql = (
            session.bind is not None and session.bind.dialect.name == "postgresql"
        )

        if is_postgresql:
            result = session.execute(
                text("SELECT COUNT(*) FROM pg_extension WHERE extname = 'postgis';")
            ).scalar()

            if result > 0:
                query = text("""
                    SELECT id FROM bench_candidates
                    WHERE ST_MakePoint(lng, lat)::geography && ST_MakeEnvelope(:west, :south, :east, :north, 4326)::geography
                """)
                result = session.execute(
                    query, {"west": west, "east": east, "south": south, "north": north}
                ).fetchall()

                return [row[0] for row in result] if result else []
            else:
                return None

        else:
            result = session.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='rtree_bench_candidates';"
                )
            ).fetchone()

            if not result:
                return None

            query = text("""
                SELECT id FROM rtree_bench_candidates
                WHERE minLng <= :east AND maxLng >= :west
                  AND minLat <= :north AND maxLat >= :south
            """)
            result = session.execute(
                query, {"west": west, "east": east, "south": south, "north": north}
            ).fetchall()

            return [row[0] for row in result] if result else []

    except Exception as e:
        logger.debug(
            f"Spatial index query failed, falling back to regular filtering: {e}"
        )
        return None


# BENCH ENDPOINTS
@router.get(
    "/api/benches",
    summary="List Benches",
    description="Get paginated list of benches with high confidence detections, sorted by various criteria",
    response_model=BenchListResponse,
    responses={
        400: {
            "model": EnhancedErrorResponse,
            "description": "Invalid query parameters",
        },
        500: {"model": EnhancedErrorResponse, "description": "Internal server error"},
    },
    tags=["benches"],
)
async def get_benches(
    db: BenchDatabase = Depends(get_db),
    page: int = Query(0, ge=0, le=1000, description="Page number (0-based)"),
    page_size: int = Query(
        PAGE_SIZE, ge=1, le=50, description="Items per page (max 50)"
    ),
    min_confidence: float = Query(
        DEFAULT_MIN_CONFIDENCE,
        ge=0.0,
        le=1.0,
        description="Minimum detection confidence",
    ),
    start_lat: float = Query(
        DEFAULT_START_LAT,
        ge=-90.0,
        le=90.0,
        description="Starting latitude for distance sorting",
    ),
    start_lng: float = Query(
        DEFAULT_START_LNG,
        ge=-180.0,
        le=180.0,
        description="Starting longitude for distance sorting",
    ),
    sort_by: str = Query(
        "distance",
        pattern="^(distance|confidence|images|recent)$",
        description="Sort criteria",
    ),
    source: DataSource | None = Query(
        DataSource.OSM,
        description="Filter by data source: 'osm' or 'mapillary' (default: OSM, None for all sources)",
    ),
    mode: BenchMode = Query(
        BenchMode.BENCHES,
        description="Return mode: 'benches' (detected), 'no_bench' (not detected), or 'both'",
    ),
    include_detection_data: bool = Query(
        False,
        description="Include detection items (bbox, polygon) in response (default: False)",
    ),
) -> BenchListResponse:
    """
    Retrieve a paginated list of benches with configurable detection modes.

    **Sorting Options:**
    - `distance`: Sort by distance from start_lat/start_lng (default)
    - `confidence`: Sort by highest detection confidence first
    - `images`: Sort by number of images per bench
    - `recent`: Sort by most recently added benches
    """
    try:
        result = await get_high_confidence_benches_filtered(
            db=db,
            page=page,
            page_size=page_size,
            min_confidence=min_confidence,
            start_lat=start_lat,
            start_lng=start_lng,
            sort_by=sort_by,
            mode=mode,
            include_detection_data=include_detection_data,
            source=source,
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve benches: {e!s}",
        ) from e


@router.get(
    "/api/benches/random",
    summary="Get Random Bench",
    description="Get a randomly selected bench that meets the specified criteria",
    response_model=WebBenchData,
    responses={
        404: {
            "model": EnhancedErrorResponse,
            "description": "No benches found matching criteria",
        },
        500: {"model": EnhancedErrorResponse, "description": "Internal server error"},
    },
    tags=["benches"],
)
async def get_random_bench(
    db: BenchDatabase = Depends(get_db),
    min_confidence: float = Query(
        DEFAULT_MIN_CONFIDENCE,
        ge=0.0,
        le=1.0,
        description="Minimum detection confidence",
    ),
    mode: BenchMode = Query(
        BenchMode.BENCHES,
        description="Return mode: 'benches' (detected), 'no_bench' (not detected), or 'both'",
    ),
    include_detection_data: bool = Query(
        False,
        description="Include detection items (bbox, polygon) in response (default: False)",
    ),
    source: DataSource | None = Query(
        DataSource.OSM,
        description="Filter by data source: 'osm' or 'mapillary' (default: OSM, None for all sources)",
    ),
) -> WebBenchData:
    """Get a randomly selected bench that meets the specified criteria."""
    try:
        with db.get_session() as session:
            from sqlalchemy import func

            base_query = (
                session.query(ProcessedBench)
                .join(
                    BenchCandidate,
                    ProcessedBench.bench_candidate_id == BenchCandidate.id,
                )
                .outerjoin(Detection, ProcessedBench.best_detection_id == Detection.id)
            )

            if source is not None:
                base_query = base_query.filter(BenchCandidate.source == source)

            if mode == BenchMode.BENCHES:
                base_query = base_query.filter(
                    ProcessedBench.detection_status == "detected",
                    Detection.max_confidence >= min_confidence,
                )
            elif mode == BenchMode.NO_BENCH:
                base_query = base_query.filter(
                    ProcessedBench.detection_status == "no_bench"
                )

            random_bench = base_query.order_by(func.random()).first()

            if not random_bench:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No benches found matching the specified criteria",
                )

            bench_data = get_bench_by_id(
                bench_id=random_bench.id,
                db=db,
                include_detection_data=include_detection_data,
            )

            return bench_data

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get random bench: {e!s}",
        ) from e


@router.get(
    "/api/bench/{bench_id}",
    summary="Get Bench by ID",
    description="Get detailed information for a specific bench by its ID",
    response_model=WebBenchData,
    responses={
        404: {
            "model": EnhancedErrorResponse,
            "description": "Bench not found",
        },
        500: {"model": EnhancedErrorResponse, "description": "Internal server error"},
    },
    tags=["benches"],
)
async def get_bench_by_id_endpoint(
    db: BenchDatabase = Depends(get_db),
    bench_id: int = Path(..., description="Bench ID to retrieve"),
    include_detection_data: bool = Query(
        False,
        description="Include detection items (bbox, polygon) in response (default: False)",
    ),
) -> WebBenchData:
    """Get detailed information for a specific bench by its ID."""
    bench_data = get_bench_by_id(
        bench_id=bench_id,
        db=db,
        include_detection_data=include_detection_data,
    )

    return bench_data


@router.get(
    "/api/benches/bbox",
    summary="Get Benches in Bounding Box",
    description="Get benches within a geographic bounding box for map applications",
    response_model=BboxBenchResponse,
    responses={
        400: {
            "model": EnhancedErrorResponse,
            "description": "Invalid bounding box parameters",
        },
        500: {"model": EnhancedErrorResponse, "description": "Internal server error"},
    },
    tags=["benches"],
)
async def get_benches_in_bbox(
    db: BenchDatabase = Depends(get_db),
    north: float = Query(
        ..., ge=-90.0, le=90.0, description="Northern latitude boundary"
    ),
    south: float = Query(
        ..., ge=-90.0, le=90.0, description="Southern latitude boundary"
    ),
    east: float = Query(
        ..., ge=-180.0, le=180.0, description="Eastern longitude boundary"
    ),
    west: float = Query(
        ..., ge=-180.0, le=180.0, description="Western longitude boundary"
    ),
    min_confidence: float = Query(
        DEFAULT_MIN_CONFIDENCE,
        ge=0.0,
        le=1.0,
        description="Minimum detection confidence",
    ),
    source: DataSource | None = Query(
        DataSource.OSM,
        description="Filter by data source: 'osm' or 'mapillary' (default: OSM, None for all sources)",
    ),
    mode: BenchMode = Query(
        BenchMode.BENCHES,
        description="Return mode: 'benches' (detected), 'no_bench' (not detected), or 'both'",
    ),
    sort_by: str = Query(
        "distance",
        pattern="^(distance|confidence|images|recent)$",
        description="Sort criteria",
    ),
    limit: int = Query(200, ge=1, le=500, description="Maximum number of results"),
    include_detection_data: bool = Query(
        False,
        description="Include detection items (bbox, polygon) in response (default: False)",
    ),
) -> BboxBenchResponse:
    """Get benches within a geographic bounding box."""
    try:
        if north <= south:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="North boundary must be greater than south boundary",
            )

        if east <= west:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="East boundary must be greater than west boundary",
            )

        with db.get_session() as session:
            from sqlalchemy import case, func
            from sqlalchemy.orm import aliased
            from sqlalchemy.types import String as SAString

            rtree_ids = _get_bbox_filtered_bench_candidate_ids(
                session, south, north, west, east
            )

            if rtree_ids is not None and not rtree_ids:
                return BboxBenchResponse(
                    benches=[],
                    total_count=0,
                    bbox={"north": north, "south": south, "east": east, "west": west},
                )

            is_postgresql = (
                session.bind is not None and session.bind.dialect.name == "postgresql"
            )
            if is_postgresql:
                def concat_func(expr):
                    return func.array_to_string(
                        func.array_agg(func.distinct(expr)), ","
                    )
                capture_success_value = True
            else:
                def concat_func(expr):
                    return func.group_concat(func.distinct(expr))
                capture_success_value = 1

            image_subquery = (
                session.query(
                    Image.bench_candidate_id,
                    func.count(func.distinct(Image.id)).label("image_count"),
                    concat_func(Image.filename).label("image_filenames"),
                    concat_func(func.cast(Image.id, SAString)).label("image_ids"),
                )
                .filter(Image.capture_success == capture_success_value)
                .group_by(Image.bench_candidate_id)
                .subquery()
            )
            img_subq = aliased(image_subquery)

            segmentation_subquery = (
                session.query(
                    DetectionItem.detection_id,
                    func.max(
                        case(
                            (DetectionItem.__table__.c.polygon.isnot(None), 1), else_=0
                        )
                    ).label("has_segmentation"),
                )
                .group_by(DetectionItem.detection_id)
                .subquery()
            )
            seg_subq = aliased(segmentation_subquery)

            query = (
                session.query(
                    ProcessedBench.id.label("processed_bench_id"),
                    BenchCandidate.id.label("bench_candidate_id"),
                    BenchCandidate.provider_id,
                    BenchCandidate.lat,
                    BenchCandidate.lng,
                    BenchCandidate.tags,
                    BenchCandidate.source,
                    BenchCandidate.external_id,
                    func.coalesce(Detection.max_confidence, 0.0).label(
                        "best_confidence"
                    ),
                    func.coalesce(Detection.source, DetectionSource.NONE).label(
                        "detection_source"
                    ),
                    func.coalesce(img_subq.c.image_count, 0).label("image_count"),
                    func.coalesce(img_subq.c.image_filenames, "").label(
                        "image_filenames"
                    ),
                    func.coalesce(img_subq.c.image_ids, "").label("image_ids"),
                    ProcessedBench.detection_status,
                    ProcessedBench.best_image_id,
                    Detection.id.label("best_detection_id"),
                    func.coalesce(seg_subq.c.has_segmentation, 0).label(
                        "has_segmentation"
                    ),
                )
                .join(
                    BenchCandidate,
                    ProcessedBench.bench_candidate_id == BenchCandidate.id,
                )
                .outerjoin(Detection, ProcessedBench.best_detection_id == Detection.id)
                .outerjoin(img_subq, BenchCandidate.id == img_subq.c.bench_candidate_id)
                .outerjoin(seg_subq, Detection.id == seg_subq.c.detection_id)
            )

            if rtree_ids is not None:
                query = query.filter(BenchCandidate.id.in_(rtree_ids))
            else:
                query = query.filter(
                    BenchCandidate.lat.between(south, north),
                    BenchCandidate.lng.between(west, east),
                )

            if source is not None:
                query = query.filter(BenchCandidate.source == source)

            if mode == BenchMode.BENCHES:
                query = query.filter(
                    ProcessedBench.detection_status == "detected",
                    func.coalesce(Detection.max_confidence, 0.0) >= min_confidence,
                )
            elif mode == BenchMode.NO_BENCH:
                query = query.filter(ProcessedBench.detection_status == "no_bench")

            center_lat = (north + south) / 2
            center_lng = (east + west) / 2

            if sort_by == "confidence":
                query = query.order_by(
                    func.coalesce(Detection.max_confidence, 0.0).desc(),
                    ProcessedBench.id,
                )
            elif sort_by == "images":
                query = query.order_by(
                    func.coalesce(img_subq.c.image_count, 0).desc(),
                    func.coalesce(Detection.max_confidence, 0.0).desc(),
                    ProcessedBench.id,
                )
            elif sort_by == "recent":
                query = query.order_by(ProcessedBench.id.desc())
            else:  # distance (default)
                distance_expr = (BenchCandidate.lat - center_lat) * (
                    BenchCandidate.lat - center_lat
                ) + (BenchCandidate.lng - center_lng) * (
                    BenchCandidate.lng - center_lng
                )
                query = query.order_by(
                    distance_expr.asc(),
                    func.coalesce(Detection.max_confidence, 0.0).desc(),
                )

            results = query.limit(limit).all()

            reverse_geocode_map = {}
            if results:
                bench_candidate_ids_for_rg = [r.bench_candidate_id for r in results]
                if bench_candidate_ids_for_rg:
                    reverse_geocodes = (
                        session.query(ReverseGeocode)
                        .filter(
                            ReverseGeocode.bench_candidate_id.in_(
                                bench_candidate_ids_for_rg
                            )
                        )
                        .all()
                    )
                    for rg in reverse_geocodes:
                        reverse_geocode_map[rg.bench_candidate_id] = rg

            images_map = {}
            if results:
                all_image_ids = set()
                for result in results:
                    image_ids_str = result.image_ids or ""
                    if image_ids_str:
                        all_image_ids.update(
                            int(x) for x in image_ids_str.split(",") if x
                        )
                if all_image_ids:
                    images = (
                        session.query(Image).filter(Image.id.in_(all_image_ids)).all()
                    )
                    images_map = {img.id: img for img in images}

            best_bbox_map = {}
            if results:
                best_detection_ids = [
                    r.best_detection_id
                    for r in results
                    if r.best_detection_id is not None
                ]
                if best_detection_ids:
                    best_bbox_query = (
                        session.query(
                            DetectionItem.detection_id,
                            DetectionItem.bbox,
                        )
                        .filter(DetectionItem.detection_id.in_(best_detection_ids))
                        .order_by(
                            DetectionItem.detection_id, DetectionItem.confidence.desc()
                        )
                        .all()
                    )
                    seen_detection_ids = set()
                    for detection_id, bbox_data in best_bbox_query:
                        if detection_id not in seen_detection_ids and bbox_data:
                            seen_detection_ids.add(detection_id)
                            if isinstance(bbox_data, dict):
                                from bench_finder.models.unified_models import (
                                    BoundingBox,
                                )

                                best_bbox_map[detection_id] = BoundingBox(**bbox_data)
                            else:
                                best_bbox_map[detection_id] = bbox_data

            detection_items_map = {}
            if include_detection_data:
                bench_candidate_ids = [r.bench_candidate_id for r in results]
                if bench_candidate_ids:
                    detection_items_query = (
                        session.query(
                            DetectionItem,
                            Image.bench_candidate_id,
                        )
                        .join(Detection, DetectionItem.detection_id == Detection.id)
                        .join(Image, Detection.image_id == Image.id)
                        .filter(Image.bench_candidate_id.in_(bench_candidate_ids))
                        .order_by(DetectionItem.confidence.desc())
                        .all()
                    )
                    for item, bc_id in detection_items_query:
                        if bc_id not in detection_items_map:
                            detection_items_map[bc_id] = []
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
                        detection_items_map[bc_id].append(
                            ApiDetectionItem(
                                detection_id=item.detection_id,
                                confidence=item.confidence,
                                bbox=bbox,
                                class_name=item.class_name,
                                polygon=polygon,
                            )
                        )

            benches = []
            for result in results:
                bench_candidate_id = result.bench_candidate_id
                best_confidence = result.best_confidence or 0.0
                detection_source = result.detection_source or DetectionSource.NONE

                image_filenames_str = result.image_filenames or ""
                image_ids_str = result.image_ids or ""
                image_filenames = (
                    image_filenames_str.split(",") if image_filenames_str else []
                )
                image_ids = (
                    [int(x) for x in image_ids_str.split(",") if x]
                    if image_ids_str
                    else []
                )

                image_filenames, image_ids = sort_images_by_best(
                    image_filenames, image_ids, result.best_image_id
                )

                images_for_bench = [
                    images_map[img_id] for img_id in image_ids if img_id in images_map
                ]
                image_urls = build_image_urls(images_for_bench, image_ids)

                has_segmentation = bool(result.has_segmentation)

                distance = calculate_distance(
                    center_lat, center_lng, result.lat, result.lng
                )

                detection_items = (
                    detection_items_map.get(bench_candidate_id)
                    if include_detection_data
                    else None
                )

                best_bbox = (
                    best_bbox_map.get(result.best_detection_id)
                    if result.best_detection_id
                    else None
                )

                roboflow_confidence = 0.0
                ultralytics_confidence = 0.0
                mapillary_confidence = 0.0
                if detection_source == DetectionSource.ROBOFLOW:
                    roboflow_confidence = best_confidence
                elif detection_source == DetectionSource.ULTRALYTICS:
                    ultralytics_confidence = best_confidence
                elif detection_source == DetectionSource.MAPILLARY:
                    mapillary_confidence = best_confidence

                reverse_geocode = None
                rg = reverse_geocode_map.get(bench_candidate_id)
                if rg:
                    reverse_geocode = StructuredAddress(
                        formatted_address=rg.formatted_address,
                        street_number=rg.street_number,
                        street_name=rg.street_name,
                        city=rg.city,
                        state=rg.state,
                        postal_code=rg.postal_code,
                        country=rg.country,
                    )

                bench_data = WebBenchData(
                    id=result.processed_bench_id,
                    provider_id=result.provider_id,
                    lat=result.lat,
                    lng=result.lng,
                    tags=result.tags or {},
                    source=_safe_convert_source(result.source),
                    external_id=result.external_id,
                    bench_found=result.detection_status == "detected",
                    best_confidence=round(best_confidence, 3),
                    roboflow_confidence=round(roboflow_confidence, 3),
                    ultralytics_confidence=round(ultralytics_confidence, 3),
                    mapillary_confidence=round(mapillary_confidence, 3),
                    detection_type=detection_source,
                    has_segmentation=has_segmentation,
                    image_count=result.image_count or 0,
                    image_filenames=image_filenames,
                    image_ids=image_ids,
                    image_urls=image_urls,
                    best_image_id=result.best_image_id,
                    best_detection_id=result.best_detection_id,
                    best_bbox=best_bbox,
                    distance_meters=round(distance),
                    distance_km=round(distance / 1000, 2),
                    reverse_geocode=reverse_geocode,
                    detection_items=detection_items,
                )

                benches.append(bench_data)

            return BboxBenchResponse(
                benches=benches,
                total_count=len(benches),
                bbox={"north": north, "south": south, "east": east, "west": west},
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get benches in bounding box: {e!s}",
        ) from e
