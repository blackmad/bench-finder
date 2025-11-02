"""
Image storage service abstraction for local filesystem and Firebase Storage.

This module provides an abstraction layer for storing and retrieving images,
supporting both local filesystem storage (for development) and Firebase Storage
(for production hosting).
"""

import base64
import binascii
import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path


logger = logging.getLogger(__name__)


class ImageStorageService(ABC):
    """Abstract base class for image storage services."""

    @abstractmethod
    async def upload_image(self, file_path: str, filename: str) -> str:
        """
        Upload an image and return a public URL.

        Args:
            file_path: Local file path to the image
            filename: Destination filename (may be modified for uniqueness)

        Returns:
            Public URL to access the uploaded image
        """

    @abstractmethod
    async def get_image_url(self, filename: str) -> str | None:
        """
        Get public URL for an image by filename.

        Args:
            filename: Image filename

        Returns:
            Public URL if image exists, None otherwise
        """

    @abstractmethod
    async def delete_image(self, filename: str) -> bool:
        """
        Delete an image.

        Args:
            filename: Image filename to delete

        Returns:
            True if deletion was successful, False otherwise
        """

    @abstractmethod
    def exists(self, filename: str) -> bool:
        """
        Check if an image exists.

        Args:
            filename: Image filename to check

        Returns:
            True if image exists, False otherwise
        """


class LocalImageStorage(ImageStorageService):
    """Local filesystem-based image storage service."""

    def __init__(self, images_dir: str = "images"):
        """
        Initialize local image storage.

        Args:
            images_dir: Directory where images are stored
        """
        self.images_dir = Path(images_dir)
        self.images_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"LocalImageStorage initialized with directory: {self.images_dir}")

    async def upload_image(self, file_path: str, filename: str) -> str:
        """
        For local storage, 'upload' just means copying to the images directory.
        Returns a relative path that can be served via the /images endpoint.

        Args:
            file_path: Source file path
            filename: Destination filename

        Returns:
            Relative path to the image (for serving via /images/{filename})
        """
        import shutil

        source_path = Path(file_path)
        if not source_path.exists():
            raise FileNotFoundError(f"Source file does not exist: {file_path}")

        dest_path = self.images_dir / filename
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        # Copy the file
        shutil.copy2(source_path, dest_path)
        logger.debug(f"Copied image to local storage: {dest_path}")

        # Return the filename (relative path) for serving via /images endpoint
        return filename

    async def get_image_url(self, filename: str) -> str | None:
        """
        Get local file path (relative) for serving.

        Args:
            filename: Image filename

        Returns:
            Filename (relative path) if exists, None otherwise
        """
        file_path = self.images_dir / filename
        if file_path.exists():
            return filename
        return None

    async def delete_image(self, filename: str) -> bool:
        """
        Delete an image from local storage.

        Args:
            filename: Image filename to delete

        Returns:
            True if deletion was successful, False otherwise
        """
        file_path = self.images_dir / filename
        try:
            if file_path.exists():
                file_path.unlink()
                logger.debug(f"Deleted local image: {file_path}")
                return True
            return False
        except Exception:
            logger.exception(f"Error deleting local image {filename}")
            return False

    def exists(self, filename: str) -> bool:
        """
        Check if an image exists in local storage.

        Args:
            filename: Image filename to check

        Returns:
            True if image exists, False otherwise
        """
        file_path = self.images_dir / filename
        return file_path.exists()


class FirebaseImageStorage(ImageStorageService):
    """Firebase Storage-based image storage service."""

    def __init__(
        self,
        bucket_name: str,
        credentials_path: str | None = None,
        credentials_base64: str | None = None,
        storage_path_prefix: str = "images",
        hosting_url: str | None = None,
    ):
        """
        Initialize Firebase Storage service.

        Args:
            bucket_name: Firebase Storage bucket name
            credentials_path: Path to Firebase service account JSON file
            credentials_base64: Base64-encoded Firebase service account JSON (alternative to credentials_path)
            storage_path_prefix: Prefix path in the storage bucket
            hosting_url: Firebase Hosting base URL (e.g., https://project-id.web.app)
                        If provided, image URLs will use Hosting instead of Storage
        """
        try:
            import firebase_admin
            from firebase_admin import credentials, storage
        except ImportError as err:
            raise ImportError(
                "firebase-admin is not installed. Please install it with 'pip install firebase-admin'"
            ) from err

        # Initialize Firebase Admin if not already initialized
        try:
            firebase_admin.get_app()
        except ValueError:
            # Firebase Admin not initialized, initialize it now
            if credentials_base64:
                # Decode base64 credentials and parse JSON
                try:
                    decoded_bytes = base64.b64decode(credentials_base64)
                    credentials_dict = json.loads(decoded_bytes.decode("utf-8"))
                    cred = credentials.Certificate(credentials_dict)
                    _ = firebase_admin.initialize_app(cred)
                except (binascii.Error, json.JSONDecodeError, UnicodeDecodeError) as e:
                    raise ValueError(f"Failed to decode base64 credentials: {e}") from e
            elif credentials_path:
                cred = credentials.Certificate(credentials_path)
                _ = firebase_admin.initialize_app(cred)
            else:
                # Try to use default credentials (e.g., from environment)
                _ = firebase_admin.initialize_app()

        self.bucket_name = bucket_name
        self.bucket = storage.bucket(bucket_name)
        self.storage_path_prefix = storage_path_prefix
        # Normalize hosting URL (remove trailing slash)
        self.hosting_url = hosting_url.rstrip("/") if hosting_url else None

    def _get_storage_path(self, filename: str) -> str:
        """Get full storage path for a filename."""
        if self.storage_path_prefix:
            return f"{self.storage_path_prefix}/{filename}"
        return filename

    def _get_hosting_url(self, filename: str) -> str:
        """
        Get Firebase Hosting URL for an image.

        Args:
            filename: Image filename

        Returns:
            Firebase Hosting URL
        """
        if not self.hosting_url:
            raise ValueError("Firebase Hosting URL not configured")
        # Images are served at root level, e.g., https://project.web.app/filename.jpg
        return f"{self.hosting_url}/{filename}"

    async def upload_image(self, file_path: str, filename: str) -> str:
        """
        Upload an image to Firebase Storage.

        Args:
            file_path: Local file path to the image
            filename: Destination filename

        Returns:
            Public URL to access the uploaded image (Firebase Hosting URL if configured, otherwise Storage URL)
        """
        import asyncio

        source_path = Path(file_path)
        if not source_path.exists():
            raise FileNotFoundError(f"Source file does not exist: {file_path}")

        storage_path = self._get_storage_path(filename)
        blob = self.bucket.blob(storage_path)

        # Upload the file (Firebase Admin SDK is synchronous, run in executor)
        def _upload():
            with open(file_path, "rb") as f:
                file_data = f.read()
            blob.content_type = "image/jpeg"
            blob.upload_from_string(file_data, content_type="image/jpeg")
            blob.make_public()
            return blob.public_url

        # Run synchronous Firebase operation in executor
        loop = asyncio.get_event_loop()
        storage_url = await loop.run_in_executor(None, _upload)

        # Return Firebase Hosting URL if configured, otherwise Storage URL
        if self.hosting_url:
            hosting_url = self._get_hosting_url(filename)
            logger.debug(
                f"Uploaded image to Firebase Storage: {storage_path} -> {hosting_url} (via Hosting)"
            )
            return hosting_url
        else:
            logger.debug(
                f"Uploaded image to Firebase Storage: {storage_path} -> {storage_url}"
            )
            return storage_url

    async def get_image_url(self, filename: str) -> str | None:
        """
        Get public URL for an image by filename.

        Args:
            filename: Image filename

        Returns:
            Public URL if image exists (Firebase Hosting URL if configured, otherwise Storage URL), None otherwise
        """
        storage_path = self._get_storage_path(filename)
        blob = self.bucket.blob(storage_path)

        try:
            if blob.exists():
                # Return Firebase Hosting URL if configured, otherwise Storage URL
                if self.hosting_url:
                    return self._get_hosting_url(filename)
                return blob.public_url
        except Exception:
            logger.exception(f"Error checking Firebase Storage blob {storage_path}")

        return None

    async def delete_image(self, filename: str) -> bool:
        """
        Delete an image from Firebase Storage.

        Args:
            filename: Image filename to delete

        Returns:
            True if deletion was successful, False otherwise
        """
        storage_path = self._get_storage_path(filename)
        blob = self.bucket.blob(storage_path)

        try:
            blob.delete()
            logger.debug(f"Deleted Firebase Storage image: {storage_path}")
            return True
        except Exception:
            logger.exception(f"Error deleting Firebase Storage image {storage_path}")
            return False

    def exists(self, filename: str) -> bool:
        """
        Check if an image exists in Firebase Storage.

        Args:
            filename: Image filename to check

        Returns:
            True if image exists, False otherwise
        """
        storage_path = self._get_storage_path(filename)
        blob = self.bucket.blob(storage_path)

        try:
            return blob.exists()
        except Exception:
            return False


def get_image_storage_service(
    backend: str = "local",
    images_dir: str = "images",
    firebase_bucket: str | None = None,
    firebase_credentials: str | None = None,
    firebase_credentials_base64: str | None = None,
    firebase_storage_prefix: str = "images",
    firebase_hosting_url: str | None = None,
) -> ImageStorageService:
    """
    Factory function to get the appropriate image storage service.

    Args:
        backend: Storage backend ('local' or 'firebase')
        images_dir: Directory for local storage
        firebase_bucket: Firebase Storage bucket name (required for Firebase backend)
        firebase_credentials: Path to Firebase credentials JSON file
        firebase_credentials_base64: Base64-encoded Firebase credentials JSON (alternative to firebase_credentials)
        firebase_storage_prefix: Prefix path in Firebase Storage bucket
        firebase_hosting_url: Firebase Hosting base URL (e.g., https://project-id.web.app)

    Returns:
        ImageStorageService instance
    """
    if backend == "firebase":
        if not firebase_bucket:
            raise ValueError("firebase_bucket is required for Firebase backend")
        return FirebaseImageStorage(
            bucket_name=firebase_bucket,
            credentials_path=firebase_credentials,
            credentials_base64=firebase_credentials_base64,
            storage_path_prefix=firebase_storage_prefix,
            hosting_url=firebase_hosting_url,
        )
    else:
        return LocalImageStorage(images_dir=images_dir)


def get_image_storage_service_from_config() -> ImageStorageService:
    """
    Get image storage service initialized from configuration values.

    This function reads configuration from environment variables (via bench_finder.config)
    and initializes the appropriate storage service. It supports:
    - Local filesystem storage (default)
    - Firebase Storage with credentials from file path or base64-encoded env variable

    Environment variables used:
    - IMAGE_STORAGE_BACKEND: 'local' or 'firebase' (default: 'local')
    - FIREBASE_STORAGE_BUCKET: Firebase bucket name (required for Firebase backend)
    - FIREBASE_CREDENTIALS_PATH: Path to Firebase credentials JSON file
    - FIREBASE_CREDENTIALS_BASE64: Base64-encoded Firebase credentials (alternative to FIREBASE_CREDENTIALS_PATH)
    - FIREBASE_STORAGE_PREFIX: Prefix path in Firebase bucket (default: 'images')
    - FIREBASE_HOSTING_URL: Firebase Hosting base URL (e.g., https://project-id.web.app)
    - IMAGES_DIR: Directory for local storage (default: 'images')

    Returns:
        ImageStorageService instance configured from environment variables

    Raises:
        ValueError: If Firebase backend is selected but required config is missing
    """
    from bench_finder.config import (
        FIREBASE_CREDENTIALS_BASE64,
        FIREBASE_CREDENTIALS_PATH,
        FIREBASE_HOSTING_URL,
        FIREBASE_STORAGE_BUCKET,
        FIREBASE_STORAGE_PREFIX,
        IMAGE_STORAGE_BACKEND,
        IMAGES_DIR,
    )

    return get_image_storage_service(
        backend=IMAGE_STORAGE_BACKEND,
        images_dir=IMAGES_DIR,
        firebase_bucket=FIREBASE_STORAGE_BUCKET,
        firebase_credentials=FIREBASE_CREDENTIALS_PATH,
        firebase_credentials_base64=FIREBASE_CREDENTIALS_BASE64,
        firebase_storage_prefix=FIREBASE_STORAGE_PREFIX,
        firebase_hosting_url=FIREBASE_HOSTING_URL,
    )
