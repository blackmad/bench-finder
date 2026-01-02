"""
Google Street View Static API integration for capturing street view images.
Supports multiple sources: Google Street View API, Google Street View via streetlevel, and Apple Look Around via streetlevel.
"""

import asyncio
import io
import json
import logging
import math
import os
from typing import Any

import aiohttp
import numpy as np
import requests
from aiohttp import ClientSession
from PIL import Image as PILImage

# Increase PIL max image pixels limit to handle large panoramas (e.g., 16384x8192)
# Default is ~89 million pixels, we set to 300 million to handle 4x larger images
PILImage.MAX_IMAGE_PIXELS = 300_000_000

from streetlevel import lookaround
from streetlevel import streetview as streetlevel_streetview

from bench_finder.config import (
    GOOGLE_MAPS_API_KEY,
    IMAGES_DIR,
    STREETVIEW_FOV,
    STREETVIEW_HEADINGS,
    STREETVIEW_SIZE,
    BACKOFF_INITIAL_WAIT,
    BACKOFF_DECREASE_STEP,
)
from bench_finder.models.enums import ImageSource
from bench_finder.models.streetview_models import (
    StreetViewBatchCaptureResult,
    StreetViewCleanupResult,
    StreetViewImageCapture,
    StreetViewLocation,
    StreetViewMetadata,
    StreetViewMetadataResponse,
)


logger = logging.getLogger(__name__)

STREETLEVEL_STREETVIEW_AVAILABLE = True
STREETLEVEL_LOOKAROUND_AVAILABLE = True


class StreetViewClient:
    """Client for capturing street view images from multiple sources."""

    def __init__(self) -> None:
        """Initialize the Street View client."""
        if not GOOGLE_MAPS_API_KEY:
            raise ValueError("GOOGLE_MAPS_API_KEY is required")

        self.api_key = GOOGLE_MAPS_API_KEY
        self.base_url = "https://maps.googleapis.com/maps/api/streetview"

        # Ensure images directory exists
        os.makedirs(IMAGES_DIR, exist_ok=True)

        # Metadata cache directory
        self.metadata_cache_dir = os.path.join(IMAGES_DIR, ".metadata_cache")
        os.makedirs(self.metadata_cache_dir, exist_ok=True)

        # Backoff state
        self.current_backoff = 0


    def _get_metadata_cache_path(self, lat: float, lng: float, source: str) -> str:
        """Get the path to the metadata cache file for a location and source."""
        # Create a safe filename from coordinates and source
        cache_key = f"{lat:.6f}_{lng:.6f}_{source}.json"
        return os.path.join(self.metadata_cache_dir, cache_key)

    def _load_cached_metadata(
        self, lat: float, lng: float, source: str
    ) -> dict[str, Any] | None:
        """Load cached metadata if it exists."""
        cache_path = self._get_metadata_cache_path(lat, lng, source)
        if os.path.exists(cache_path):
            try:
                with open(cache_path) as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load cached metadata from {cache_path}: {e}")
        return None

    def _save_metadata_cache(
        self, lat: float, lng: float, source: str, metadata: dict[str, Any]
    ) -> None:
        """Save metadata to cache."""
        cache_path = self._get_metadata_cache_path(lat, lng, source)
        try:
            with open(cache_path, "w") as f:
                json.dump(metadata, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save metadata cache to {cache_path}: {e}")

    def _generate_filename(
        self,
        bench_id: str,
        heading: int,
        source: ImageSource,
        is_direct_heading: bool = False,
    ) -> str:
        """Generate a filename that clearly indicates the source."""
        source_suffix = {
            ImageSource.STREETVIEW_API: "api",
            ImageSource.STREETVIEW_STREETLEVEL: "streetview",  # Google Street View via streetlevel
            ImageSource.APPLE_STREETLEVEL: "lookaround",  # Apple Look Around via streetlevel
        }.get(source, "unknown")
        if is_direct_heading:
            return f"bench_{bench_id}_direct_heading_{source_suffix}.jpg"
        return f"bench_{bench_id}_heading_{heading}_{source_suffix}.jpg"

    def _handle_backoff(self) -> None:
        """
        Handle backoff if active.
        Waits for the current backoff duration and then decreases it.
        """
        if self.current_backoff > 0:
            import time

            logger.warning(
                f"Backing off for {self.current_backoff} seconds due to previous errors..."
            )
            time.sleep(self.current_backoff)

            # Decrease backoff for next time
            self.current_backoff = max(
                0, self.current_backoff - BACKOFF_DECREASE_STEP
            )
            if self.current_backoff > 0:
                logger.info(
                    f"Backoff decreased to {self.current_backoff} seconds for next request"
                )
            else:
                logger.info("Backoff cleared")

    def _trigger_backoff(self) -> None:
        """
        Trigger backoff due to an error.
        Sets the backoff to the initial wait time.
        """
        import time

        self.current_backoff = BACKOFF_INITIAL_WAIT
        logger.warning(
            f"Error occurred, triggering backoff. Waiting {self.current_backoff} seconds..."
        )
        # Wait immediately to let the system cool down
        time.sleep(self.current_backoff)
        
        # Decrease for next time (since we just waited)
        self.current_backoff = max(0, self.current_backoff - BACKOFF_DECREASE_STEP)

    def capture_bench_images(
        self, lat: float, lng: float, bench_id: str
    ) -> StreetViewBatchCaptureResult:
        """
        Capture street view images from multiple headings for a bench location.
        Tries multiple sources in order: API, Google streetlevel, Apple streetlevel.

        Args:
            lat: Latitude of the bench
            lng: Longitude of the bench
            bench_id: Unique identifier for the bench

        Returns:
            StreetViewBatchCaptureResult with capture information
        """
        logger.debug(
            f"Capturing street view images for bench {bench_id} at {lat}, {lng}"
        )

        # Run async capture in event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            # If loop is already running, we need to use a different approach
            # Create a new task or use asyncio.run_coroutine_threadsafe
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run, self._capture_bench_images_async(lat, lng, bench_id)
                )
                capture_results = future.result()
        else:
            capture_results = loop.run_until_complete(
                self._capture_bench_images_async(lat, lng, bench_id)
            )

        # Create batch result from individual capture results
        batch_result = StreetViewBatchCaptureResult.from_capture_results(
            bench_id, lat, lng, capture_results
        )

        logger.debug(
            f"Bench {bench_id}: {batch_result.successful_images}/{batch_result.total_images} images total "
            f"({batch_result.downloaded_images} downloaded, {batch_result.cached_images} cached, {batch_result.failed_images} failed)"
        )

        return batch_result

    async def _capture_bench_images_async(
        self, lat: float, lng: float, bench_id: str
    ) -> list[StreetViewImageCapture | None]:
        """Async helper to capture images from multiple headings."""
        # Handle backoff before starting batch
        self._handle_backoff()

        capture_results = []
        panorama_location = (
            None  # Store panorama location for direct heading calculation
        )

           # Set timeout to prevent hanging (30 seconds total, 10 seconds connect)
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        # Try set trace configs for debugging on session creation
        trace_config = aiohttp.TraceConfig()
        # async def on_request_start(session, trace_config_ctx, params):
        #     print(f"Request started: {params.method} {params.url}")
        # async def on_request_end(session, trace_config_ctx, params):
        #     print(f"Request ended: {params.method} {params.url} -> {params.response.status}")
        # trace_config.on_request_start.append(on_request_start)
        # trace_config.on_request_end.append(on_request_end)

        async with ClientSession(trace_configs=[trace_config], timeout=timeout) as session:
            # First, capture all the regular heading images
            for heading in STREETVIEW_HEADINGS:
                try:
                    result = await self.capture_image_async(
                        lat, lng, bench_id, heading, session=session
                    )
                    capture_results.append(result)

                    if result and result.success:
                        # Store panorama location from first successful capture for direct heading
                        if (
                            panorama_location is None
                            and result.panorama_lat
                            and result.panorama_lng
                        ):
                            panorama_location = (
                                result.panorama_lat,
                                result.panorama_lng,
                                result.image_source,
                            )

                        if result.cached:
                            logger.debug(f"Using cached image at heading {heading}°")
                        else:
                            logger.debug(
                                f"Successfully downloaded image at heading {heading}° from {result.image_source}"
                            )
                    else:
                        error_msg = (
                            f" - error: {result.error}"
                            if result and result.error
                            else ""
                        )
                        logger.warning(
                            f"Failed to capture image at heading {heading}°{error_msg}"
                        )

                except Exception:
                    logger.exception(f"Error capturing image at heading {heading}°")
                    capture_results.append(None)

            # Now capture the direct heading image (from panorama center to bench location)
            if panorama_location:
                panorama_lat, panorama_lng, source_str = panorama_location
                try:
                    # Calculate heading from panorama location to bench location
                    direct_heading = self._calculate_bearing(
                        panorama_lat, panorama_lng, lat, lng
                    )
                    direct_heading_int = int(round(direct_heading))

                    logger.error(
                        f"Calculating direct heading from panorama ({panorama_lat}, {panorama_lng}) "
                        f"to bench ({lat}, {lng}): {direct_heading:.1f}°"
                    )

                    # Determine source from the string
                    source = ImageSource.STREETVIEW_STREETLEVEL  # Default
                    if "api" in source_str:
                        source = ImageSource.STREETVIEW_API
                    elif "lookaround" in source_str:
                        source = ImageSource.APPLE_STREETLEVEL

                    # Capture direct heading image
                    direct_result = await self.capture_image_async(
                        lat,
                        lng,
                        bench_id,
                        direct_heading_int + 270,
                        session=session,
                        is_direct_heading=True,
                        source=source,
                    )
                    capture_results.append(direct_result)

                    if direct_result and direct_result.success:
                        logger.debug(
                            f"Successfully captured direct heading image at {direct_heading:.1f}° from {source_str}"
                        )
                    else:
                        logger.warning(
                            f"Failed to capture direct heading image at {direct_heading:.1f}°"
                        )

                except Exception:
                    logger.exception("Error capturing direct heading image")
                    capture_results.append(None)
            else:
                logger.debug(
                    "No panorama location found, skipping direct heading capture"
                )

        return capture_results

    async def capture_image_async(
        self,
        lat: float,
        lng: float,
        bench_id: str,
        heading: int,
        session: ClientSession | None = None,
        is_direct_heading: bool = False,
        source: ImageSource | None = None,
    ) -> StreetViewImageCapture | None:
        """
        Capture a single street view image at specified heading.
        Tries multiple sources in order until one succeeds.

        Args:
            lat: Latitude
            lng: Longitude
            bench_id: Unique identifier for the bench
            heading: Compass heading (0-360 degrees)
            session: Optional aiohttp session for reuse

        Returns:
            StreetViewImageCapture with capture results
        """
        should_close = session is None
        if session is None:
               # Set timeout to prevent hanging (30 seconds total, 10 seconds connect)
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            # Try set trace configs for debugging on session creation
            trace_config = aiohttp.TraceConfig()
            async def on_request_start(session, trace_config_ctx, params):
                print(f"Request started: {params.method} {params.url}")
            async def on_request_end(session, trace_config_ctx, params):
                print(f"Request ended: {params.method} {params.url} -> {params.response.status}")
            trace_config.on_request_start.append(on_request_start)
            trace_config.on_request_end.append(on_request_end)
            session = ClientSession(trace_configs=[trace_config], timeout=timeout)

        try:
            # Always try both streetlevel sources (Google Street View and Apple Look Around)
            # API is only used as fallback if both streetlevel sources fail
            streetlevel_sources = [
                (
                    ImageSource.STREETVIEW_STREETLEVEL,
                    self._capture_from_streetlevel_google,
                ),
                (ImageSource.APPLE_STREETLEVEL, self._capture_from_streetlevel_apple),
            ]

            # Track results from streetlevel sources
            streetlevel_results = []
            at_least_one_streetlevel_success = False

            # Determine which sources to try
            # If source is specified (e.g., for direct heading), only try that source
            # Otherwise, try both streetlevel sources
            if source:
                # Use the specified source
                if source == ImageSource.STREETVIEW_STREETLEVEL:
                    sources_to_try = [
                        (
                            ImageSource.STREETVIEW_STREETLEVEL,
                            self._capture_from_streetlevel_google,
                        )
                    ]
                elif source == ImageSource.APPLE_STREETLEVEL:
                    sources_to_try = [
                        (
                            ImageSource.APPLE_STREETLEVEL,
                            self._capture_from_streetlevel_apple,
                        )
                    ]
                elif source == ImageSource.STREETVIEW_API:
                    sources_to_try = []  # Will be handled in API fallback section
                else:
                    sources_to_try = streetlevel_sources
            else:
                sources_to_try = streetlevel_sources

            # Try both streetlevel sources - always download both if available
            # Track errors from each source for better error reporting
            source_errors: dict[str, str] = {}

            for img_source, capture_func in sources_to_try:
                # Check if image already exists for this source
                filename = self._generate_filename(
                    bench_id, heading, img_source, is_direct_heading=is_direct_heading
                )
                filepath = os.path.join(IMAGES_DIR, filename)

                # For Apple Look Around, skip checking for per-heading files (we don't write them)
                # Just proceed to capture which will cache faces but not write per-heading files
                if img_source == ImageSource.APPLE_STREETLEVEL:
                    # Skip the file existence check - we'll handle caching in the capture function
                    pass
                elif os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                    logger.debug(f"Image already exists: {filename}, skipping download")
                    # Load metadata if available
                    metadata = self._load_cached_metadata(lat, lng, img_source.value)
                    panorama_lat = metadata.get("panorama_lat") if metadata else None
                    panorama_lng = metadata.get("panorama_lng") if metadata else None
                    panorama_metadata = (
                        metadata.get("panorama_metadata") if metadata else None
                    )

                    try:
                        with PILImage.open(filepath) as img:
                            width, height = img.size
                    except Exception:
                        width = int(STREETVIEW_SIZE.split("x")[0])
                        height = int(STREETVIEW_SIZE.split("x")[1])

                    result = StreetViewImageCapture(
                        bench_id=bench_id,
                        lat=lat,
                        lng=lng,
                        heading=heading,
                        filepath=filepath,
                        filename=filename,
                        success=True,
                        file_size=os.path.getsize(filepath),
                        cached=True,
                        error=None,
                        width=width,
                        height=height,
                        image_source=img_source.value,
                        panorama_lat=panorama_lat,
                        panorama_lng=panorama_lng,
                        panorama_metadata=panorama_metadata,
                    )
                    streetlevel_results.append(result)
                    at_least_one_streetlevel_success = True
                    continue

                # Try to capture from this source
                try:
                    result = await capture_func(
                        lat, lng, bench_id, heading, filename, filepath, session
                    )
                    if result and result.success:
                        # Save metadata to cache
                        if result.panorama_metadata or result.panorama_lat:
                            metadata = {
                                "panorama_lat": result.panorama_lat,
                                "panorama_lng": result.panorama_lng,
                                "panorama_metadata": result.panorama_metadata,
                            }
                            self._save_metadata_cache(
                                lat, lng, img_source.value, metadata
                            )
                        streetlevel_results.append(result)
                        at_least_one_streetlevel_success = True
                    elif result and result.error:
                        # Capture returned a failed result with error info
                        source_errors[img_source.value] = result.error
                        streetlevel_results.append(result)
                    else:
                        # Capture returned None - no panorama found
                        source_errors[img_source.value] = "no panorama found"
                except Exception as e:
                    error_msg = str(e)
                    source_errors[img_source.value] = error_msg
                    logger.debug(
                        f"Failed to capture from {img_source.value} for heading {heading}: {e}"
                    )
                    # Continue to try the other source even if this one fails

            # If at least one streetlevel source succeeded, return the first successful result
            # (or the first one if multiple succeeded - caller can handle multiple results)
            if at_least_one_streetlevel_success:
                # Return the first successful result (prefer Google Street View if both succeed)
                for result in streetlevel_results:
                    if result and result.success:
                        return result

            # If both streetlevel sources failed, try API as fallback
            # (or if source was explicitly set to API)
            api_error = None
            if not source or source == ImageSource.STREETVIEW_API:
                if source != ImageSource.STREETVIEW_API:
                    logger.debug(
                        f"Both streetlevel sources failed for bench {bench_id} at heading {heading}, trying API fallback"
                    )
                api_source = ImageSource.STREETVIEW_API
                api_capture_func = self._capture_from_api
                api_filename = self._generate_filename(
                    bench_id, heading, api_source, is_direct_heading=is_direct_heading
                )
                api_filepath = os.path.join(IMAGES_DIR, api_filename)

                # Check if API image already exists
                if os.path.exists(api_filepath) and os.path.getsize(api_filepath) > 0:
                    logger.debug(
                        f"API image already exists: {api_filename}, skipping download"
                    )
                    metadata = self._load_cached_metadata(lat, lng, api_source.value)
                    panorama_lat = metadata.get("panorama_lat") if metadata else None
                    panorama_lng = metadata.get("panorama_lng") if metadata else None
                    panorama_metadata = (
                        metadata.get("panorama_metadata") if metadata else None
                    )

                    try:
                        with PILImage.open(api_filepath) as img:
                            width, height = img.size
                    except Exception:
                        width = int(STREETVIEW_SIZE.split("x")[0])
                        height = int(STREETVIEW_SIZE.split("x")[1])

                    return StreetViewImageCapture(
                        bench_id=bench_id,
                        lat=lat,
                        lng=lng,
                        heading=heading,
                        filepath=api_filepath,
                        filename=api_filename,
                        success=True,
                        file_size=os.path.getsize(api_filepath),
                        cached=True,
                        error=None,
                        width=width,
                        height=height,
                        image_source=api_source.value,
                        panorama_lat=panorama_lat,
                        panorama_lng=panorama_lng,
                        panorama_metadata=panorama_metadata,
                    )

                # Try API capture
                try:
                    result = await api_capture_func(
                        lat, lng, bench_id, heading, api_filename, api_filepath, session
                    )
                    if result and result.success:
                        # Save metadata to cache
                        if result.panorama_metadata or result.panorama_lat:
                            metadata = {
                                "panorama_lat": result.panorama_lat,
                                "panorama_lng": result.panorama_lng,
                                "panorama_metadata": result.panorama_metadata,
                            }
                            self._save_metadata_cache(
                                lat, lng, api_source.value, metadata
                            )
                        return result
                    elif result and result.error:
                        api_error = result.error
                except Exception as e:
                    api_error = str(e)
                    logger.debug(
                        f"Failed to capture from API for heading {heading}: {e}"
                    )

            # All sources failed - collect error information from source_errors dict
            error_details = [
                f"{source}: {error}" for source, error in source_errors.items()
            ]
            if api_error:
                error_details.append(f"API: {api_error}")

            error_msg = (
                f" - errors: {', '.join(error_details)}" if error_details else ""
            )
            logger.warning(
                f"All sources failed for bench {bench_id} at heading {heading}{error_msg}"
            )
            return None

        except Exception as e:
            # Trigger backoff on unexpected errors
            logger.error(f"Unexpected error in capture_image_async: {e}")
            self._trigger_backoff()
            return None

        finally:
            if should_close:
                await session.close()

    async def _capture_from_api(
        self,
        lat: float,
        lng: float,
        bench_id: str,
        heading: int,
        filename: str,
        filepath: str,
        session: ClientSession,
    ) -> StreetViewImageCapture | None:
        """Capture image from Google Street View Static API."""
        try:
            params = {
                "location": f"{lat},{lng}",
                "size": STREETVIEW_SIZE,
                "heading": heading,
                "fov": STREETVIEW_FOV,
                "source": "outdoor",
                "key": self.api_key,
            }

            logger.debug(
                f"Requesting street view image from API: lat={lat}, lng={lng}, heading={heading}"
            )

            # Use requests for API (synchronous)
            response = requests.get(self.base_url, params=params, timeout=30)

            if response.status_code != 200:
                logger.error(f"Street View API returned status {response.status_code}")
                return None

            content_type = response.headers.get("content-type", "")
            if not content_type.startswith("image/"):
                logger.error(f"Expected image, got content-type: {content_type}")
                return None

            # Save the image
            with open(filepath, "wb") as f:
                f.write(response.content)

            if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
                logger.error(f"Failed to save image to {filepath}")
                return None

            # Verify it's a valid image
            try:
                with PILImage.open(filepath) as img:
                    width, height = img.size
                    logger.debug(f"Saved image {filename}: {width}x{height}")
            except Exception as e:
                logger.warning(f"Could not verify image {filename}: {e}")
                width = int(STREETVIEW_SIZE.split("x")[0])
                height = int(STREETVIEW_SIZE.split("x")[1])

            return StreetViewImageCapture(
                width=width,
                height=height,
                filename=filename,
                bench_id=bench_id,
                lat=lat,
                lng=lng,
                heading=heading,
                filepath=filepath,
                success=True,
                file_size=os.path.getsize(filepath),
                cached=False,
                error=None,
                image_source=ImageSource.STREETVIEW_API.value,
                panorama_lat=lat,  # API uses requested location
                panorama_lng=lng,
                panorama_metadata=None,
            )

            return None

        except Exception as e:
            logger.debug(f"Error capturing from API: {e}")
            # Trigger backoff on API errors
            self._trigger_backoff()
            return None

    def _get_pano_filename(self, pano_id: str | None, lat: float, lng: float) -> str:
        """
        Generate a consistent filename for a panorama based on its ID or location.

        Args:
            pano_id: Panorama ID if available
            lat: Latitude of panorama
            lng: Longitude of panorama

        Returns:
            Filename for the panorama
        """
        if pano_id:
            # Use panorama ID for consistent naming
            safe_id = pano_id.replace("/", "_").replace("\\", "_")
            return f"pano_{safe_id}.jpg"
        else:
            # Fall back to location-based naming
            return f"pano_{lat:.6f}_{lng:.6f}.jpg"

    async def _get_or_download_panorama(
        self,
        lat: float,
        lng: float,
        bench_id: str | None = None,
        session: ClientSession | None = None,
    ) -> tuple[Any, PILImage.Image | None, str | None, float, float, str | None] | None:
        """
        Get or download a Google Street View panorama, reusing cached version if available.

        Args:
            lat: Latitude to search for panorama
            lng: Longitude to search for panorama
            bench_id: Optional bench ID to use for naming (uses bench naming scheme if provided)
            session: aiohttp session for requests

        Returns:
            Tuple of (pano object, equirectangular PIL Image, pano_id, panorama_lat, panorama_lng, error)
            Returns None if panorama not found (with error in last element if tuple returned)
            The error element is None on success, or an error message string on failure
        """
        try:
            # Find panorama
            pano = await streetlevel_streetview.find_panorama_async(
                lat, lng, radius=25, session=session
            )

            if not pano:
                error_msg = f"no panorama found within 25m of ({lat:.6f}, {lng:.6f})"
                logger.debug(f"Google Street View streetlevel: {error_msg}")
                return (None, None, None, lat, lng, error_msg)

            # Get panorama location and ID
            panorama_lat = pano.lat if hasattr(pano, "lat") else lat
            panorama_lng = pano.lon if hasattr(pano, "lon") else lng
            pano_id = pano.id if hasattr(pano, "id") else None

            # Generate filename using bench naming scheme if bench_id provided, otherwise use pano ID
            if bench_id:
                pano_filename = f"bench_{bench_id}_streetview_pano.jpg"
            else:
                pano_filename = self._get_pano_filename(
                    pano_id, panorama_lat, panorama_lng
                )
            pano_filepath = os.path.join(IMAGES_DIR, pano_filename)

            if os.path.exists(pano_filepath) and os.path.getsize(pano_filepath) > 0:
                logger.debug(f"Reusing cached panorama: {pano_filename}")
                try:
                    equirectangular = PILImage.open(pano_filepath)
                    return (pano, equirectangular, pano_id, panorama_lat, panorama_lng, None)
                except Exception as e:
                    logger.warning(
                        f"Failed to load cached panorama {pano_filename}: {e}"
                    )
                    # Continue to download if loading fails

            # Download panorama if not cached
            logger.debug(f"Downloading panorama for {panorama_lat}, {panorama_lng}")
            equirectangular = await streetlevel_streetview.get_panorama_async(
                pano, zoom=5, session=session
            )

            if not equirectangular:
                error_msg = f"failed to download panorama tiles for pano_id={pano_id}"
                logger.debug(f"Google Street View streetlevel: {error_msg}")
                return (pano, None, pano_id, panorama_lat, panorama_lng, error_msg)

            # Save the panorama (only once)
            try:
                equirectangular.save(pano_filepath, "JPEG")
                logger.debug(f"Saved full panorama to {pano_filename}")
            except Exception as e:
                logger.warning(f"Failed to save full panorama {pano_filename}: {e}")

            return (pano, equirectangular, pano_id, panorama_lat, panorama_lng, None)

        except Exception as e:
            error_msg = f"exception: {e}"
            logger.debug(f"Error getting panorama: {e}")
            return (None, None, None, lat, lng, error_msg)

    def _calculate_bearing(
        self, lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """
        Calculate the bearing (heading) from point 1 to point 2 in degrees.

        Args:
            lat1: Latitude of starting point
            lon1: Longitude of starting point
            lat2: Latitude of destination point
            lon2: Longitude of destination point

        Returns:
            Bearing in degrees (0-360, where 0 is North)
        """
        # Convert to radians
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lon = math.radians(lon2 - lon1)

        # Calculate bearing
        y = math.sin(delta_lon) * math.cos(lat2_rad)
        x = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(
            lat2_rad
        ) * math.cos(delta_lon)

        bearing = math.atan2(y, x)
        bearing_degrees = math.degrees(bearing)

        # Normalize to 0-360
        bearing_degrees = (bearing_degrees + 360) % 360

        return bearing_degrees

    def _extract_perspective_view(
        self,
        equirectangular: PILImage.Image,
        heading: int,
        fov: int,
        size: tuple[int, int],
    ) -> PILImage.Image:
        """
        Extract a perspective view from an equirectangular panorama using equi2pers.

        Args:
            equirectangular: The full equirectangular panorama image
            heading: Compass heading in degrees (0-360, where 0 is North)
            fov: Field of view in degrees
            size: Output image size (width, height)

        Returns:
            Perspective view image at the specified heading and FOV
        """
        try:
            from equilib import equi2pers
        except ImportError:
            # Fallback: try pyequilib
            try:
                from pyequilib import equi2pers
            except ImportError:
                logger.warning(
                    "equilib/pyequilib not available, falling back to manual projection"
                )
                return self._extract_perspective_view_manual(
                    equirectangular, heading, fov, size
                )

        width, height = size

        # Convert PIL Image to numpy array
        equi_array = np.asarray(equirectangular)

        # Ensure the image is in channel-first format (C, H, W) for equi2pers
        if len(equi_array.shape) == 3 and (
            equi_array.shape[2] == 3 or equi_array.shape[2] == 4
        ):  # H, W, C format
            equi_array = np.transpose(equi_array, (2, 0, 1))

        # Remove alpha channel if present (keep only RGB)
        if equi_array.shape[0] == 4:
            equi_array = equi_array[:3, :, :]

        # Convert heading to yaw angle
        # In equi2pers: yaw angles are in degrees (0 = front/North, 90 = right/East, etc.)
        # In GSV: 0 = North, 90 = East, 180 = South, 270 = West
        # Based on notebook usage with yaw_angles=[0, 90, 180, 270], the coordinate systems match
        yaw_deg = float(heading)

        # Extract perspective view
        rots_dict = {
            "roll": 0.0,  # No roll
            "pitch": 0.0,  # Look straight ahead
            "yaw": np.deg2rad(yaw_deg),
        }

        pers_img = equi2pers(
            equi=equi_array,
            rots=rots_dict,
            height=height,
            width=width,
            mode="bilinear",
            clip_output=False,
            fov_x=fov,
        )

        # Convert back to H, W, C format for PIL
        if len(pers_img.shape) == 3 and pers_img.shape[0] == 3:
            pers_img = np.transpose(pers_img, (1, 2, 0))

        # Ensure values are in valid range [0, 255]
        pers_img = np.clip(pers_img, 0, 255).astype(np.uint8)

        return PILImage.fromarray(pers_img)

    def _extract_perspective_view_manual(
        self,
        equirectangular: PILImage.Image,
        heading: int,
        fov: int,
        size: tuple[int, int],
    ) -> PILImage.Image:
        """
        Fallback manual extraction method (original implementation).
        Only used if equilib library is not available.
        """
        width, height = size
        pano_width, pano_height = equirectangular.size

        # Convert inputs to radians
        fov_rad = np.radians(fov)
        heading_rad = np.radians(heading)

        # Camera parameters
        f = 0.5 * width / np.tan(0.5 * fov_rad)

        # Create meshgrid of output pixel coordinates
        x, y = np.meshgrid(np.arange(width), np.arange(height))

        # Center coordinates
        x_c = x - width / 2
        y_c = y - height / 2
        z_c = np.full_like(x_c, f)

        # Normalize vectors
        norm = np.sqrt(x_c**2 + y_c**2 + z_c**2)
        x_n = x_c / norm
        y_n = y_c / norm
        z_n = z_c / norm

        # Convert to spherical coordinates
        phi = np.arctan2(x_n, z_n)
        theta = np.arcsin(y_n)

        # Adjust phi by heading
        phi_world = phi + heading_rad

        # Normalize phi to [-pi, pi]
        phi_world = (phi_world + np.pi) % (2 * np.pi) - np.pi

        # Map to equirectangular pixel coordinates
        u = (phi_world + np.pi) / (2 * np.pi)
        v = (theta + np.pi / 2) / np.pi

        # Map to source image coordinates
        src_x = u * pano_width
        src_y = v * pano_height

        # Wrap x coordinates
        src_x = np.mod(src_x, pano_width)

        # Clip y coordinates
        src_y = np.clip(src_y, 0, pano_height - 1)

        # Sample pixels
        src_x_int = src_x.astype(int)
        src_y_int = src_y.astype(int)

        # Convert PIL image to numpy array
        pano_array = np.array(equirectangular)

        # Sample
        output_array = pano_array[src_y_int, src_x_int]

        return PILImage.fromarray(output_array)

    async def _capture_from_streetlevel_google(
        self,
        lat: float,
        lng: float,
        bench_id: str,
        heading: int,
        filename: str,
        filepath: str,
        session: ClientSession,
    ) -> StreetViewImageCapture | None:
        """Capture image from Google Street View via streetlevel library."""
        if not STREETLEVEL_STREETVIEW_AVAILABLE:
            return StreetViewImageCapture(
                bench_id=bench_id,
                lat=lat,
                lng=lng,
                heading=heading,
                filepath=filepath,
                filename=filename,
                success=False,
                file_size=0,
                cached=False,
                error="streetlevel library not available",
                image_source=ImageSource.STREETVIEW_STREETLEVEL.value,
                width=0,
                height=0,
            )

        try:
            logger.debug(
                f"Requesting street view image from streetlevel (Google): lat={lat}, lng={lng}, heading={heading}"
            )

            # Get or download panorama (reuses cached version if available)
            # Use bench naming scheme for the panorama file
            result = await self._get_or_download_panorama(
                lat, lng, bench_id=bench_id, session=session
            )

            # Handle errors from panorama download
            if result is None:
                return StreetViewImageCapture(
                    bench_id=bench_id,
                    lat=lat,
                    lng=lng,
                    heading=heading,
                    filepath=filepath,
                    filename=filename,
                    success=False,
                    file_size=0,
                    cached=False,
                    error="panorama download returned None",
                    image_source=ImageSource.STREETVIEW_STREETLEVEL.value,
                    width=0,
                    height=0,
                )

            pano, equirectangular, pano_id, panorama_lat, panorama_lng, pano_error = (
                result
            )

            # Check for error from panorama download
            if pano_error or equirectangular is None:
                return StreetViewImageCapture(
                    bench_id=bench_id,
                    lat=lat,
                    lng=lng,
                    heading=heading,
                    filepath=filepath,
                    filename=filename,
                    success=False,
                    file_size=0,
                    cached=False,
                    error=pano_error or "failed to get panorama image",
                    image_source=ImageSource.STREETVIEW_STREETLEVEL.value,
                    panorama_lat=panorama_lat,
                    panorama_lng=panorama_lng,
                    width=0,
                    height=0,
                )

            # Extract perspective view at the specified heading and FOV
            # Use higher resolution to match the high-res panorama (zoom=5 is ~2048x1024)
            # Extract at 2048x2048 to preserve quality from the high-res panorama
            pano_width, pano_height = equirectangular.size
            # Use panorama height as the target size to maintain quality
            # For square output, use the larger dimension
            target_dimension = max(pano_width, pano_height)
            # But cap at reasonable size for performance (2048x2048 max)
            target_dimension = min(target_dimension, 2048)
            target_size = (target_dimension, target_dimension)

            perspective_view = self._extract_perspective_view(
                equirectangular, heading, STREETVIEW_FOV, target_size
            )

            # Save the image
            perspective_view.save(filepath, "JPEG")

            if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
                logger.error(f"Failed to save image to {filepath}")
                return None

            width, height = perspective_view.size

            # Extract panorama metadata
            panorama_metadata = {
                "pano_id": pano_id,
                "date": str(pano.date) if hasattr(pano, "date") else None,
            }

            logger.debug(
                f"Saved image {filename} from streetlevel (Google): {width}x{height}, panorama at {panorama_lat}, {panorama_lng}, heading={heading}°"
            )

            return StreetViewImageCapture(
                width=width,
                height=height,
                filename=filename,
                bench_id=bench_id,
                lat=lat,
                lng=lng,
                heading=heading,
                filepath=filepath,
                success=True,
                file_size=os.path.getsize(filepath),
                cached=False,
                error=None,
                image_source=ImageSource.STREETVIEW_STREETLEVEL.value,
                panorama_lat=panorama_lat,
                panorama_lng=panorama_lng,
                panorama_metadata=panorama_metadata,
            )

        except Exception as e:
            logger.debug(f"Error capturing from streetlevel (Google): {e}")
            return StreetViewImageCapture(
                bench_id=bench_id,
                lat=lat,
                lng=lng,
                heading=heading,
                filepath=filepath,
                filename=filename,
                success=False,
                file_size=0,
                cached=False,
                error=f"exception: {e}",
                image_source=ImageSource.STREETVIEW_STREETLEVEL.value,
                width=0,
                height=0,
            )

    async def _capture_from_streetlevel_apple(
        self,
        lat: float,
        lng: float,
        bench_id: str,
        heading: int,
        filename: str,
        filepath: str,
        session: ClientSession,
    ) -> StreetViewImageCapture | None:
        """Capture image from Apple Look Around via streetlevel library."""
        if not STREETLEVEL_LOOKAROUND_AVAILABLE:
            return StreetViewImageCapture(
                bench_id=bench_id,
                lat=lat,
                lng=lng,
                heading=heading,
                filepath=filepath,
                filename=filename,
                success=False,
                file_size=0,
                cached=False,
                error="streetlevel library (lookaround) not available",
                image_source=ImageSource.APPLE_STREETLEVEL.value,
                width=0,
                height=0,
            )

        try:
            logger.debug(
                f"Requesting street view image from streetlevel (Apple): lat={lat}, lng={lng}, heading={heading}"
            )

            # Get coverage tile
            tile = await lookaround.get_coverage_tile_by_latlon_async(
                lat, lng, session=session
            )

            if not tile or not tile.panos or len(tile.panos) == 0:
                logger.debug("No Apple Look Around panoramas found")
                return StreetViewImageCapture(
                    bench_id=bench_id,
                    lat=lat,
                    lng=lng,
                    heading=heading,
                    filepath=filepath,
                    filename=filename,
                    success=False,
                    file_size=0,
                    cached=False,
                    error=f"no Look Around coverage at ({lat:.6f}, {lng:.6f})",
                    image_source=ImageSource.APPLE_STREETLEVEL.value,
                    width=0,
                    height=0,
                )

            # Find the closest panorama
            import math

            def haversine_distance(lat1, lon1, lat2, lon2):
                """Calculate the great circle distance between two points on Earth in meters."""
                R = 6371000  # Earth radius in meters
                phi1 = math.radians(lat1)
                phi2 = math.radians(lat2)
                delta_phi = math.radians(lat2 - lat1)
                delta_lambda = math.radians(lon2 - lon1)

                a = (
                    math.sin(delta_phi / 2) ** 2
                    + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
                )
                c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

                return R * c

            closest_pano = None
            min_distance = float("inf")
            for candidate_pano in tile.panos:
                distance = haversine_distance(
                    lat, lng, candidate_pano.lat, candidate_pano.lon
                )
                if distance < min_distance:
                    min_distance = distance
                    closest_pano = candidate_pano

            if closest_pano is None:
                logger.debug("No closest panorama found")
                return StreetViewImageCapture(
                    bench_id=bench_id,
                    lat=lat,
                    lng=lng,
                    heading=heading,
                    filepath=filepath,
                    filename=filename,
                    success=False,
                    file_size=0,
                    cached=False,
                    error="no closest panorama found in coverage tile",
                    image_source=ImageSource.APPLE_STREETLEVEL.value,
                    width=0,
                    height=0,
                )

            pano = closest_pano
            panorama_lat = pano.lat
            panorama_lng = pano.lon

            # Generate filenames for individual faces
            # Face names: BACK=0, LEFT=1, FRONT=2, RIGHT=3, TOP=4, BOTTOM=5
            face_names = ["back", "left", "front", "right", "top", "bottom"]
            # Use bench_id for base name to share faces across headings
            base_name = f"bench_{bench_id}_lookaround"
            face_filenames = [f"{base_name}_face_{face_names[i]}.jpg" for i in range(6)]
            face_filepaths = [
                os.path.join(IMAGES_DIR, face_filename)
                for face_filename in face_filenames
            ]

            # Check if all faces are already cached (we don't check for stitched image anymore)
            all_faces_cached = all(
                os.path.exists(fp) and os.path.getsize(fp) > 0 for fp in face_filepaths
            )

            if all_faces_cached:
                logger.debug(
                    f"All Apple Look Around faces already cached for bench {bench_id}"
                )
                # Load metadata if available
                metadata = self._load_cached_metadata(
                    lat, lng, ImageSource.APPLE_STREETLEVEL.value
                )
                panorama_metadata = (
                    metadata.get("panorama_metadata")
                    if metadata
                    else {
                        "pano_id": pano.id if hasattr(pano, "id") else None,
                        "date": str(pano.date) if hasattr(pano, "date") else None,
                    }
                )
                # Add face filenames to metadata
                if panorama_metadata:
                    panorama_metadata["face_filenames"] = face_filenames

                # Get dimensions from front face
                try:
                    with PILImage.open(face_filepaths[2]) as img:  # FRONT face
                        width, height = img.size
                except Exception:
                    width = int(STREETVIEW_SIZE.split("x")[0])
                    height = int(STREETVIEW_SIZE.split("x")[1])

                # Return success but with None filepath since we're not writing per-heading files
                return StreetViewImageCapture(
                    width=width,
                    height=height,
                    filename=filename,
                    bench_id=bench_id,
                    lat=lat,
                    lng=lng,
                    heading=heading,
                    filepath=None,  # Not writing per-heading file to disk
                    success=True,
                    file_size=0,  # No file written
                    cached=True,
                    error=None,
                    image_source=ImageSource.APPLE_STREETLEVEL.value,
                    panorama_lat=panorama_lat,
                    panorama_lng=panorama_lng,
                    panorama_metadata=panorama_metadata,
                )

            # Get panorama faces and create equirectangular projection
            auth = lookaround.Authenticator()
            zoom = 2

            # Try to get equirectangular projection
            try:
                # Try using pillow-heif if available
                try:
                    from pillow_heif import register_heif_opener

                    register_heif_opener()
                except ImportError:
                    pass

                # Get all 6 faces
                faces = []
                faces_cached = []
                for face_idx in range(6):
                    # Check if this face is already cached
                    if (
                        os.path.exists(face_filepaths[face_idx])
                        and os.path.getsize(face_filepaths[face_idx]) > 0
                    ):
                        try:
                            img = PILImage.open(face_filepaths[face_idx])
                            faces.append(img)
                            faces_cached.append(True)
                            logger.debug(
                                f"Using cached face {face_idx} ({face_names[face_idx]})"
                            )
                        except Exception as e:
                            logger.debug(f"Could not load cached face {face_idx}: {e}")
                            faces.append(None)
                            faces_cached.append(False)
                    else:
                        # Fetch face from API
                        try:
                            face_heic = await asyncio.to_thread(
                                lookaround.get_panorama_face,
                                pano,
                                face_idx,
                                zoom,
                                auth,
                                None,
                            )
                            img = PILImage.open(io.BytesIO(face_heic))
                            faces.append(img)
                            faces_cached.append(False)

                            # Save individual face
                            img.save(face_filepaths[face_idx], "JPEG")
                            logger.debug(
                                f"Saved face {face_idx} ({face_names[face_idx]}) to {face_filenames[face_idx]}"
                            )
                        except Exception as e:
                            logger.debug(f"Could not fetch face {face_idx}: {e}")
                            faces.append(None)
                            faces_cached.append(False)

                # Save all successfully fetched faces (even if some failed)
                for face_idx, face in enumerate(faces):
                    if face is not None and not faces_cached[face_idx]:
                        try:
                            face.save(face_filepaths[face_idx], "JPEG")
                        except Exception as e:
                            logger.warning(f"Failed to save face {face_idx}: {e}")

                # For now, just cache the faces without writing per-heading files
                # Don't write the per-heading file to disk - just cache the faces
                if not any(faces):
                    logger.debug("Could not get any faces from Apple Look Around")
                    return StreetViewImageCapture(
                        bench_id=bench_id,
                        lat=lat,
                        lng=lng,
                        heading=heading,
                        filepath=filepath,
                        filename=filename,
                        success=False,
                        file_size=0,
                        cached=False,
                        error="could not fetch any faces from Look Around",
                        image_source=ImageSource.APPLE_STREETLEVEL.value,
                        panorama_lat=panorama_lat,
                        panorama_lng=panorama_lng,
                        width=0,
                        height=0,
                    )

                # Faces are cached, but we don't write the per-heading file
                logger.debug(
                    f"Cached {len([f for f in faces if f is not None])} faces for Apple Look Around "
                    f"(per-heading file not written: {filename})"
                )
            except Exception as e:
                logger.debug(f"Error fetching Apple Look Around faces: {e}")
                return StreetViewImageCapture(
                    bench_id=bench_id,
                    lat=lat,
                    lng=lng,
                    heading=heading,
                    filepath=filepath,
                    filename=filename,
                    success=False,
                    file_size=0,
                    cached=False,
                    error=f"error fetching faces: {e}",
                    image_source=ImageSource.APPLE_STREETLEVEL.value,
                    panorama_lat=panorama_lat,
                    panorama_lng=panorama_lng,
                    width=0,
                    height=0,
                )

            # Get image dimensions from front face if available, otherwise use default
            if faces[2]:  # FRONT face
                width, height = faces[2].size
            else:
                # Fallback to first available face
                first_face = next((f for f in faces if f is not None), None)
                if first_face:
                    width, height = first_face.size
                else:
                    width = int(STREETVIEW_SIZE.split("x")[0])
                    height = int(STREETVIEW_SIZE.split("x")[1])

            # Extract panorama metadata
            panorama_metadata = {
                "pano_id": pano.id if hasattr(pano, "id") else None,
                "date": str(pano.date) if hasattr(pano, "date") else None,
                "face_filenames": face_filenames,  # Track individual face files
            }

            logger.debug(
                f"Cached Apple Look Around faces for bench {bench_id}: panorama at {panorama_lat}, {panorama_lng}, "
                f"with {len([f for f in faces if f is not None])} faces (per-heading file skipped)"
            )

            # Return success but with None filepath since we're not writing the per-heading file
            return StreetViewImageCapture(
                width=width,
                height=height,
                filename=filename,
                bench_id=bench_id,
                lat=lat,
                lng=lng,
                heading=heading,
                filepath=None,  # Not writing per-heading file to disk
                success=True,
                file_size=0,  # No file written
                cached=all_faces_cached,
                error=None,
                image_source=ImageSource.APPLE_STREETLEVEL.value,
                panorama_lat=panorama_lat,
                panorama_lng=panorama_lng,
                panorama_metadata=panorama_metadata,
            )

        except Exception as e:
            logger.debug(f"Error capturing from streetlevel (Apple): {e}")
            return StreetViewImageCapture(
                bench_id=bench_id,
                lat=lat,
                lng=lng,
                heading=heading,
                filepath=filepath,
                filename=filename,
                success=False,
                file_size=0,
                cached=False,
                error=f"exception: {e}",
                image_source=ImageSource.APPLE_STREETLEVEL.value,
                width=0,
                height=0,
            )

    def capture_image(
        self, lat: float, lng: float, bench_id: str, heading: int
    ) -> StreetViewImageCapture | None:
        """
        Synchronous wrapper for capture_image_async.

        Args:
            lat: Latitude
            lng: Longitude
            bench_id: Unique identifier for the bench
            heading: Compass heading (0-360 degrees)

        Returns:
            StreetViewImageCapture with capture results
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    self.capture_image_async(lat, lng, bench_id, heading),
                )
                return future.result()
        else:
            return loop.run_until_complete(
                self.capture_image_async(lat, lng, bench_id, heading)
            )

    def get_street_view_metadata(
        self, lat: float, lng: float
    ) -> StreetViewMetadataResponse:
        """
        Get metadata about street view availability at a location.

        Args:
            lat: Latitude
            lng: Longitude

        Returns:
            StreetViewMetadataResponse with metadata information
        """
        requested_location = StreetViewLocation(lat=lat, lng=lng)

        try:
            metadata_url = "https://maps.googleapis.com/maps/api/streetview/metadata"
            params = {
                "location": f"{lat},{lng}",
                "source": "outdoor",
                "key": self.api_key,
            }

            response = requests.get(metadata_url, params=params, timeout=10)
            response.raise_for_status()

            metadata_raw = response.json()
            status = metadata_raw.get("status")

            if status == "OK":
                logger.debug(f"Street view available at {lat}, {lng}")

                # Parse location information
                location_info = metadata_raw.get("location", {})
                location = None
                if location_info:
                    location = StreetViewLocation(
                        lat=location_info.get("lat"), lng=location_info.get("lng")
                    )

                metadata = StreetViewMetadata(
                    status=status,
                    location=location,
                    pano_id=metadata_raw.get("pano_id"),
                    date=metadata_raw.get("date"),
                    copyright=metadata_raw.get("copyright"),
                )

                return StreetViewMetadataResponse(
                    requested_location=requested_location, metadata=metadata
                )
            else:
                logger.debug(f"Street view not available at {lat}, {lng}: {status}")

                # Create metadata with error status
                metadata = StreetViewMetadata(
                    status=status,
                    location=None,
                    pano_id=None,
                    date=None,
                    copyright=None,
                )

                return StreetViewMetadataResponse(
                    requested_location=requested_location, metadata=metadata
                )

        except Exception:
            logger.exception("Error getting street view metadata")

            # Return error response
            error_metadata = StreetViewMetadata(
                status="ERROR", location=None, pano_id=None, date=None, copyright=None
            )

            return StreetViewMetadataResponse(
                requested_location=requested_location, metadata=error_metadata
            )

    def cleanup_images(self, filepaths: list[str]) -> StreetViewCleanupResult:
        """
        Clean up image files.

        Args:
            filepaths: List of file paths to delete

        Returns:
            StreetViewCleanupResult with cleanup statistics
        """
        removed_count = 0
        failed_count = 0
        errors = []

        for filepath in filepaths:
            try:
                if filepath and os.path.exists(filepath):
                    os.remove(filepath)
                    removed_count += 1
                    logger.debug(f"Removed image file: {filepath}")
                elif filepath:
                    # File doesn't exist, but this isn't really an error
                    logger.debug(f"File already removed or doesn't exist: {filepath}")
            except Exception as e:
                failed_count += 1
                error_msg = f"Could not remove image file {filepath}: {e}"
                errors.append(error_msg)
                logger.warning(error_msg)

        return StreetViewCleanupResult(
            filepaths=filepaths,
            removed_count=removed_count,
            failed_count=failed_count,
            errors=errors,
        )
