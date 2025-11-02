from enum import StrEnum


class DataSource(StrEnum):
    OSM = "OSM"
    MAPILLARY = "MAPILLARY"


class DetectionSource(StrEnum):
    ROBOFLOW = "ROBOFLOW"
    ULTRALYTICS = "ULTRALYTICS"
    MAPILLARY = "MAPILLARY"
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
