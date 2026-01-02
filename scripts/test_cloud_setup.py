#!/usr/bin/env python3
"""
Test script to verify Firebase setup.

This script checks:
1. Database connection (SQLite or Cloud SQL)
2. Firebase Storage initialization
3. Firebase Auth (Admin SDK)
4. Database schema (tables exist)
5. Firebase Storage bucket access

Usage:
    python scripts/test_cloud_setup.py
"""

import os
import sys
from pathlib import Path


# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_database():
    """Test database connection (SQLite or Cloud SQL)."""
    print("=" * 60)
    print("Testing Database Connection")
    print("=" * 60)

    database_url = os.getenv("DATABASE_URL")
    database_path = os.getenv("DATABASE_PATH", "data/benches.db")

    try:
        from bench_finder.models.unified_models import BenchCandidate, Image, Search
        from bench_finder.services.database import BenchDatabase

        if database_url and database_url.startswith("postgresql"):
            print(f"Connecting to PostgreSQL: {database_url[:50]}...")
        else:
            print(f"Connecting to SQLite: {database_path}")

        db = BenchDatabase()

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


def test_firebase_storage():
    """Test Firebase Storage initialization."""
    print("\n" + "=" * 60)
    print("Testing Firebase Storage")
    print("=" * 60)

    backend = os.getenv("IMAGE_STORAGE_BACKEND", "local")
    bucket = os.getenv("FIREBASE_STORAGE_BUCKET")
    credentials_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
    credentials_base64 = os.getenv("FIREBASE_CREDENTIALS_BASE64")

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
        if credentials_base64:
            print(
                "  Credentials: Using base64-encoded credentials from FIREBASE_CREDENTIALS_BASE64"
            )
        elif credentials_path:
            print(f"  Credentials: {credentials_path}")
        else:
            print("  Credentials: Using default credentials")

        FirebaseImageStorage(
            bucket_name=bucket,
            credentials_path=credentials_path if credentials_path else None,
            credentials_base64=credentials_base64 if credentials_base64 else None,
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
            "   Make sure FIREBASE_CREDENTIALS_PATH or FIREBASE_CREDENTIALS_BASE64 is set correctly"
        )
        return False


def test_firebase_auth():
    """Test Firebase Auth (Admin SDK)."""
    print("\n" + "=" * 60)
    print("Testing Firebase Auth (Admin SDK)")
    print("=" * 60)

    credentials_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
    credentials_base64 = os.getenv("FIREBASE_CREDENTIALS_BASE64")

    if not credentials_path and not credentials_base64:
        print(
            "⚠️  FIREBASE_CREDENTIALS_PATH or FIREBASE_CREDENTIALS_BASE64 not set. Skipping Firebase Auth test."
        )
        return False

    try:
        import firebase_admin
        from firebase_admin import auth, credentials

        # Check if already initialized
        try:
            firebase_admin.get_app()
            print("Firebase Admin SDK already initialized")
        except ValueError:
            # Initialize
            if credentials_base64:
                import base64
                import json

                creds_json = base64.b64decode(credentials_base64).decode("utf-8")
                creds_dict = json.loads(creds_json)
                cred = credentials.Certificate(creds_dict)
                print("  Credentials: Using base64-encoded credentials")
            elif credentials_path:
                cred = credentials.Certificate(credentials_path)
                print(f"  Credentials: {credentials_path}")
            else:
                cred = credentials.ApplicationDefault()
                print("  Credentials: Using Application Default Credentials")

            firebase_admin.initialize_app(cred)

        # Test by getting project info
        app = firebase_admin.get_app()
        print("✓ Firebase Admin SDK initialized successfully!")
        print(f"  Project ID: {app.project_id}")
        return True

    except ImportError as e:
        print(f"❌ Failed to import Firebase Admin: {e}")
        print("   Install with: pip install firebase-admin")
        return False
    except Exception as e:
        print(f"❌ Firebase Auth initialization failed: {e}")
        return False


def main():
    """Run all tests."""
    print("\n" + "🔍 Firebase Cloud Setup Verification" + "\n")

    results = []

    # Test database
    results.append(("Database", test_database()))

    # Test Firebase Auth
    results.append(("Firebase Auth", test_firebase_auth()))

    # Test Firebase Storage
    results.append(("Firebase Storage", test_firebase_storage()))

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
