from enum import StrEnum


class DataSource(StrEnum):
    OSM = "osm"
    MAPILLARY = "mapillary"


class DetectionSource(StrEnum):
    ROBOFLOW = "roboflow"
    ULTRALYTICS = "ultralytics"
    MAPILLARY = "mapillary"


class BenchCandidateStatus(StrEnum):
    PENDING = "pending"
    IMAGE_DOWNLOAD_DONE = "image_download_done"
    DETECTION_DONE = "detection_done"


class SearchStatus(StrEnum):
    PENDING = "pending"
    # Add more states later if needed


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
