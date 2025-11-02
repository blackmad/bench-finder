#!/usr/bin/env python3
"""
Add spatial indexes for PostgreSQL bounding box queries.

This script adds PostGIS spatial indexes (GIST) for efficient bounding box queries
on location columns. It checks for PostGIS availability and falls back to regular
GIST indexes if PostGIS is not installed.

For PostgreSQL, bounding box queries using lat/lng BETWEEN clauses are inefficient
with regular B-tree indexes. PostGIS GIST indexes provide much better performance.
"""

import logging
import sys

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from bench_finder.config import DATABASE_URL
from bench_finder.models.unified_models import create_database_engine


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def check_postgis_available(engine: Engine) -> bool:
    """Check if PostGIS extension is available in the database."""
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text("SELECT COUNT(*) FROM pg_extension WHERE extname = 'postgis';")
            ).scalar()
            return result > 0
    except Exception as e:
        logger.debug(f"Error checking PostGIS: {e}")
        return False


def enable_postgis(engine: Engine, dry_run: bool = False) -> bool:
    """Enable PostGIS extension if available."""
    try:
        with engine.begin() as conn:
            # Check if extension is available (even if not enabled)
            result = conn.execute(
                text(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM pg_available_extensions
                        WHERE name = 'postgis'
                    );
                    """
                )
            ).scalar()

            if not result:
                logger.warning("PostGIS extension is not available in this database")
                return False

            # Check if already enabled
            if check_postgis_available(engine):
                logger.info("PostGIS extension is already enabled")
                return True

            if dry_run:
                logger.info("[DRY RUN] Would enable PostGIS extension")
                return True

            # Enable PostGIS
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
            logger.info("✅ Enabled PostGIS extension")
            return True
    except Exception as e:
        logger.warning(f"Failed to enable PostGIS (will use fallback): {e}")
        return False


def create_postgis_spatial_index(
    engine: Engine,
    table_name: str,
    index_name: str,
    lat_col: str,
    lng_col: str,
    dry_run: bool = False,
) -> bool:
    """
    Create PostGIS GIST spatial index using geography/geometry point type.

    This is the optimal solution for PostgreSQL spatial queries.
    """
    # Use CAST() instead of :: for better compatibility with SQLAlchemy
    create_sql = f"""
        CREATE INDEX IF NOT EXISTS {index_name}
        ON {table_name}
        USING GIST (
            CAST(ST_MakePoint({lng_col}, {lat_col}) AS geography)
        );
    """

    if dry_run:
        logger.info(f"[DRY RUN] Would create PostGIS spatial index: {index_name}")
        return True

    try:
        with engine.begin() as conn:
            conn.execute(text(create_sql))
        logger.info(f"✅ Created PostGIS spatial index: {index_name}")
        return True
    except Exception as e:
        logger.warning(f"Failed to create PostGIS index {index_name}: {e}")
        return False


def create_fallback_spatial_index(
    engine: Engine,
    table_name: str,
    index_name: str,
    lat_col: str,
    lng_col: str,
    dry_run: bool = False,
) -> bool:
    """
    Create fallback GIST index on composite (lat, lng) columns.

    This is less optimal than PostGIS but better than B-tree for spatial queries.
    """
    create_sql = f"""
        CREATE INDEX IF NOT EXISTS {index_name}
        ON {table_name}
        USING GIST (
            point({lng_col}, {lat_col})
        );
    """

    if dry_run:
        logger.info(f"[DRY RUN] Would create fallback spatial index: {index_name}")
        return True

    try:
        with engine.begin() as conn:
            conn.execute(text(create_sql))
        logger.info(f"✅ Created fallback spatial index: {index_name}")
        return True
    except Exception as e:
        logger.warning(f"Failed to create fallback index {index_name}: {e}")
        # Try even simpler composite index
        return create_simple_composite_index(
            engine, table_name, index_name, lat_col, lng_col, dry_run
        )


def create_simple_composite_index(
    engine: Engine,
    table_name: str,
    index_name: str,
    lat_col: str,
    lng_col: str,
    dry_run: bool = False,
) -> bool:
    """
    Create a simple B-tree composite index as last resort.

    This is better than nothing but not optimal for spatial queries.
    """
    create_sql = f"""
        CREATE INDEX IF NOT EXISTS {index_name}
        ON {table_name} ({lat_col}, {lng_col});
    """

    if dry_run:
        logger.info(f"[DRY RUN] Would create composite B-tree index: {index_name}")
        return True

    try:
        with engine.begin() as conn:
            conn.execute(text(create_sql))
        logger.info(f"✅ Created composite B-tree index: {index_name}")
        return True
    except Exception:
        logger.exception(f"Failed to create index {index_name}")
        return False


def index_exists(engine: Engine, index_name: str) -> bool:
    """Check if an index already exists."""
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM pg_indexes
                    WHERE indexname = :index_name;
                    """
                ),
                {"index_name": index_name},
            ).scalar()
            return result > 0
    except Exception as e:
        logger.debug(f"Error checking index existence: {e}")
        return False


def create_spatial_index_for_table(
    engine: Engine,
    table_name: str,
    index_name: str,
    lat_col: str,
    lng_col: str,
    use_postgis: bool,
    dry_run: bool = False,
) -> bool:
    """Create the best available spatial index for a table."""
    if index_exists(engine, index_name):
        logger.info(f"⏭️  Index already exists: {index_name}")
        return True

    if use_postgis:
        success = create_postgis_spatial_index(
            engine, table_name, index_name, lat_col, lng_col, dry_run
        )
        if success:
            return True
        logger.info(f"PostGIS index failed for {table_name}, trying fallback...")

    # Try fallback point-based GIST index
    fallback_name = index_name.replace("_postgis", "") + "_gist"
    success = create_fallback_spatial_index(
        engine, table_name, fallback_name, lat_col, lng_col, dry_run
    )
    return success


def check_missing_indexes(engine: Engine) -> list[dict]:
    """
    Check for other missing indexes that might be beneficial.

    Returns list of suggested indexes.
    """
    inspector = inspect(engine)
    existing_indexes = set()

    # Collect all existing index names
    for table_name in inspector.get_table_names():
        for index in inspector.get_indexes(table_name):
            existing_indexes.add(index["name"])

    suggestions = []

    # Check for missing indexes on commonly queried columns
    indexes_to_check = [
        # Foreign key indexes (should already exist from migration, but double-check)
        (
            "processed_benches",
            "idx_processed_benches_bench_candidate_id",
            "bench_candidate_id",
        ),
        (
            "processed_benches",
            "idx_processed_benches_best_detection_id",
            "best_detection_id",
        ),
        ("processed_benches", "idx_processed_benches_best_image_id", "best_image_id"),
        ("images", "idx_images_bench_candidate_id", "bench_candidate_id"),
        ("detections", "idx_detections_image_id", "image_id"),
        ("detection_items", "idx_detection_items_detection_id", "detection_id"),
        # Filter column indexes
        (
            "processed_benches",
            "idx_processed_benches_detection_status",
            "detection_status",
        ),
        ("detections", "idx_detections_max_confidence", "max_confidence"),
        ("bench_candidates", "idx_bench_candidates_source", "source"),
        ("images", "idx_images_capture_success", "capture_success"),
        # Composite indexes for common query patterns
        (
            "processed_benches",
            "idx_processed_benches_status_detection",
            "detection_status, best_detection_id",
        ),
        (
            "images",
            "idx_images_bench_success",
            "bench_candidate_id, capture_success",
        ),
        (
            "bench_candidates",
            "idx_bench_candidates_source_lat_lng",
            "source, lat, lng",
        ),
        # Date-based indexes for time-based queries
        ("missing_bench_reports", "idx_missing_bench_reports_created_at", "created_at"),
        ("bench_candidates", "idx_bench_candidates_created_at", "created_at"),
    ]

    for table_name, index_name, columns in indexes_to_check:
        if (
            index_name not in existing_indexes
            and table_name in inspector.get_table_names()
        ):
            suggestions.append(
                {
                    "table": table_name,
                    "index": index_name,
                    "columns": columns,
                }
            )

    return suggestions


def create_missing_index(
    engine: Engine,
    table_name: str,
    index_name: str,
    columns: str,
    dry_run: bool = False,
) -> bool:
    """Create a missing index."""
    create_sql = f"""
        CREATE INDEX IF NOT EXISTS {index_name}
        ON {table_name} ({columns});
    """

    if dry_run:
        logger.info(
            f"[DRY RUN] Would create index: {index_name} on {table_name}({columns})"
        )
        return True

    try:
        with engine.begin() as conn:
            conn.execute(text(create_sql))
        logger.info(f"✅ Created index: {index_name} on {table_name}({columns})")
        return True
    except Exception as e:
        logger.warning(f"⚠️  Failed to create index {index_name}: {e}")
        return False


def main():
    """Main function to add spatial indexes."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Add spatial indexes for PostgreSQL bounding box queries"
    )
    parser.add_argument(
        "--database-url",
        type=str,
        default=DATABASE_URL,
        help="PostgreSQL database URL (default: from config)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be created without actually creating indexes",
    )
    parser.add_argument(
        "--enable-postgis",
        action="store_true",
        help="Attempt to enable PostGIS extension if not already enabled",
    )
    parser.add_argument(
        "--check-other-indexes",
        action="store_true",
        help="Also check and create other missing indexes",
    )
    args = parser.parse_args()

    if not args.database_url:
        logger.error("DATABASE_URL not provided and not found in config")
        sys.exit(1)

    if not args.database_url.startswith("postgresql"):
        logger.warning(
            "This script is designed for PostgreSQL. "
            f"Detected database type: {args.database_url.split('://')[0]}"
        )
        response = input("Continue anyway? (y/N): ")
        if response.lower() != "y":
            sys.exit(0)

    logger.info("Connecting to database...")
    engine = create_database_engine(database_url=args.database_url)

    # Check database type
    is_postgresql = engine.dialect.name == "postgresql"
    if not is_postgresql:
        logger.error("This script is for PostgreSQL databases only!")
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("PostgreSQL Spatial Index Migration")
    logger.info("=" * 60)

    # Check/enable PostGIS
    use_postgis = False
    if args.enable_postgis:
        use_postgis = enable_postgis(engine, dry_run=args.dry_run)
    else:
        use_postgis = check_postgis_available(engine)
        if use_postgis:
            logger.info("✅ PostGIS is available and enabled")
        else:
            logger.info("ℹ️  PostGIS is not enabled (use --enable-postgis to enable it)")

    logger.info("")

    # Tables that need spatial indexes for bounding box queries
    spatial_indexes = [
        {
            "table": "bench_candidates",
            "index": "idx_bench_candidates_location_postgis",
            "lat_col": "lat",
            "lng_col": "lng",
            "description": "Main table for bbox queries",
        },
        {
            "table": "missing_bench_reports",
            "index": "idx_missing_bench_reports_location_postgis",
            "lat_col": "lat",
            "lng_col": "lng",
            "description": "Missing bench reports location",
        },
    ]

    logger.info("Creating spatial indexes for bounding box queries...")
    logger.info("")
    created = 0
    skipped = 0
    failed = 0

    for idx_config in spatial_indexes:
        table_name = idx_config["table"]
        index_name = idx_config["index"]
        lat_col = idx_config["lat_col"]
        lng_col = idx_config["lng_col"]
        description = idx_config.get("description", "")

        logger.info(f"Processing {table_name}: {description}")
        success = create_spatial_index_for_table(
            engine,
            table_name,
            index_name,
            lat_col,
            lng_col,
            use_postgis,
            dry_run=args.dry_run,
        )

        if success:
            if index_exists(engine, index_name) or args.dry_run:
                created += 1
            else:
                skipped += 1
        else:
            failed += 1
        logger.info("")

    logger.info("=" * 60)
    logger.info(
        f"Spatial Indexes: Created {created}, Skipped {skipped}, Failed {failed}"
    )
    logger.info("=" * 60)

    # Check for other missing indexes
    if args.check_other_indexes:
        logger.info("")
        logger.info("Checking for other missing indexes...")
        logger.info("")

        missing = check_missing_indexes(engine)
        if missing:
            logger.info(f"Found {len(missing)} missing indexes:")
            for idx_info in missing:
                logger.info(
                    f"  - {idx_info['index']} on {idx_info['table']}({idx_info['columns']})"
                )
            logger.info("")

            if not args.dry_run:
                response = input("Create these indexes? (Y/n): ")
                if response.lower() != "n":
                    created_other = 0
                    for idx_info in missing:
                        if create_missing_index(
                            engine,
                            idx_info["table"],
                            idx_info["index"],
                            idx_info["columns"],
                            dry_run=args.dry_run,
                        ):
                            created_other += 1
                    logger.info("")
                    logger.info(f"Created {created_other} additional indexes")
        else:
            logger.info("✅ No missing indexes found!")

    logger.info("")
    logger.info("Done!")


if __name__ == "__main__":
    main()
