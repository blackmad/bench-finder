#!/usr/bin/env python3
"""
Debug script to check what's in the database and why the query isn't returning results.
"""

from database import BenchDatabase


def debug_database():
    """Debug the database to understand what data exists."""
    print("🔍 Debugging database contents...")

    try:
        db = BenchDatabase()
        with db._get_connection() as conn:
            # Check table existence
            print("\n1. Checking table existence:")
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            for table in ["benches", "images", "detections", "ultralytics_detections"]:
                exists = table in tables
                print(f"   {table}: {'✓' if exists else '✗'}")

            # Check basic counts
            print("\n2. Basic table counts:")
            for table in ["benches", "images", "detections", "ultralytics_detections"]:
                if table in tables:
                    try:
                        count = conn.execute(
                            f"SELECT COUNT(*) FROM {table}"
                        ).fetchone()[0]
                        print(f"   {table}: {count} records")
                    except Exception as e:
                        print(f"   {table}: Error counting - {e}")

            # Check detection data specifically
            print("\n3. Detection data analysis:")

            # Regular detections
            try:
                cursor = conn.execute("""
                    SELECT COUNT(*) as total,
                           COUNT(CASE WHEN has_bench = 1 THEN 1 END) as with_benches,
                           MAX(max_confidence) as max_conf,
                           MIN(max_confidence) as min_conf
                    FROM detections
                """)
                row = cursor.fetchone()
                if row:
                    print(
                        f"   Roboflow detections: {row[0]} total, {row[1]} with benches"
                    )
                    print(f"   Roboflow confidence range: {row[3]} - {row[2]}")
            except Exception as e:
                print(f"   Roboflow detections: Error - {e}")

            # Ultralytics detections (if table exists)
            if "ultralytics_detections" in tables:
                try:
                    cursor = conn.execute("""
                        SELECT COUNT(*) as total,
                               COUNT(CASE WHEN has_bench = 1 THEN 1 END) as with_benches,
                               MAX(max_confidence) as max_conf,
                               MIN(max_confidence) as min_conf
                        FROM ultralytics_detections
                    """)
                    row = cursor.fetchone()
                    if row:
                        print(
                            f"   Ultralytics detections: {row[0]} total, {row[1]} with benches"
                        )
                        print(f"   Ultralytics confidence range: {row[3]} - {row[2]}")
                except Exception as e:
                    print(f"   Ultralytics detections: Error - {e}")

            # Test the original simple query
            print("\n4. Testing original simple query:")
            try:
                cursor = conn.execute("""
                    SELECT COUNT(*)
                    FROM benches b
                    JOIN images i ON b.id = i.bench_id
                    JOIN detections d ON i.id = d.image_id
                    WHERE d.has_bench = 1 AND d.max_confidence >= 0.8
                """)
                count = cursor.fetchone()[0]
                print(f"   Original query (confidence >= 0.8): {count} results")

                # Try with lower confidence
                cursor = conn.execute("""
                    SELECT COUNT(*)
                    FROM benches b
                    JOIN images i ON b.id = i.bench_id
                    JOIN detections d ON i.id = d.image_id
                    WHERE d.has_bench = 1 AND d.max_confidence >= 0.5
                """)
                count = cursor.fetchone()[0]
                print(f"   Original query (confidence >= 0.5): {count} results")

                # Try with any confidence
                cursor = conn.execute("""
                    SELECT COUNT(*)
                    FROM benches b
                    JOIN images i ON b.id = i.bench_id
                    JOIN detections d ON i.id = d.image_id
                    WHERE d.has_bench = 1
                """)
                count = cursor.fetchone()[0]
                print(f"   Original query (any confidence): {count} results")

            except Exception as e:
                print(f"   Original query error: {e}")

            # Test the new broken query
            print("\n5. Testing the new query:")
            try:
                cursor = conn.execute("""
                    SELECT COUNT(DISTINCT b.id)
                    FROM benches b
                    JOIN images i ON b.id = i.bench_id AND i.capture_success = 1
                    LEFT JOIN detections d ON i.id = d.image_id
                    LEFT JOIN ultralytics_detections ud ON i.id = ud.image_id
                    WHERE (d.has_bench = 1 AND d.max_confidence >= 0.8) OR
                          (ud.has_bench = 1 AND ud.max_confidence >= 0.8)
                """)
                count = cursor.fetchone()[0]
                print(f"   New query (confidence >= 0.8): {count} results")

                # Debug the individual parts
                cursor = conn.execute("""
                    SELECT COUNT(DISTINCT b.id)
                    FROM benches b
                    JOIN images i ON b.id = i.bench_id AND i.capture_success = 1
                    LEFT JOIN detections d ON i.id = d.image_id
                    WHERE d.has_bench = 1 AND d.max_confidence >= 0.8
                """)
                count = cursor.fetchone()[0]
                print(f"   New query (Roboflow only): {count} results")

                if "ultralytics_detections" in tables:
                    cursor = conn.execute("""
                        SELECT COUNT(DISTINCT b.id)
                        FROM benches b
                        JOIN images i ON b.id = i.bench_id AND i.capture_success = 1
                        LEFT JOIN ultralytics_detections ud ON i.id = ud.image_id
                        WHERE ud.has_bench = 1 AND ud.max_confidence >= 0.8
                    """)
                    count = cursor.fetchone()[0]
                    print(f"   New query (Ultralytics only): {count} results")

            except Exception as e:
                print(f"   New query error: {e}")

            # Check image success rates
            print("\n6. Image success analysis:")
            try:
                cursor = conn.execute("""
                    SELECT COUNT(*) as total,
                           COUNT(CASE WHEN capture_success = 1 THEN 1 END) as successful
                    FROM images
                """)
                row = cursor.fetchone()
                if row:
                    print(f"   Images: {row[1]}/{row[0]} successful captures")
            except Exception as e:
                print(f"   Image analysis error: {e}")

    except Exception as e:
        print(f"❌ Database error: {e}")


if __name__ == "__main__":
    debug_database()
