"""
Firestore database service for bench finder application.
Replaces SQLAlchemy with Firestore for cost-effective cloud database.
"""

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from google.cloud import firestore
from google.cloud.firestore_v1 import SERVER_TIMESTAMP

from bench_finder.config import (
    FIREBASE_CREDENTIALS_BASE64,
    FIREBASE_CREDENTIALS_PATH,
)
from bench_finder.models.enums import DataSource, SearchStatus
from bench_finder.models.unified_models import (
    BenchBase,
    BenchCandidate,
    BenchCandidateStatus,
    Detection,
    DetectionBase,
    DetectionItem,
    Image,
    ImageBase,
    ProcessedBench,
    ReverseGeocode,
    Search,
    SearchBase,
)

if TYPE_CHECKING:
    from google.cloud.firestore_v1.client import Client

logger = logging.getLogger(__name__)

# Firebase Admin SDK initialization
_firestore_client: "Client | None" = None


def _initialize_firestore() -> "Client":
    """Initialize Firestore client if not already initialized."""
    global _firestore_client  # noqa: PLW0603

    if _firestore_client is not None:
        return _firestore_client

    try:
        import base64
        import json

        import firebase_admin
        from firebase_admin import credentials

        # Check if Firebase Admin is already initialized
        try:
            firebase_admin.get_app()
        except ValueError:
            # Initialize Firebase Admin
            cred = None

            # Option 1: Base64-encoded credentials (for Vercel/serverless)
            if FIREBASE_CREDENTIALS_BASE64:
                creds_json = base64.b64decode(FIREBASE_CREDENTIALS_BASE64).decode("utf-8")
                creds_dict = json.loads(creds_json)
                cred = credentials.Certificate(creds_dict)
                logger.info("Firebase Admin SDK initialized with base64 credentials")

            # Option 2: Credentials file path
            elif FIREBASE_CREDENTIALS_PATH:
                cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
                logger.info(
                    f"Firebase Admin SDK initialized with credentials from {FIREBASE_CREDENTIALS_PATH}"
                )

            # Option 3: Application Default Credentials (GCP environments)
            else:
                cred = credentials.ApplicationDefault()
                logger.info(
                    "Firebase Admin SDK initialized with Application Default Credentials"
                )

            firebase_admin.initialize_app(cred)

        # Initialize Firestore client
        _firestore_client = firestore.Client()
        logger.info("Firestore client initialized")
        return _firestore_client

    except Exception as e:
        logger.exception(f"Failed to initialize Firestore: {e}")
        raise


def _model_to_dict(model: Any, exclude_id: bool = False) -> dict[str, Any]:
    """Convert a SQLModel/Pydantic model to a Firestore-compatible dict."""
    if hasattr(model, "model_dump"):
        data = model.model_dump(exclude_none=True)
    elif hasattr(model, "dict"):
        data = model.dict(exclude_none=True)
    else:
        data = dict(model)

    # Remove id if exclude_id is True (for new documents)
    if exclude_id and "id" in data:
        del data["id"]

    # Convert datetime objects to Firestore timestamps
    for key, value in data.items():
        if isinstance(value, datetime):
            data[key] = value
        elif isinstance(value, dict):
            # Recursively handle nested dicts
            data[key] = _model_to_dict(value, exclude_id=False)

    return data


def _dict_to_model(model_class: type, data: dict[str, Any]) -> Any:
    """Convert a Firestore dict to a SQLModel/Pydantic model."""
    # Convert Firestore timestamps to datetime
    for key, value in data.items():
        if hasattr(value, "timestamp"):
            # Firestore timestamp
            data[key] = value.to_datetime()
        elif isinstance(value, dict):
            # Recursively handle nested dicts
            data[key] = _dict_to_model(dict, value)

    return model_class(**data)


class FirestoreDatabase:
    """Firestore database manager for bench finder application."""

    def __init__(self):
        """Initialize Firestore connection."""
        self.client = _initialize_firestore()
        logger.info("FirestoreDatabase initialized")

    # Collection names
    COLLECTION_SEARCHES = "searches"
    COLLECTION_BENCH_CANDIDATES = "bench_candidates"
    COLLECTION_IMAGES = "images"
    COLLECTION_DETECTIONS = "detections"
    COLLECTION_DETECTION_ITEMS = "detection_items"
    COLLECTION_PROCESSED_BENCHES = "processed_benches"
    COLLECTION_REVERSE_GEOCODES = "reverse_geocodes"
    COLLECTION_BENCH_REPORTS = "bench_reports"
    COLLECTION_MISSING_BENCH_REPORTS = "missing_bench_reports"
    COLLECTION_BENCH_RATINGS = "bench_ratings"
    COLLECTION_BENCH_USER_STATUS = "bench_user_status"
    COLLECTION_BENCH_COMMENTS = "bench_comments"

    def create_search(self, search_data: SearchBase) -> int:
        """
        Create a new search record.

        Args:
            search_data: SearchBase schema with search parameters

        Returns:
            The ID of the created search record
        """
        try:
            # Get next ID by finding the max ID and adding 1
            existing = (
                self.client.collection(self.COLLECTION_SEARCHES)
                .order_by("id", direction=firestore.Query.DESCENDING)
                .limit(1)
                .get()
            )
            
            if existing:
                max_id = int(existing[0].to_dict().get("id", 0))
                search_id = max_id + 1
            else:
                search_id = 1

            search_dict = _model_to_dict(search_data, exclude_id=True)
            search_dict["id"] = search_id
            search_dict["created_at"] = SERVER_TIMESTAMP
            search_dict["status"] = SearchStatus.PENDING.value

            # Use integer ID as document ID (stored as string)
            self.client.collection(self.COLLECTION_SEARCHES).document(str(search_id)).set(search_dict)

            logger.info(f"Created search record {search_id} for query: {search_data.query}")
            return search_id

        except Exception:
            logger.exception("Error creating search record")
            raise

    def add_bench(self, bench_data: BenchBase, search_id: int | None = None) -> int:
        """
        Add a bench record to the database.

        Args:
            bench_data: BenchBase schema with bench data from OSM
            search_id: Optional search ID to associate with the bench

        Returns:
            The ID of the created bench record
        """
        try:
            # Check if bench already exists by provider_id
            if bench_data.provider_id:
                existing = (
                    self.client.collection(self.COLLECTION_BENCH_CANDIDATES)
                    .where("provider_id", "==", bench_data.provider_id)
                    .where("source", "==", bench_data.source.value)
                    .limit(1)
                    .get()
                )
                if existing:
                    existing_id = int(existing[0].id)
                    logger.debug(
                        f"Bench {bench_data.provider_id} already exists as record {existing_id}"
                    )
                    return existing_id

            # Get next ID
            existing = (
                self.client.collection(self.COLLECTION_BENCH_CANDIDATES)
                .order_by("id", direction=firestore.Query.DESCENDING)
                .limit(1)
                .get()
            )
            
            if existing:
                max_id = int(existing[0].to_dict().get("id", 0))
                bench_id = max_id + 1
            else:
                bench_id = 1

            bench_dict = _model_to_dict(bench_data, exclude_id=True)
            bench_dict["id"] = bench_id
            bench_dict["search_id"] = search_id
            bench_dict["created_at"] = SERVER_TIMESTAMP
            bench_dict["status"] = BenchCandidateStatus.PENDING.value

            self.client.collection(self.COLLECTION_BENCH_CANDIDATES).document(str(bench_id)).set(bench_dict)

            logger.debug(f"Added bench {bench_data.provider_id} as record {bench_id}")
            return bench_id

        except Exception:
            logger.exception("Error adding bench record")
            raise

    def add_image(self, image_data: ImageBase, bench_id: int) -> int:
        """
        Add an image record to the database.

        Args:
            image_data: ImageBase schema with image capture results
            bench_id: ID of the bench this image belongs to

        Returns:
            The ID of the created image record
        """
        try:
            # Get next ID
            existing = (
                self.client.collection(self.COLLECTION_IMAGES)
                .order_by("id", direction=firestore.Query.DESCENDING)
                .limit(1)
                .get()
            )
            
            if existing:
                max_id = int(existing[0].to_dict().get("id", 0))
                image_id = max_id + 1
            else:
                image_id = 1

            image_dict = _model_to_dict(image_data, exclude_id=True)
            image_dict["id"] = image_id
            image_dict["bench_candidate_id"] = bench_id
            image_dict["created_at"] = SERVER_TIMESTAMP

            self.client.collection(self.COLLECTION_IMAGES).document(str(image_id)).set(image_dict)

            logger.debug(
                f"Added image record {image_id} for bench candidate {bench_id}, heading {image_data.heading}"
            )
            return image_id

        except Exception:
            logger.exception("Error adding image record")
            raise

    def add_detection(self, detection_data: DetectionBase, image_id: int) -> int:
        """
        Add a detection record to the database.

        Args:
            detection_data: DetectionBase schema with detection results
            image_id: ID of the image this detection belongs to

        Returns:
            The ID of the created detection record
        """
        try:
            # Get next ID
            existing = (
                self.client.collection(self.COLLECTION_DETECTIONS)
                .order_by("id", direction=firestore.Query.DESCENDING)
                .limit(1)
                .get()
            )
            
            if existing:
                max_id = int(existing[0].to_dict().get("id", 0))
                detection_id = max_id + 1
            else:
                detection_id = 1

            detection_dict = _model_to_dict(detection_data, exclude_id=True)
            detection_dict["id"] = detection_id
            detection_dict["image_id"] = image_id
            detection_dict["created_at"] = SERVER_TIMESTAMP

            self.client.collection(self.COLLECTION_DETECTIONS).document(str(detection_id)).set(detection_dict)

            # Add detection items if they exist
            if hasattr(detection_data, "detection_items") and detection_data.detection_items:
                # Get next detection item ID
                item_existing = (
                    self.client.collection(self.COLLECTION_DETECTION_ITEMS)
                    .order_by("id", direction=firestore.Query.DESCENDING)
                    .limit(1)
                    .get()
                )
                
                if item_existing:
                    item_max_id = int(item_existing[0].to_dict().get("id", 0))
                    item_id = item_max_id + 1
                else:
                    item_id = 1

                for item_data in detection_data.detection_items:
                    item_dict = _model_to_dict(item_data, exclude_id=True)
                    item_dict["id"] = item_id
                    item_dict["detection_id"] = detection_id
                    item_dict["created_at"] = SERVER_TIMESTAMP
                    self.client.collection(self.COLLECTION_DETECTION_ITEMS).document(str(item_id)).set(item_dict)
                    item_id += 1

            logger.debug(
                f"Added detection record {detection_id} for image {image_id} with {len(getattr(detection_data, 'detection_items', []))} detection items"
            )
            return detection_id

        except Exception:
            logger.exception("Error adding detection record")
            raise

    def update_search_status(
        self,
        search_id: int,
        status: SearchStatus,
        completed_at: datetime | None = None,
    ) -> None:
        """
        Update the status of a search record.

        Args:
            search_id: ID of the search record
            status: New status ('pending', 'completed', 'failed')
            completed_at: Completion timestamp (defaults to current time)
        """
        try:
            if completed_at is None:
                completed_at = datetime.now()

            doc_ref = self.client.collection(self.COLLECTION_SEARCHES).document(str(search_id))
            doc_ref.update({"status": status.value, "completed_at": completed_at})

            logger.debug(f"Updated search {search_id} status to {status}")

        except Exception:
            logger.exception("Error updating search status")
            raise

    def add_bench_candidate(
        self,
        search_id: int,
        provider_id: str,
        lat: float,
        lng: float,
        tags: dict,
        source: DataSource,
        external_id: str | None = None,
        confidence: float | None = None,
    ) -> int | None:
        """
        Add a bench candidate to the database.

        Args:
            search_id: ID of the search this candidate belongs to
            provider_id: Unified ID from OSM or Mapillary
            lat: Latitude
            lng: Longitude
            tags: JSON tags/metadata
            source: Source of the candidate ('osm', 'mapillary', etc.)
            external_id: External ID if applicable
            confidence: Confidence score if available

        Returns:
            ID of the created bench candidate, or None if failed
        """
        try:
            # Get next ID
            existing = (
                self.client.collection(self.COLLECTION_BENCH_CANDIDATES)
                .order_by("id", direction=firestore.Query.DESCENDING)
                .limit(1)
                .get()
            )
            
            if existing:
                max_id = int(existing[0].to_dict().get("id", 0))
                candidate_id = max_id + 1
            else:
                candidate_id = 1

            candidate_dict = {
                "id": candidate_id,
                "search_id": search_id,
                "provider_id": provider_id,
                "lat": lat,
                "lng": lng,
                "tags": tags,
                "source": source.value,
                "external_id": external_id,
                "confidence": confidence,
                "status": BenchCandidateStatus.PENDING.value,
                "created_at": SERVER_TIMESTAMP,
            }

            self.client.collection(self.COLLECTION_BENCH_CANDIDATES).document(str(candidate_id)).set(candidate_dict)

            logger.debug(f"Added bench candidate: {provider_id} from {source}")
            return candidate_id

        except Exception:
            logger.exception("Error adding bench candidate")
            return None

    def get_bench_candidates(self, search_id: int) -> list[BenchCandidate]:
        """
        Get all bench candidates for a search.

        Args:
            search_id: ID of the search

        Returns:
            List of BenchCandidate objects
        """
        try:
            docs = (
                self.client.collection(self.COLLECTION_BENCH_CANDIDATES)
                .where("search_id", "==", search_id)
                .get()
            )

            candidates = []
            for doc in docs:
                data = doc.to_dict()
                if "id" not in data:
                    data["id"] = int(doc.id)
                else:
                    data["id"] = int(data["id"])
                candidates.append(_dict_to_model(BenchCandidate, data))

            return candidates

        except Exception:
            logger.exception("Error getting bench candidates")
            return []

    def get_bench_candidate_count(self, search_id: int) -> int:
        """
        Get count of bench candidates for a search.

        Args:
            search_id: ID of the search

        Returns:
            Number of bench candidates
        """
        try:
            docs = (
                self.client.collection(self.COLLECTION_BENCH_CANDIDATES)
                .where("search_id", "==", search_id)
                .get()
            )
            return len(list(docs))

        except Exception:
            logger.exception("Error getting bench candidate count")
            return 0

    def update_bench_candidate_status(self, candidate_id: int, status: str) -> bool:
        """
        Update the status of a bench candidate.

        Args:
            candidate_id: ID of the bench candidate
            status: New status ('pending', 'image_download_done', 'detection_done')

        Returns:
            True if update was successful, False otherwise
        """
        try:
            doc_ref = self.client.collection(self.COLLECTION_BENCH_CANDIDATES).document(
                str(candidate_id)
            )
            doc_ref.update({"status": status})

            logger.debug(f"Updated candidate {candidate_id} status to {status}")
            return True

        except Exception:
            logger.exception(f"Error updating candidate {candidate_id} status to {status}")
            return False

    def get_bench_candidates_by_status(
        self,
        status: BenchCandidateStatus,
        search_id: int | None = None,
    ) -> list[BenchCandidate]:
        """
        Get bench candidates for a search filtered by status.

        Args:
            status: Status to filter by ('pending', 'image_download_done', 'detection_done')
            search_id: Optional search ID to filter by

        Returns:
            List of BenchCandidate objects with the specified status
        """
        try:
            query = self.client.collection(self.COLLECTION_BENCH_CANDIDATES).where(
                "status", "==", status.value
            )

            if search_id is not None:
                query = query.where("search_id", "==", search_id)

            docs = query.get()

            candidates = []
            for doc in docs:
                data = doc.to_dict()
                if "id" not in data:
                    data["id"] = int(doc.id)
                else:
                    data["id"] = int(data["id"])
                candidates.append(_dict_to_model(BenchCandidate, data))

            return candidates

        except Exception:
            logger.exception("Error getting bench candidates by status")
            return []

    def get_latest_search_id(self) -> int | None:
        """
        Get the ID of the most recently created search.

        Returns:
            The latest search ID, or None if no searches exist
        """
        try:
            docs = (
                self.client.collection(self.COLLECTION_SEARCHES)
                .order_by("created_at", direction=firestore.Query.DESCENDING)
                .limit(1)
                .get()
            )

            if docs:
                data = docs[0].to_dict()
                if "id" in data:
                    return int(data["id"])
                return int(docs[0].id)
            return None

        except Exception:
            logger.exception("Error getting latest search ID")
            return None

    def clear_detections_table(self) -> int:
        """
        Clear all records from the detections table.

        Returns:
            Number of detections that were deleted
        """
        try:
            docs = self.client.collection(self.COLLECTION_DETECTIONS).get()
            count = len(list(docs))

            # Delete in batches
            batch = self.client.batch()
            batch_count = 0
            for doc in docs:
                batch.delete(doc.reference)
                batch_count += 1
                if batch_count >= 500:  # Firestore batch limit
                    batch.commit()
                    batch = self.client.batch()
                    batch_count = 0

            if batch_count > 0:
                batch.commit()

            logger.info(f"Cleared {count} detections from database")
            return count

        except Exception:
            logger.exception("Error clearing detections table")
            return 0

    def upsert_detected_bench(
        self, bench_id: int, image_id: int, confidence: float
    ) -> int:
        """
        Create or update the best detected image for a bench candidate.

        Args:
            bench_id: bench_candidate_id (legacy parameter name kept for compatibility)
            image_id: ID of the best image
            confidence: Confidence score

        Returns the ProcessedBench.id
        """
        try:
            # Get the best detection for this image (highest confidence)
            best_detection_id = None
            detections = (
                self.client.collection(self.COLLECTION_DETECTIONS)
                .where("image_id", "==", image_id)
                .order_by("max_confidence", direction=firestore.Query.DESCENDING)
                .limit(1)
                .get()
            )

            if detections:
                best_detection_id = int(detections[0].to_dict().get("id", detections[0].id))

            # Check if ProcessedBench already exists
            existing = (
                self.client.collection(self.COLLECTION_PROCESSED_BENCHES)
                .where("bench_candidate_id", "==", bench_id)
                .limit(1)
                .get()
            )

            if existing:
                doc_ref = existing[0].reference
                doc_ref.update(
                    {
                        "best_image_id": image_id,
                        "best_detection_id": best_detection_id,
                        "detection_status": "detected",
                    }
                )
                logger.debug(
                    f"Updated ProcessedBench for bench candidate {bench_id} -> image {image_id} (confidence {confidence:.2f})"
                )
                return int(doc_ref.id)

            # Get next ID
            existing_id = (
                self.client.collection(self.COLLECTION_PROCESSED_BENCHES)
                .order_by("id", direction=firestore.Query.DESCENDING)
                .limit(1)
                .get()
            )
            
            if existing_id:
                max_id = int(existing_id[0].to_dict().get("id", 0))
                processed_id = max_id + 1
            else:
                processed_id = 1

            # Create new ProcessedBench
            processed_dict = {
                "id": processed_id,
                "bench_candidate_id": bench_id,
                "best_image_id": image_id,
                "best_detection_id": best_detection_id,
                "detection_status": "detected",
                "created_at": SERVER_TIMESTAMP,
            }

            self.client.collection(self.COLLECTION_PROCESSED_BENCHES).document(str(processed_id)).set(processed_dict)
            logger.debug(
                f"Inserted ProcessedBench for bench candidate {bench_id} -> image {image_id} (confidence {confidence:.2f})"
            )
            return processed_id

        except Exception:
            logger.exception("Error upserting ProcessedBench record")
            raise

    def reset_bench_candidate_detection_status(self) -> int:
        """
        Reset bench candidate status from DETECTION_DONE to IMAGE_DOWNLOAD_DONE.

        Returns:
            Number of candidates that were reset
        """
        try:
            candidates = (
                self.client.collection(self.COLLECTION_BENCH_CANDIDATES)
                .where("status", "==", BenchCandidateStatus.DETECTION_DONE.value)
                .get()
            )

            count = 0
            batch = self.client.batch()
            batch_count = 0

            for doc in candidates:
                batch.update(doc.reference, {"status": BenchCandidateStatus.IMAGE_DOWNLOAD_DONE.value})
                batch_count += 1
                count += 1

                if batch_count >= 500:
                    batch.commit()
                    batch = self.client.batch()
                    batch_count = 0

            if batch_count > 0:
                batch.commit()

            logger.info(
                f"Reset {count} bench candidates from DETECTION_DONE to IMAGE_DOWNLOAD_DONE"
            )
            return count

        except Exception:
            logger.exception("Error resetting bench candidate detection status")
            return 0

    def reset_bench_candidate_image_status(self) -> int:
        """
        Reset bench candidate status from IMAGE_DOWNLOAD_DONE or DETECTION_DONE to PENDING.

        Returns:
            Number of candidates that were reset
        """
        try:
            # Firestore doesn't support "in" with multiple values directly, so we need to query separately
            candidates_done = (
                self.client.collection(self.COLLECTION_BENCH_CANDIDATES)
                .where("status", "==", BenchCandidateStatus.IMAGE_DOWNLOAD_DONE.value)
                .get()
            )
            candidates_detection = (
                self.client.collection(self.COLLECTION_BENCH_CANDIDATES)
                .where("status", "==", BenchCandidateStatus.DETECTION_DONE.value)
                .get()
            )
            # Combine results
            candidates = list(candidates_done) + list(candidates_detection)

            count = 0
            batch = self.client.batch()
            batch_count = 0

            for doc in candidates:
                batch.update(doc.reference, {"status": BenchCandidateStatus.PENDING.value})
                batch_count += 1
                count += 1

                if batch_count >= 500:
                    batch.commit()
                    batch = self.client.batch()
                    batch_count = 0

            if batch_count > 0:
                batch.commit()

            logger.info(f"Reset {count} bench candidates to PENDING status")
            return count

        except Exception:
            logger.exception("Error resetting bench candidate image status")
            return 0

    def get_random_streetview_image(self) -> Image | None:
        """
        Get a random streetview image that was successfully captured.

        Returns:
            Random Image object with successful capture, or None if no images found
        """
        try:
            # Firestore doesn't have a native random query, so we'll get all and pick one
            # For better performance, we could use a random offset
            import random

            images = (
                self.client.collection(self.COLLECTION_IMAGES)
                .where("capture_success", "==", True)
                .where("filepath", "!=", None)
                .get()
            )

            images_list = list(images)
            if not images_list:
                logger.warning("No successful streetview images found in database")
                return None

            random_doc = random.choice(images_list)
            data = random_doc.to_dict()
            if "id" not in data:
                data["id"] = int(random_doc.id)
            else:
                data["id"] = int(data["id"])
            image = _dict_to_model(Image, data)

            logger.debug(f"Selected random image: {image.filename}")
            return image

        except Exception:
            logger.exception("Error getting random streetview image")
            return None

    def add_or_update_reverse_geocode(
        self,
        bench_candidate_id: int,
        formatted_address: str,
        street_number: str | None = None,
        street_name: str | None = None,
        city: str | None = None,
        state: str | None = None,
        postal_code: str | None = None,
        country: str | None = None,
        raw_response: dict[str, Any] | None = None,
    ) -> int | None:
        """
        Add or update reverse geocode for a bench candidate.

        Args:
            bench_candidate_id: ID of the bench candidate
            formatted_address: Formatted address string from reverse geocoding
            street_number: Street number (optional)
            street_name: Street name/route (optional)
            city: City/locality (optional)
            state: State/administrative area (optional)
            postal_code: Postal/ZIP code (optional)
            country: Country code (optional)
            raw_response: Optional raw API response for future reference

        Returns:
            ID of the created/updated reverse geocode record, or None if failed
        """
        try:
            # Check if reverse geocode already exists
            existing = (
                self.client.collection(self.COLLECTION_REVERSE_GEOCODES)
                .where("bench_candidate_id", "==", bench_candidate_id)
                .limit(1)
                .get()
            )

            geocode_dict = {
                "bench_candidate_id": bench_candidate_id,
                "formatted_address": formatted_address,
                "street_number": street_number,
                "street_name": street_name,
                "city": city,
                "state": state,
                "postal_code": postal_code,
                "country": country,
                "raw_response": raw_response,
            }

            if existing:
                # Update existing record
                doc_ref = existing[0].reference
                geocode_dict["updated_at"] = SERVER_TIMESTAMP
                doc_ref.update(geocode_dict)
                geocode_id = int(existing[0].to_dict().get("id", existing[0].id))
                logger.debug(
                    f"Updated reverse geocode for bench candidate {bench_candidate_id}"
                )
                return geocode_id
            else:
                # Get next ID
                id_existing = (
                    self.client.collection(self.COLLECTION_REVERSE_GEOCODES)
                    .order_by("id", direction=firestore.Query.DESCENDING)
                    .limit(1)
                    .get()
                )
                
                if id_existing:
                    max_id = int(id_existing[0].to_dict().get("id", 0))
                    geocode_id = max_id + 1
                else:
                    geocode_id = 1

                # Create new record
                geocode_dict["id"] = geocode_id
                geocode_dict["created_at"] = SERVER_TIMESTAMP
                self.client.collection(self.COLLECTION_REVERSE_GEOCODES).document(str(geocode_id)).set(geocode_dict)
                logger.debug(
                    f"Added reverse geocode for bench candidate {bench_candidate_id}: {formatted_address[:50]}..."
                )
                return geocode_id

        except Exception:
            logger.exception(
                f"Error adding/updating reverse geocode for bench candidate {bench_candidate_id}"
            )
            return None

    def get_reverse_geocode(self, bench_candidate_id: int) -> ReverseGeocode | None:
        """
        Get reverse geocode for a bench candidate.

        Args:
            bench_candidate_id: ID of the bench candidate

        Returns:
            ReverseGeocode object if found, None otherwise
        """
        try:
            docs = (
                self.client.collection(self.COLLECTION_REVERSE_GEOCODES)
                .where("bench_candidate_id", "==", bench_candidate_id)
                .limit(1)
                .get()
            )

            if docs:
                data = docs[0].to_dict()
                if "id" not in data:
                    data["id"] = int(docs[0].id)
                else:
                    data["id"] = int(data["id"])
                return _dict_to_model(ReverseGeocode, data)

            return None

        except Exception:
            logger.exception(
                f"Error getting reverse geocode for bench candidate {bench_candidate_id}"
            )
            return None

    def get_bench_candidates_without_reverse_geocode(
        self, limit: int | None = None
    ) -> list[BenchCandidate]:
        """
        Get bench candidates that don't have reverse geocode yet.

        Args:
            limit: Optional limit on number of candidates to return

        Returns:
            List of BenchCandidate objects without reverse geocode
        """
        try:
            # Get all bench candidates
            candidates_query = self.client.collection(self.COLLECTION_BENCH_CANDIDATES)

            if limit:
                candidates_query = candidates_query.limit(limit)

            candidates = candidates_query.get()

            # Get all reverse geocodes
            geocodes = (
                self.client.collection(self.COLLECTION_REVERSE_GEOCODES).get()
            )
            geocode_bench_ids = {int(doc.to_dict()["bench_candidate_id"]) for doc in geocodes}

            # Filter candidates without geocode
            result = []
            for doc in candidates:
                data = doc.to_dict()
                if "id" not in data:
                    candidate_id = int(doc.id)
                else:
                    candidate_id = int(data["id"])
                if candidate_id not in geocode_bench_ids:
                    data["id"] = candidate_id
                    result.append(_dict_to_model(BenchCandidate, data))

            return result

        except Exception:
            logger.exception("Error getting bench candidates without reverse geocode")
            return []

    def close(self) -> None:
        """Close database connection if needed."""
        # Firestore client doesn't need explicit closing
        pass

    def get_session(self) -> "Client":
        """Get Firestore client (for compatibility with SQLAlchemy interface)."""
        return self.client

