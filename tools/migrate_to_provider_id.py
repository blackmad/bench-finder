#!/usr/bin/env python3
"""
Migration script to update bench schema:
- Rename osm_id to provider_id (as string)
- Remove osm_type column
- Populate provider_id from OSM data and external_id for Mapillary
"""

import os
import sqlite3
import sys


DATABASE_PATH = "data/benches.db"


def migrate_database():
    """Apply the migration to update bench schema."""
    if not os.path.exists(DATABASE_PATH):
        print(f"Database {DATABASE_PATH} not found!")
        return False

    print(f"Starting migration of {DATABASE_PATH}...")

    # Create backup
    backup_path = f"{DATABASE_PATH}.backup_provider_id_migration"
    print(f"Creating backup at {backup_path}...")

    try:
        # Copy database file for backup
        import shutil

        shutil.copy2(DATABASE_PATH, backup_path)
        print("Backup created successfully")
    except Exception as e:
        print(f"Failed to create backup: {e}")
        return False

    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # Begin transaction
        cursor.execute("BEGIN")

        print("Step 1: Creating new benches table with provider_id...")

        # Create new benches table with updated schema
        cursor.execute("""
            CREATE TABLE benches_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                search_id INTEGER,
                provider_id TEXT,
                lat REAL NOT NULL,
                lng REAL NOT NULL,
                tags TEXT,
                source TEXT DEFAULT 'osm',
                external_id TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (search_id) REFERENCES searches (id)
            )
        """)

        print("Step 2: Migrating data from old table...")

        # Copy data from old table to new table
        # For OSM benches: provider_id = str(osm_id) + "_" + osm_type
        # For Mapillary benches: provider_id = external_id
        cursor.execute("""
            INSERT INTO benches_new (id, search_id, provider_id, lat, lng, tags, source, external_id, created_at)
            SELECT
                id,
                search_id,
                CASE
                    WHEN source = 'mapillary' THEN external_id
                    WHEN osm_id IS NOT NULL AND osm_type IS NOT NULL THEN CAST(osm_id AS TEXT) || '_' || osm_type
                    WHEN osm_id IS NOT NULL THEN CAST(osm_id AS TEXT)
                    ELSE 'unknown_' || CAST(id AS TEXT)
                END as provider_id,
                lat,
                lng,
                tags,
                COALESCE(source, 'osm') as source,
                external_id,
                created_at
            FROM benches
        """)

        rows_migrated = cursor.rowcount
        print(f"Migrated {rows_migrated} bench records")

        print("Step 3: Dropping old table and renaming new table...")

        # Drop old table and rename new table
        cursor.execute("DROP TABLE benches")
        cursor.execute("ALTER TABLE benches_new RENAME TO benches")

        print("Step 4: Creating indexes...")

        # Recreate indexes
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_benches_search_id ON benches(search_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_benches_provider_id ON benches(provider_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_benches_source ON benches(source)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_benches_external_id ON benches(external_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_benches_location ON benches(lat, lng)"
        )

        print("Step 5: Verifying migration...")

        # Verify the migration
        cursor.execute("SELECT COUNT(*) as count FROM benches")
        total_count = cursor.fetchone()["count"]

        cursor.execute(
            "SELECT COUNT(*) as count FROM benches WHERE provider_id IS NOT NULL"
        )
        provider_id_count = cursor.fetchone()["count"]

        cursor.execute(
            "SELECT COUNT(*) as count FROM benches WHERE source = 'mapillary'"
        )
        mapillary_count = cursor.fetchone()["count"]

        cursor.execute("SELECT COUNT(*) as count FROM benches WHERE source = 'osm'")
        osm_count = cursor.fetchone()["count"]

        print("Migration verification:")
        print(f"  Total benches: {total_count}")
        print(f"  With provider_id: {provider_id_count}")
        print(f"  OSM benches: {osm_count}")
        print(f"  Mapillary benches: {mapillary_count}")

        if provider_id_count != total_count:
            raise Exception(
                f"Migration failed: {provider_id_count} provider_id records vs {total_count} total records"
            )

        # Sample some records to verify
        print("\nSample migrated records:")
        cursor.execute("SELECT provider_id, source, external_id FROM benches LIMIT 5")
        for row in cursor.fetchall():
            print(
                f"  provider_id: {row['provider_id']}, source: {row['source']}, external_id: {row['external_id']}"
            )

        # Commit transaction
        cursor.execute("COMMIT")
        print("\nMigration completed successfully!")

        return True

    except Exception as e:
        print(f"Migration failed: {e}")
        cursor.execute("ROLLBACK")
        return False

    finally:
        conn.close()


def main():
    """Run the migration."""
    print("Bench Database Migration: osm_id -> provider_id")
    print("=" * 50)

    if migrate_database():
        print("\n✅ Migration completed successfully!")
        print(f"Backup saved as: {DATABASE_PATH}.backup_provider_id_migration")
    else:
        print("\n❌ Migration failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
