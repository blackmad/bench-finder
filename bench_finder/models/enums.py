from enum import StrEnum


class DataSource(StrEnum):
    OSM = "OSM"


class DetectionSource(StrEnum):
    ROBOFLOW = "ROBOFLOW"
    ULTRALYTICS = "ULTRALYTICS"
    MULTI_MODEL = "MULTI_MODEL"
    NONE = "NONE"


class BenchCandidateStatus(StrEnum):
    PENDING = "pending"
    IMAGE_DOWNLOAD_DONE = "image_download_done"
    DETECTION_DONE = "detection_done"


class SearchStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class BenchReportType(StrEnum):
    BAD_DETECTION = "bad_detection"
    INCORRECT_LOCATION = "incorrect_location"
    POOR_IMAGE_QUALITY = "poor_image_quality"


class BenchReportStatus(StrEnum):
    PENDING = "pending"
    REVIEWED = "reviewed"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class MissingBenchReportStatus(StrEnum):
    PENDING = "pending"
    VERIFIED = "verified"
    ADDED = "added"
    DISMISSED = "dismissed"


class LocationMethod(StrEnum):
    GPS = "gps"
    MAP_CLICK = "map_click"


class BenchUserStatus(StrEnum):
    BEEN = "been"
    WANT_TO_GO = "want_to_go"
    FAVORITE = "favorite"


class ImageKind(StrEnum):
    """What an images row holds."""

    AIMED = "aimed"  # perspective view aimed at the bench
    PANO = "pano"  # raw panorama
    LEGACY = "legacy"  # pre-resurrection rows


class ImageSource(StrEnum):
    """Source of the street view image."""

    STREETVIEW_API = "streetview_api"  # Google Street View Static API
    STREETVIEW_STREETLEVEL = (
        "streetview_streetlevel"  # Google Street View via streetlevel library
    )
    APPLE_STREETLEVEL = "apple_streetlevel"  # Apple Look Around via streetlevel library
    AMSTERDAM_PANORAMA = "amsterdam_panorama"  # City of Amsterdam panoramas (open data)
