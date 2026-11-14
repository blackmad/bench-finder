"""Reporting endpoints for bad detections and missing benches."""

import os

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Request, status

from bench_finder.config import IMAGES_DIR
from bench_finder.models.enums import BenchReportType, LocationMethod
from bench_finder.models.unified_models import (
    BenchCandidate,
    Image,
    ProcessedBench,
)
from bench_finder.services.database import BenchDatabase

from ..api_models import (
    MissingBenchReportResponse,
    ReportResponse,
)
from ..dependencies import get_db
from ..helpers import EnhancedErrorResponse


router = APIRouter()


@router.post(
    "/api/benches/{bench_id}/report",
    summary="Report Bad Bench Detection",
    description="Report a bad bench detection with optional description and image data",
    response_model=ReportResponse,
    responses={
        400: {
            "model": EnhancedErrorResponse,
            "description": "Invalid bench ID or request data",
        },
        404: {"model": EnhancedErrorResponse, "description": "Bench not found"},
        500: {"model": EnhancedErrorResponse, "description": "Internal server error"},
    },
    tags=["reporting"],
)
async def report_bad_bench(
    request: Request,
    db: BenchDatabase = Depends(get_db),
    bench_id: int = Path(..., gt=0, description="Bench ID to report"),
    report_type: BenchReportType = Body(
        BenchReportType.BAD_DETECTION, description="Type of report"
    ),
    description: str | None = Body(
        None, description="Optional description of the issue"
    ),
    image_id: int | None = Body(None, description="Specific image ID being reported"),
    user_location_lat: float | None = Body(None, description="User's GPS latitude"),
    user_location_lng: float | None = Body(None, description="User's GPS longitude"),
) -> ReportResponse:
    """Report a bad bench detection."""
    try:
        import shutil
        from datetime import datetime

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

            reported_image_filename = None
            if image_id:
                image = (
                    session.query(Image)
                    .filter(
                        Image.id == image_id,
                        Image.bench_candidate_id == bench_candidate_id,
                    )
                    .first()
                )

                if image and image.filename:
                    source_path = os.path.join(IMAGES_DIR, image.filename)
                    if os.path.exists(source_path):
                        reports_dir = os.path.join(IMAGES_DIR, "reports")
                        os.makedirs(reports_dir, exist_ok=True)

                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        reported_image_filename = (
                            f"report_{bench_id}_{timestamp}_{image.filename}"
                        )
                        dest_path = os.path.join(reports_dir, reported_image_filename)

                        try:
                            shutil.copy2(source_path, dest_path)
                        except Exception as e:
                            print(f"Warning: Failed to copy reported image: {e}")
                            reported_image_filename = None

            user_agent = request.headers.get("user-agent", "")
            client_host = request.client.host if request.client else None

            from bench_finder.models.unified_models import BenchReport

            report = BenchReport(
                bench_candidate_id=bench_candidate_id,
                image_id=image_id,
                report_type=report_type,
                description=description,
                user_agent=user_agent,
                ip_address=client_host,
                user_location_lat=user_location_lat,
                user_location_lng=user_location_lng,
                reported_image_filename=reported_image_filename,
                extra_metadata={
                    "processed_bench_id": bench_id,
                    "bench_source": bench_candidate.source,
                    "bench_provider_id": bench_candidate.provider_id,
                    "timestamp": datetime.now().isoformat(),
                },
            )

            session.add(report)
            session.commit()
            session.refresh(report)
            report_id = report.id

            return ReportResponse(
                success=True,
                report_id=report_id,
                message="Thank you for your report. It will be reviewed by our team.",
                bench_id=bench_id,
                report_type=report_type,
                created_at=datetime.now().isoformat(),
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit report: {e!s}",
        ) from e


@router.post(
    "/api/missing-benches",
    summary="Report Missing Bench",
    description="Report a missing bench at a specific location with optional photo",
    response_model=MissingBenchReportResponse,
    responses={
        400: {
            "model": EnhancedErrorResponse,
            "description": "Invalid location or request data",
        },
        413: {"model": EnhancedErrorResponse, "description": "Image file too large"},
        500: {"model": EnhancedErrorResponse, "description": "Internal server error"},
    },
    tags=["reporting"],
)
async def report_missing_bench(
    request: Request,
    db: BenchDatabase = Depends(get_db),
    lat: float = Body(..., ge=-90.0, le=90.0, description="Bench latitude"),
    lng: float = Body(..., ge=-180.0, le=180.0, description="Bench longitude"),
    description: str | None = Body(None, description="Description of the bench"),
    location_method: str = Body(
        LocationMethod.GPS, description="How location was determined (gps, map_click)"
    ),
    user_location_lat: float | None = Body(None, description="User's GPS latitude"),
    user_location_lng: float | None = Body(None, description="User's GPS longitude"),
    accuracy_meters: float | None = Body(None, description="GPS accuracy in meters"),
    image_data: str | None = Body(None, description="Base64 encoded image data"),
) -> MissingBenchReportResponse:
    """Report a missing bench at a specific location."""
    try:
        import base64
        import io
        from datetime import datetime

        from PIL import Image

        Image.MAX_IMAGE_PIXELS = 300_000_000

        uploaded_image_filename = None
        if image_data:
            try:
                if "," in image_data:
                    _header, image_data = image_data.split(",", 1)

                image_bytes = base64.b64decode(image_data)

                if len(image_bytes) > 10 * 1024 * 1024:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="Image file too large. Maximum size is 10MB.",
                    )

                image = Image.open(io.BytesIO(image_bytes))

                if image.mode in ("RGBA", "P"):
                    image = image.convert("RGB")

                max_size = 2048
                if max(image.size) > max_size:
                    image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

                missing_reports_dir = os.path.join(IMAGES_DIR, "missing_reports")
                os.makedirs(missing_reports_dir, exist_ok=True)

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
                uploaded_image_filename = f"missing_{timestamp}_{lat}_{lng}.jpg"
                image_path = os.path.join(missing_reports_dir, uploaded_image_filename)

                image.save(image_path, "JPEG", quality=85, optimize=True)

            except Exception as e:
                print(f"Warning: Failed to process uploaded image: {e}")
                uploaded_image_filename = None

        user_agent = request.headers.get("user-agent", "")
        client_host = request.client.host if request.client else None

        with db.get_session() as session:
            from bench_finder.models.unified_models import MissingBenchReport

            report = MissingBenchReport(
                lat=lat,
                lng=lng,
                description=description,
                user_agent=user_agent,
                ip_address=client_host,
                user_location_lat=user_location_lat,
                user_location_lng=user_location_lng,
                location_method=location_method,
                uploaded_image_filename=uploaded_image_filename,
                accuracy_meters=accuracy_meters,
                extra_metadata={
                    "timestamp": datetime.now().isoformat(),
                    "has_image": uploaded_image_filename is not None,
                },
            )

            session.add(report)
            session.commit()
            session.refresh(report)
            report_id = report.id

            return MissingBenchReportResponse(
                success=True,
                report_id=report_id,
                message="Thank you for reporting this missing bench. It will be reviewed by our team.",
                location={"lat": lat, "lng": lng},
                location_method=location_method,
                has_image=uploaded_image_filename is not None,
                created_at=datetime.now().isoformat(),
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit missing bench report: {e!s}",
        ) from e
