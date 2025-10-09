#!/usr/bin/env python3
"""
Bench clustering system for de-duplicating nearby benches.

This module provides functionality to group benches that are within a configurable
distance of each other, reducing duplication in the results while preserving
access to the underlying individual benches.
"""

import json
import logging
import math
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ..config import DATABASE_PATH
from ..services.database import BenchDatabase


logger = logging.getLogger(__name__)

# Default clustering configuration
DEFAULT_CLUSTER_DISTANCE_METERS = 5.0  # 5 meters default clustering distance
MIN_CLUSTER_DISTANCE_METERS = 1.0  # Minimum allowed clustering distance
MAX_CLUSTER_DISTANCE_METERS = 50.0  # Maximum allowed clustering distance


@dataclass
class BenchData:
    """Represents a bench with its essential data for clustering."""

    id: int
    lat: float
    lng: float
    best_confidence: float
    source: str
    provider_id: str
    image_count: int


@dataclass
class BenchCluster:
    """Represents a cluster of nearby benches."""

    id: int
    center_lat: float
    center_lng: float
    bench_ids: list[int]
    best_bench_id: int
    max_distance_meters: float
    bench_count: int
    avg_confidence: float
    sources: set[str]
    created_at: datetime
    updated_at: datetime


class BenchClusterer:
    """Handles clustering of benches based on geographic proximity."""

    def __init__(
        self,
        db_path: Optional[str] = None,
        cluster_distance_meters: float = DEFAULT_CLUSTER_DISTANCE_METERS,
    ):
        """
        Initialize the clusterer.

        Args:
            db_path: Path to the database (defaults to config DATABASE_PATH)
            cluster_distance_meters: Maximum distance between benches in a cluster
        """
        self.db_path = db_path or DATABASE_PATH
        self.cluster_distance_meters = max(
            MIN_CLUSTER_DISTANCE_METERS,
            min(cluster_distance_meters, MAX_CLUSTER_DISTANCE_METERS),
        )

        logger.info(
            f"Initializing BenchClusterer with {self.cluster_distance_meters}m clustering distance"
        )

        # Ensure clustered_benches table exists
        self._create_clustering_tables()

    def _create_clustering_tables(self):
        """Create the clustered_benches table if it doesn't exist."""
        try:
            db = BenchDatabase(self.db_path)
            with db._get_connection() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS clustered_benches (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        center_lat REAL NOT NULL,
                        center_lng REAL NOT NULL,
                        bench_ids TEXT NOT NULL,  -- JSON array of bench IDs
                        best_bench_id INTEGER NOT NULL,
                        max_distance_meters REAL NOT NULL,
                        bench_count INTEGER NOT NULL,
                        avg_confidence REAL NOT NULL,
                        sources TEXT NOT NULL,  -- JSON array of sources
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (best_bench_id) REFERENCES benches (id)
                    )
                """)

                # Create spatial index on cluster centers
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_clustered_benches_location
                    ON clustered_benches(center_lat, center_lng)
                """)

                # Create index on best_bench_id for efficient lookups
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_clustered_benches_best_bench
                    ON clustered_benches(best_bench_id)
                """)

                conn.commit()
                logger.info("Clustered benches table and indexes created/verified")

        except Exception:
            logger.exception("Failed to create clustering tables")
            raise

    @staticmethod
    def calculate_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """
        Calculate the great circle distance between two points using Haversine formula.
        Returns distance in meters.
        """
        # Convert decimal degrees to radians
        lat1, lng1, lat2, lng2 = map(math.radians, [lat1, lng1, lat2, lng2])

        # Haversine formula
        dlat = lat2 - lat1
        dlng = lng2 - lng1
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
        )
        c = 2 * math.asin(math.sqrt(a))

        # Earth's radius in meters
        r = 6371000
        return c * r

    def _get_bench_data_for_clustering(
        self, min_confidence: float = 0.0
    ) -> list[BenchData]:
        """
        Get bench data suitable for clustering.

        Args:
            min_confidence: Minimum confidence threshold for benches to include

        Returns:
            List of BenchData objects ready for clustering
        """
        try:
            db = BenchDatabase(self.db_path)
            with db._get_connection() as conn:
                # Get benches with their best confidence scores
                query = """
                    SELECT
                        b.id, b.lat, b.lng, b.source, b.provider_id,
                        COUNT(DISTINCT i.id) as image_count,
                        COALESCE(rf_data.max_confidence, 0) as roboflow_confidence,
                        COALESCE(ul_data.max_confidence, 0) as ultralytics_confidence,
                        COALESCE(mp_data.max_confidence, 0) as mapillary_confidence,
                        CASE
                            WHEN COALESCE(rf_data.max_confidence, 0) >= COALESCE(ul_data.max_confidence, 0) AND COALESCE(rf_data.max_confidence, 0) >= COALESCE(mp_data.max_confidence, 0)
                            THEN COALESCE(rf_data.max_confidence, 0)
                            WHEN COALESCE(ul_data.max_confidence, 0) >= COALESCE(mp_data.max_confidence, 0)
                            THEN COALESCE(ul_data.max_confidence, 0)
                            ELSE COALESCE(mp_data.max_confidence, 0)
                        END as best_confidence
                    FROM benches b
                    LEFT JOIN images i ON b.id = i.bench_id AND i.capture_success = 1
                    LEFT JOIN (
                        SELECT image_id, MAX(max_confidence) as max_confidence
                        FROM detections
                        WHERE has_bench = 1
                        GROUP BY image_id
                    ) rf_data ON i.id = rf_data.image_id
                    LEFT JOIN (
                        SELECT image_id, MAX(max_confidence) as max_confidence
                        FROM ultralytics_detections
                        WHERE has_bench = 1
                        GROUP BY image_id
                    ) ul_data ON i.id = ul_data.image_id
                    LEFT JOIN (
                        SELECT image_id, MAX(max_confidence) as max_confidence
                        FROM detections
                        WHERE has_bench = 1 AND source = 'mapillary'
                        GROUP BY image_id
                    ) mp_data ON i.id = mp_data.image_id
                    GROUP BY b.id
                    HAVING best_confidence >= ?
                    ORDER BY best_confidence DESC
                """

                rows = conn.execute(query, [min_confidence]).fetchall()

                benches = []
                for row in rows:
                    bench = BenchData(
                        id=row["id"],
                        lat=row["lat"],
                        lng=row["lng"],
                        best_confidence=row["best_confidence"],
                        source=row["source"] or "osm",
                        provider_id=row["provider_id"] or str(row["id"]),
                        image_count=row["image_count"] or 0,
                    )
                    benches.append(bench)

                logger.info(
                    f"Retrieved {len(benches)} benches for clustering (min_confidence >= {min_confidence})"
                )
                return benches

        except Exception:
            logger.exception("Failed to get bench data for clustering")
            raise

    def _cluster_benches(self, benches: list[BenchData]) -> list[BenchCluster]:
        """
        Cluster benches based on distance using a simple greedy algorithm.

        Args:
            benches: List of BenchData to cluster

        Returns:
            List of BenchCluster objects
        """
        if not benches:
            return []

        clusters = []
        unclustered = benches.copy()
        cluster_id = 1

        logger.info(
            f"Starting clustering of {len(benches)} benches with {self.cluster_distance_meters}m threshold"
        )

        while unclustered:
            # Start a new cluster with the highest confidence unclustered bench
            seed_bench = unclustered[0]  # Already sorted by confidence DESC
            cluster_benches = [seed_bench]
            unclustered.remove(seed_bench)

            # Find all benches within clustering distance of the seed
            i = 0
            while i < len(unclustered):
                candidate = unclustered[i]

                # Check if candidate is close to any bench in the current cluster
                is_close = False
                for cluster_bench in cluster_benches:
                    distance = self.calculate_distance(
                        cluster_bench.lat,
                        cluster_bench.lng,
                        candidate.lat,
                        candidate.lng,
                    )
                    if distance <= self.cluster_distance_meters:
                        is_close = True
                        break

                if is_close:
                    cluster_benches.append(candidate)
                    unclustered.pop(i)
                    # Don't increment i since we removed an element
                else:
                    i += 1

            # Create the cluster
            if cluster_benches:
                cluster = self._create_cluster_from_benches(cluster_id, cluster_benches)
                clusters.append(cluster)
                cluster_id += 1

        logger.info(f"Created {len(clusters)} clusters from {len(benches)} benches")
        return clusters

    def _create_cluster_from_benches(
        self, cluster_id: int, benches: list[BenchData]
    ) -> BenchCluster:
        """
        Create a BenchCluster from a list of benches.

        Args:
            cluster_id: Unique identifier for the cluster
            benches: List of benches to include in the cluster

        Returns:
            BenchCluster object
        """
        if not benches:
            raise ValueError("Cannot create cluster from empty bench list")

        # Calculate cluster center (centroid)
        center_lat = sum(b.lat for b in benches) / len(benches)
        center_lng = sum(b.lng for b in benches) / len(benches)

        # Find the best bench (highest confidence)
        best_bench = max(benches, key=lambda b: b.best_confidence)

        # Calculate maximum distance from center
        max_distance = 0.0
        for bench in benches:
            distance = self.calculate_distance(
                center_lat, center_lng, bench.lat, bench.lng
            )
            max_distance = max(max_distance, distance)

        # Calculate average confidence
        avg_confidence = sum(b.best_confidence for b in benches) / len(benches)

        # Collect unique sources
        sources = {b.source for b in benches}

        return BenchCluster(
            id=cluster_id,
            center_lat=center_lat,
            center_lng=center_lng,
            bench_ids=[b.id for b in benches],
            best_bench_id=best_bench.id,
            max_distance_meters=max_distance,
            bench_count=len(benches),
            avg_confidence=avg_confidence,
            sources=sources,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    def _save_clusters_to_database(self, clusters: list[BenchCluster]):
        """
        Save clusters to the database, replacing existing clusters.

        Args:
            clusters: List of BenchCluster objects to save
        """
        try:
            db = BenchDatabase(self.db_path)
            with db._get_connection() as conn:
                # Clear existing clusters
                conn.execute("DELETE FROM clustered_benches")

                # Insert new clusters
                for cluster in clusters:
                    conn.execute(
                        """
                        INSERT INTO clustered_benches (
                            center_lat, center_lng, bench_ids, best_bench_id,
                            max_distance_meters, bench_count, avg_confidence, sources,
                            created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        [
                            cluster.center_lat,
                            cluster.center_lng,
                            json.dumps(cluster.bench_ids),
                            cluster.best_bench_id,
                            cluster.max_distance_meters,
                            cluster.bench_count,
                            cluster.avg_confidence,
                            json.dumps(list(cluster.sources)),
                            cluster.created_at,
                            cluster.updated_at,
                        ],
                    )

                conn.commit()
                logger.info(f"Saved {len(clusters)} clusters to database")

        except Exception:
            logger.exception("Failed to save clusters to database")
            raise

    def cluster_all_benches(self, min_confidence: float = 0.5) -> int:
        """
        Perform complete clustering of all benches in the database.

        Args:
            min_confidence: Minimum confidence threshold for benches to include

        Returns:
            Number of clusters created
        """
        logger.info(
            f"Starting complete bench clustering with min_confidence={min_confidence}"
        )

        try:
            # Get all benches suitable for clustering
            benches = self._get_bench_data_for_clustering(min_confidence)

            if not benches:
                logger.warning("No benches found for clustering")
                return 0

            # Cluster the benches
            clusters = self._cluster_benches(benches)

            # Save to database
            self._save_clusters_to_database(clusters)

            logger.info(
                f"Clustering complete: {len(clusters)} clusters created from {len(benches)} benches"
            )
            return len(clusters)

        except Exception:
            logger.exception("Failed to cluster all benches")
            raise

    def get_cluster_by_bench_id(self, bench_id: int) -> Optional[BenchCluster]:
        """
        Get the cluster that contains a specific bench.

        Args:
            bench_id: ID of the bench to find cluster for

        Returns:
            BenchCluster object if found, None otherwise
        """
        try:
            db = BenchDatabase(self.db_path)
            with db._get_connection() as conn:
                query = """
                    SELECT * FROM clustered_benches
                    WHERE bench_ids LIKE ?
                """

                # Search for the bench ID in the JSON array
                # Note: This is a simple search, could be optimized with JSON functions
                pattern = f"%{bench_id}%"
                row = conn.execute(query, [pattern]).fetchone()

                if row:
                    bench_ids = json.loads(row["bench_ids"])
                    if bench_id in bench_ids:  # Confirm exact match
                        sources = set(json.loads(row["sources"]))

                        return BenchCluster(
                            id=row["id"],
                            center_lat=row["center_lat"],
                            center_lng=row["center_lng"],
                            bench_ids=bench_ids,
                            best_bench_id=row["best_bench_id"],
                            max_distance_meters=row["max_distance_meters"],
                            bench_count=row["bench_count"],
                            avg_confidence=row["avg_confidence"],
                            sources=sources,
                            created_at=row["created_at"],
                            updated_at=row["updated_at"],
                        )

                return None

        except Exception:
            logger.exception(f"Failed to get cluster for bench {bench_id}")
            return None

    def get_all_clusters(self) -> list[BenchCluster]:
        """
        Get all clusters from the database.

        Returns:
            List of all BenchCluster objects
        """
        try:
            db = BenchDatabase(self.db_path)
            with db._get_connection() as conn:
                query = "SELECT * FROM clustered_benches ORDER BY avg_confidence DESC"
                rows = conn.execute(query).fetchall()

                clusters = []
                for row in rows:
                    sources = set(json.loads(row["sources"]))
                    bench_ids = json.loads(row["bench_ids"])

                    cluster = BenchCluster(
                        id=row["id"],
                        center_lat=row["center_lat"],
                        center_lng=row["center_lng"],
                        bench_ids=bench_ids,
                        best_bench_id=row["best_bench_id"],
                        max_distance_meters=row["max_distance_meters"],
                        bench_count=row["bench_count"],
                        avg_confidence=row["avg_confidence"],
                        sources=sources,
                        created_at=row["created_at"],
                        updated_at=row["updated_at"],
                    )
                    clusters.append(cluster)

                return clusters

        except Exception:
            logger.exception("Failed to get all clusters")
            raise

    def get_clustering_stats(self) -> dict[str, any]:
        """
        Get statistics about the current clustering.

        Returns:
            Dictionary with clustering statistics
        """
        try:
            db = BenchDatabase(self.db_path)
            with db._get_connection() as conn:
                # Get cluster statistics
                cluster_stats = conn.execute("""
                    SELECT
                        COUNT(*) as total_clusters,
                        AVG(bench_count) as avg_benches_per_cluster,
                        MAX(bench_count) as max_benches_per_cluster,
                        MIN(bench_count) as min_benches_per_cluster,
                        AVG(avg_confidence) as overall_avg_confidence,
                        AVG(max_distance_meters) as avg_cluster_radius
                    FROM clustered_benches
                """).fetchone()

                # Get total bench count
                total_benches = conn.execute(
                    "SELECT COUNT(*) as total FROM benches"
                ).fetchone()["total"]

                # Get clustered bench count
                clustered_benches_result = conn.execute("""
                    SELECT SUM(bench_count) as clustered_total
                    FROM clustered_benches
                """).fetchone()
                clustered_benches = clustered_benches_result["clustered_total"] or 0

                return {
                    "total_benches": total_benches,
                    "clustered_benches": clustered_benches,
                    "unclustered_benches": total_benches - clustered_benches,
                    "total_clusters": cluster_stats["total_clusters"] or 0,
                    "avg_benches_per_cluster": round(
                        cluster_stats["avg_benches_per_cluster"] or 0, 2
                    ),
                    "max_benches_per_cluster": cluster_stats["max_benches_per_cluster"]
                    or 0,
                    "min_benches_per_cluster": cluster_stats["min_benches_per_cluster"]
                    or 0,
                    "overall_avg_confidence": round(
                        cluster_stats["overall_avg_confidence"] or 0, 3
                    ),
                    "avg_cluster_radius_meters": round(
                        cluster_stats["avg_cluster_radius"] or 0, 2
                    ),
                    "clustering_distance_meters": self.cluster_distance_meters,
                }

        except Exception:
            logger.exception("Failed to get clustering stats")
            raise


def main():
    """CLI interface for clustering operations."""
    import argparse

    parser = argparse.ArgumentParser(description="Bench clustering management")
    parser.add_argument(
        "--distance",
        "-d",
        type=float,
        default=DEFAULT_CLUSTER_DISTANCE_METERS,
        help=f"Clustering distance in meters (default: {DEFAULT_CLUSTER_DISTANCE_METERS}m)",
    )
    parser.add_argument(
        "--min-confidence",
        "-c",
        type=float,
        default=0.5,
        help="Minimum confidence threshold for benches (default: 0.5)",
    )
    parser.add_argument(
        "--stats", action="store_true", help="Show clustering statistics only"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Set up logging
    level = logging.INFO if args.verbose else logging.WARNING
    logging.basicConfig(level=level, format="%(asctime)s - %(levelname)s - %(message)s")

    try:
        clusterer = BenchClusterer(cluster_distance_meters=args.distance)

        if args.stats:
            # Show statistics only
            stats = clusterer.get_clustering_stats()
            print("Bench Clustering Statistics:")
            print("=" * 30)
            for key, value in stats.items():
                print(f"{key.replace('_', ' ').title()}: {value}")
        else:
            # Perform clustering
            print(f"Starting clustering with {args.distance}m distance threshold...")
            cluster_count = clusterer.cluster_all_benches(
                min_confidence=args.min_confidence
            )
            print(f"✅ Clustering complete: {cluster_count} clusters created")

            # Show final statistics
            stats = clusterer.get_clustering_stats()
            print("\nFinal Statistics:")
            print("-" * 20)
            print(f"Total benches: {stats['total_benches']}")
            print(f"Clustered benches: {stats['clustered_benches']}")
            print(f"Total clusters: {stats['total_clusters']}")
            print(f"Average benches per cluster: {stats['avg_benches_per_cluster']}")

    except Exception:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
