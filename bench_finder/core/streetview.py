"""
Google Street View Static API integration for capturing street view images.
Supports multiple sources: Google Street View API, Google Street View via streetlevel, and Apple Look Around via streetlevel.
"""

import asyncio
import io
import json
import logging
import os
from typing import Any

import requests
from aiohttp import ClientSession
from PIL import Image as PILImage

from bench_finder.config import (
    GOOGLE_MAPS_API_KEY,
    IMAGES_DIR,
    STREETVIEW_FOV,
    STREETVIEW_HEADINGS,
    STREETVIEW_SIZE,
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

# Try to import streetlevel modules
try:
    from streetlevel import streetview as streetlevel_streetview

    STREETLEVEL_STREETVIEW_AVAILABLE = True
except ImportError:
    STREETLEVEL_STREETVIEW_AVAILABLE = False
    logger.warning(
        "streetlevel.streetview not available - Google Street View via streetlevel will be disabled"
    )

try:
    from streetlevel import lookaround

    STREETLEVEL_LOOKAROUND_AVAILABLE = True
except ImportError:
    STREETLEVEL_LOOKAROUND_AVAILABLE = False
    logger.warning(
        "streetlevel.lookaround not available - Apple Look Around will be disabled"
    )


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
        self, bench_id: str, heading: int, source: ImageSource
    ) -> str:
        """Generate a filename that clearly indicates the source."""
        source_suffix = {
            ImageSource.STREETVIEW_API: "api",
            ImageSource.STREETVIEW_STREETLEVEL: "streetlevel",
            ImageSource.APPLE_STREETLEVEL: "apple",
        }.get(source, "unknown")
        return f"bench_{bench_id}_heading_{heading}_{source_suffix}.jpg"

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
        capture_results = []

        async with ClientSession() as session:
            for heading in STREETVIEW_HEADINGS:
                try:
                    result = await self.capture_image_async(
                        lat, lng, bench_id, heading, session=session
                    )
                    capture_results.append(result)

                    if result and result.success:
                        if result.cached:
                            logger.debug(f"Using cached image at heading {heading}°")
                        else:
                            logger.debug(
                                f"Successfully downloaded image at heading {heading}° from {result.image_source}"
                            )
                    else:
                        logger.warning(f"Failed to capture image at heading {heading}°")

                except Exception:
                    logger.exception(f"Error capturing image at heading {heading}°")
                    capture_results.append(None)

        return capture_results

    async def capture_image_async(
        self,
        lat: float,
        lng: float,
        bench_id: str,
        heading: int,
        session: ClientSession | None = None,
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
            session = ClientSession()

        try:
            # Try sources in order: API, Google streetlevel, Apple streetlevel
            sources_to_try = [
                (ImageSource.STREETVIEW_API, self._capture_from_api),
                (
                    ImageSource.STREETVIEW_STREETLEVEL,
                    self._capture_from_streetlevel_google,
                ),
                (ImageSource.APPLE_STREETLEVEL, self._capture_from_streetlevel_apple),
            ]

            for source, capture_func in sources_to_try:
                # Check if image already exists for this source
                filename = self._generate_filename(bench_id, heading, source)
                filepath = os.path.join(IMAGES_DIR, filename)

                # For Apple, also check if stitched image exists
                if source == ImageSource.APPLE_STREETLEVEL:
                    # Check if stitched image exists (faces may or may not exist)
                    if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                        base_name = filename.replace(".jpg", "")
                        face_names = ["back", "left", "front", "right", "top", "bottom"]
                        logger.debug(
                            f"Apple stitched image already exists: {filename}, checking faces"
                        )
                        # Load metadata if available
                        metadata = self._load_cached_metadata(lat, lng, source.value)
                        panorama_metadata = (
                            metadata.get("panorama_metadata") if metadata else {}
                        )
                        # Update face filenames in metadata
                        if panorama_metadata:
                            panorama_metadata["face_filenames"] = [
                                f"{base_name}_face_{name}.jpg" for name in face_names
                            ]
                        panorama_lat = (
                            metadata.get("panorama_lat") if metadata else None
                        )
                        panorama_lng = (
                            metadata.get("panorama_lng") if metadata else None
                        )

                        try:
                            with PILImage.open(filepath) as img:
                                width, height = img.size
                        except Exception:
                            width = int(STREETVIEW_SIZE.split("x")[0])
                            height = int(STREETVIEW_SIZE.split("x")[1])

                        return StreetViewImageCapture(
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
                            image_source=source.value,
                            panorama_lat=panorama_lat,
                            panorama_lng=panorama_lng,
                            panorama_metadata=panorama_metadata,
                        )
                elif os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                    logger.debug(f"Image already exists: {filename}, skipping download")
                    # Load metadata if available
                    metadata = self._load_cached_metadata(lat, lng, source.value)
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

                    return StreetViewImageCapture(
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
                        image_source=source.value,
                        panorama_lat=panorama_lat,
                        panorama_lng=panorama_lng,
                        panorama_metadata=panorama_metadata,
                    )

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
                            self._save_metadata_cache(lat, lng, source.value, metadata)
                        return result
                except Exception as e:
                    logger.debug(
                        f"Failed to capture from {source.value} for heading {heading}: {e}"
                    )
                    continue

            # All sources failed
            logger.warning(
                f"All sources failed for bench {bench_id} at heading {heading}"
            )
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

        except Exception as e:
            logger.debug(f"Error capturing from API: {e}")
            return None

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
            return None

        try:
            logger.debug(
                f"Requesting street view image from streetlevel (Google): lat={lat}, lng={lng}, heading={heading}"
            )

            # Find panorama
            pano = await streetlevel_streetview.find_panorama_async(
                lat, lng, radius=25, session=session
            )

            if not pano:
                logger.debug("No Google Street View panorama found via streetlevel")
                return None

            # Get panorama image
            img = await streetlevel_streetview.get_panorama_async(
                pano, zoom=2, session=session
            )

            if not img:
                logger.debug("Failed to get panorama image from streetlevel")
                return None

            # Save the image
            img.save(filepath, "JPEG")

            if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
                logger.error(f"Failed to save image to {filepath}")
                return None

            width, height = img.size

            # Extract panorama metadata
            panorama_metadata = {
                "pano_id": pano.id if hasattr(pano, "id") else None,
                "date": str(pano.date) if hasattr(pano, "date") else None,
            }

            # Get panorama location (may differ from requested location)
            panorama_lat = pano.lat if hasattr(pano, "lat") else lat
            panorama_lng = pano.lon if hasattr(pano, "lon") else lng

            logger.debug(
                f"Saved image {filename} from streetlevel (Google): {width}x{height}, panorama at {panorama_lat}, {panorama_lng}"
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
            return None

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
            return None

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
                return None

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
                return None

            pano = closest_pano
            panorama_lat = pano.lat
            panorama_lng = pano.lon

            # Generate filenames for individual faces
            # Face names: BACK=0, LEFT=1, FRONT=2, RIGHT=3, TOP=4, BOTTOM=5
            face_names = ["back", "left", "front", "right", "top", "bottom"]
            base_name = filename.replace(".jpg", "")
            face_filenames = [f"{base_name}_face_{face_names[i]}.jpg" for i in range(6)]
            face_filepaths = [
                os.path.join(IMAGES_DIR, face_filename)
                for face_filename in face_filenames
            ]

            # Check if all faces and stitched image are already cached
            all_faces_cached = all(
                os.path.exists(fp) and os.path.getsize(fp) > 0 for fp in face_filepaths
            )
            stitched_cached = os.path.exists(filepath) and os.path.getsize(filepath) > 0

            if all_faces_cached and stitched_cached:
                logger.debug(
                    f"All Apple Look Around faces and stitched image already cached for {filename}"
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

                with PILImage.open(filepath) as img:
                    width, height = img.size

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

                # Create equirectangular projection if we have all faces
                if all(faces) and len(faces) == 6:
                    if not stitched_cached:
                        equirectangular = await asyncio.to_thread(
                            lookaround.to_equirectangular, faces, pano.camera_metadata
                        )
                        equirectangular.save(filepath, "JPEG")
                        logger.debug(
                            f"Saved stitched equirectangular image to {filename}"
                        )
                    else:
                        logger.debug(
                            f"Using cached stitched equirectangular image {filename}"
                        )
                # Fall back to using just the front face if available
                elif faces[2]:  # FRONT face
                    if not stitched_cached:
                        faces[2].save(filepath, "JPEG")
                        logger.debug(f"Saved front face as fallback to {filename}")
                else:
                    logger.debug("Could not get any faces from Apple Look Around")
                    return None
            except Exception as e:
                logger.debug(f"Error creating equirectangular projection: {e}")
                return None

            if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
                logger.error(f"Failed to save image to {filepath}")
                return None

            # Get image dimensions
            with PILImage.open(filepath) as img:
                width, height = img.size

            # Extract panorama metadata
            panorama_metadata = {
                "pano_id": pano.id if hasattr(pano, "id") else None,
                "date": str(pano.date) if hasattr(pano, "date") else None,
                "face_filenames": face_filenames,  # Track individual face files
            }

            logger.debug(
                f"Saved image {filename} from streetlevel (Apple): {width}x{height}, panorama at {panorama_lat}, {panorama_lng}, with {len([f for f in faces if f is not None])} faces"
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
                cached=all_faces_cached and stitched_cached,
                error=None,
                image_source=ImageSource.APPLE_STREETLEVEL.value,
                panorama_lat=panorama_lat,
                panorama_lng=panorama_lng,
                panorama_metadata=panorama_metadata,
            )

        except Exception as e:
            logger.debug(f"Error capturing from streetlevel (Apple): {e}")
            return None

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
