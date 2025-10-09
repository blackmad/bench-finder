"""
Utility functions for logging, error handling, and other common operations.
"""

import functools
import logging
import sys
import time
from typing import Callable, ParamSpec, TypeVar, Union

from .config import LOG_FORMAT, LOG_LEVEL


# Type variables for decorator type preservation
P = ParamSpec("P")
T = TypeVar("T")


def setup_logging(level: Union[str, None] = None, format_str: Union[str, None] = None):
    """
    Configure logging for the application.

    Args:
        level: Log level (defaults to config LOG_LEVEL if None)
        format_str: Log format string (defaults to config LOG_FORMAT if None)
    """
    level = LOG_LEVEL if level is None else level
    format_str = LOG_FORMAT if format_str is None else format_str

    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {level}")

    # Configure root logger
    logging.basicConfig(level=numeric_level, format=format_str, stream=sys.stdout)

    # Set specific loggers to appropriate levels
    logging.getLogger("urllib3").setLevel(logging.WARNING)  # Suppress HTTP debug logs
    logging.getLogger("googlemaps").setLevel(logging.INFO)  # Google Maps client logs
    logging.getLogger("PIL").setLevel(logging.WARNING)  # Pillow image processing logs

    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured at {level.upper()} level")


def retry_on_failure(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """
    Decorator that retries a function on failure with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Multiplier for delay after each retry
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            logger = logging.getLogger(func.__module__)

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries:
                        logger.exception(
                            f"{func.__name__} failed after {max_retries} retries: {e}"
                        )
                        raise

                    sleep_time = delay * (backoff**attempt)
                    logger.warning(
                        f"{func.__name__} attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {sleep_time:.1f}s..."
                    )
                    time.sleep(sleep_time)

            # This should never be reached due to the raise in the except block above
            raise RuntimeError("Unexpected end of retry loop")

        return wrapper

    return decorator


def log_execution_time(func: Callable[P, T]) -> Callable[P, T]:
    """
    Decorator that logs the execution time of a function.
    """

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        logger = logging.getLogger(func.__module__)
        start_time = time.time()

        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.debug(f"{func.__name__} completed in {execution_time:.2f}s")
            return result
        except Exception:
            execution_time = time.time() - start_time
            logger.exception(f"{func.__name__} failed after {execution_time:.2f}s")
            raise

    return wrapper


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """
    Safely divide two numbers, returning a default value if denominator is zero.

    Args:
        numerator: The numerator
        denominator: The denominator
        default: Value to return if denominator is zero

    Returns:
        Result of division or default value
    """
    try:
        if denominator == 0:
            return default
        return numerator / denominator
    except (TypeError, ValueError):
        return default


def format_file_size(size_bytes: int) -> str:
    """
    Format a file size in bytes to human readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted size string (e.g., "1.5 MB")
    """
    if size_bytes == 0:
        return "0 B"

    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size_float = float(size_bytes)

    while size_float >= 1024 and i < len(size_names) - 1:
        size_float /= 1024.0
        i += 1

    return f"{size_float:.1f} {size_names[i]}"


def validate_coordinates(lat: float, lng: float) -> bool:
    """
    Validate that latitude and longitude are within valid ranges.

    Args:
        lat: Latitude (-90 to 90)
        lng: Longitude (-180 to 180)

    Returns:
        True if coordinates are valid, False otherwise
    """
    try:
        lat = float(lat)
        lng = float(lng)
        return -90 <= lat <= 90 and -180 <= lng <= 180
    except (TypeError, ValueError):
        return False


def truncate_string(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate a string to a maximum length, adding a suffix if truncated.

    Args:
        text: String to truncate
        max_length: Maximum length of the result
        suffix: Suffix to add if truncated

    Returns:
        Truncated string
    """
    if not text or len(text) <= max_length:
        return text

    return text[: max_length - len(suffix)] + suffix


class ProgressTracker:
    """Simple progress tracker for long-running operations."""

    def __init__(self, total: int, description: str = "Processing"):
        """
        Initialize the progress tracker.

        Args:
            total: Total number of items to process
            description: Description of the operation
        """
        self.total = total
        self.current = 0
        self.description = description
        self.start_time = time.time()
        self.logger = logging.getLogger(__name__)

        self.logger.info(f"Starting {description} - {total} items")

    def update(self, increment: int = 1):
        """
        Update progress by incrementing the current count.

        Args:
            increment: Number of items to add to current count
        """
        self.current += increment

        # Log progress every 10% or every 10 items, whichever is less frequent
        log_interval = max(1, self.total // 10)

        if self.current % log_interval == 0 or self.current == self.total:
            elapsed = time.time() - self.start_time
            rate = safe_divide(self.current, elapsed)
            percentage = safe_divide(self.current * 100, self.total)

            if self.current < self.total:
                remaining_items = self.total - self.current
                eta_seconds = safe_divide(remaining_items, rate)
                eta_str = f", ETA: {eta_seconds:.0f}s" if eta_seconds > 0 else ""

                self.logger.info(
                    f"{self.description}: {self.current}/{self.total} "
                    f"({percentage:.0f}%) - {rate:.1f} items/s{eta_str}"
                )
            else:
                self.logger.info(
                    f"{self.description} completed: {self.current} items "
                    f"in {elapsed:.1f}s ({rate:.1f} items/s)"
                )

    def finish(self):
        """Mark the operation as finished."""
        self.current = max(self.current, self.total)
        self.update(0)  # Force final log message
