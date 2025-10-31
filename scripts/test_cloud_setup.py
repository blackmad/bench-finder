#!/usr/bin/env python3
"""
Test script to verify Supabase and Firebase setup.

This script checks:
1. Supabase database connection
2. Firebase Storage initialization
3. Database schema (tables exist)
4. Firebase Storage bucket access

Usage:
    python scripts/test_cloud_setup.py
"""

import os
import sys
from pathlib import Path


# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_supabase():
    """Test Supabase database connection."""
    print("=" * 60)
    print("Testing Supabase Database Connection")
    print("=" * 60)

    use_supabase = os.getenv("USE_SUPABASE", "false").lower() == "true"
    supabase_url = os.getenv("SUPABASE_DB_URL")

    if not use_supabase:
        print("⚠️  USE_SUPABASE not set to 'true', skipping Supabase test")
        return False

    if not supabase_url:
        print("❌ SUPABASE_DB_URL environment variable not set")
        return False

    try:
        from bench_finder.models.unified_models import BenchCandidate, Image, Search
        from bench_finder.services.database import BenchDatabase

        print(f"Connecting to: {supabase_url[:50]}...")
        db = BenchDatabase(db_url=supabase_url)

        # Test connection by querying tables
        with db.get_session() as session:
            search_count = session.query(Search).count()
            bench_count = session.query(BenchCandidate).count()
            image_count = session.query(Image).count()

        print("✓ Connected successfully!")
        print(f"  Searches: {search_count}")
        print(f"  Benches: {bench_count}")
        print(f"  Images: {image_count}")
        return True

    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False


def test_firebase():
    """Test Firebase Storage initialization."""
    print("\n" + "=" * 60)
    print("Testing Firebase Storage")
    print("=" * 60)

    backend = os.getenv("IMAGE_STORAGE_BACKEND", "local")
    bucket = os.getenv("FIREBASE_STORAGE_BUCKET")
    credentials = os.getenv("FIREBASE_CREDENTIALS_PATH")

    if backend != "firebase":
        print(
            f"⚠️  IMAGE_STORAGE_BACKEND is '{backend}', not 'firebase'. Skipping Firebase test."
        )
        return False

    if not bucket:
        print("❌ FIREBASE_STORAGE_BUCKET environment variable not set")
        return False

    try:
        from bench_finder.services.image_storage import FirebaseImageStorage

        print("Initializing Firebase Storage...")
        print(f"  Bucket: {bucket}")
        print(f"  Credentials: {credentials or 'Using default credentials'}")

        FirebaseImageStorage(
            bucket_name=bucket,
            credentials_path=credentials if credentials else None,
        )

        print("✓ Firebase Storage initialized successfully!")
        return True

    except ImportError as e:
        print(f"❌ Failed to import Firebase: {e}")
        print("   Install with: pip install firebase-admin")
        return False
    except Exception as e:
        print(f"❌ Initialization failed: {e}")
        print(
            "   Make sure FIREBASE_CREDENTIALS_PATH points to valid service account JSON"
        )
        return False


def test_local_fallback():
    """Test that local fallback still works."""
    print("\n" + "=" * 60)
    print("Testing Local Database (Fallback)")
    print("=" * 60)

    try:
        from bench_finder.services.database import BenchDatabase

        db = BenchDatabase()  # Should use local SQLite
        with db.get_session() as session:
            from bench_finder.models.unified_models import Search

            count = session.query(Search).count()

        print("✓ Local database connection works!")
        print(f"  Searches in local DB: {count}")
        return True

    except Exception as e:
        print(f"❌ Local database test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("\n" + "🔍 Cloud Setup Verification" + "\n")

    results = []

    # Test local fallback first
    results.append(("Local Database", test_local_fallback()))

    # Test Supabase if configured
    results.append(("Supabase", test_supabase()))

    # Test Firebase if configured
    results.append(("Firebase Storage", test_firebase()))

    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)

    for name, passed in results:
        status = "✓ PASS" if passed else "⚠️  SKIP/Fail"
        print(f"{status}: {name}")

    all_passed = all(passed for _, passed in results if results)
    print(
        "\n"
        + (
            "✅ All configured services are working!"
            if all_passed
            else "⚠️  Some services need configuration"
        )
    )

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
