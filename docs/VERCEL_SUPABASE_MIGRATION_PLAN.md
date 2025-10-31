# Vercel/Supabase Migration Plan

This document outlines the plan for hosting the bench_finder application on Vercel with Supabase database and Firebase Storage for images.

## Overview

The migration involves:
1. **Database**: Migrate from SQLite to Supabase (PostgreSQL)
2. **Images**: Host images on Firebase Storage (5GB free tier)
3. **Deployment**: Deploy FastAPI backend on Vercel serverless functions
4. **Configuration**: Environment-based switching between local and cloud services

## Current Architecture

### Database
- **Current**: SQLite (`data/benches.db`)
- **ORM**: SQLModel/SQLAlchemy
- **Models**: Located in `bench_finder/models/unified_models.py`
- **Connection**: `BenchDatabase` class in `bench_finder/services/database.py`

### Images
- **Current**: Local filesystem (`images/` directory)
- **Serving**: FastAPI StaticFiles mounted at `/images`
- **Storage**: Image paths stored in `Image` model with `filepath` and `filename` fields
- **Endpoints**: `/images/{filename}` endpoint serves images

## Target Architecture

### Database
- **Target**: Supabase PostgreSQL database
- **Connection**: Use Supabase Postgres connection string
- **Compatibility**: SQLModel/SQLAlchemy works with PostgreSQL
- **Migration**: One-time data export from SQLite to Supabase

### Images
- **Target**: Firebase Storage buckets
- **Access**: Public URLs served via Firebase CDN
- **Storage**: Maintain local filenames but store Firebase URLs in database
- **Fallback**: Support local images for development

## Implementation Plan

### Phase 1: Database Abstraction Layer

#### 1.1 Update Database Connection Logic
**File**: `bench_finder/models/unified_models.py`

- Add PostgreSQL connection string support alongside SQLite
- Modify `create_database_engine()` to detect database type from connection string
- Support both `sqlite:///path/to/db.db` and `postgresql://user:pass@host/db` formats

**Configuration Changes**:
- Add `DATABASE_URL` environment variable
- Keep `DATABASE_PATH` for backward compatibility (SQLite)
- Priority: `DATABASE_URL` > `DATABASE_PATH`

#### 1.2 Update BenchDatabase Class
**File**: `bench_finder/services/database.py`

- Modify `__init__` to accept `database_url` parameter
- Read from `DATABASE_URL` or `DATABASE_PATH` environment variables
- Ensure SQLAlchemy handles both SQLite and PostgreSQL correctly

#### 1.3 Configuration Updates
**File**: `bench_finder/config.py`

```python
# Database settings
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/benches.db")  # For SQLite
DATABASE_URL = os.getenv("DATABASE_URL")  # For Supabase PostgreSQL

# Determine which database to use
USE_SUPABASE = os.getenv("USE_SUPABASE", "false").lower() == "true"
SUPABASE_DB_URL = os.getenv("SUPABASE_DB_URL")  # Full PostgreSQL connection string

# Fallback logic
if USE_SUPABASE and SUPABASE_DB_URL:
    DATABASE_URL = SUPABASE_DB_URL
elif DATABASE_URL:
    pass  # Use provided DATABASE_URL
else:
    DATABASE_URL = f"sqlite:///{DATABASE_PATH}"
```

### Phase 2: Image Service Abstraction

#### 2.1 Create Image Storage Service
**New File**: `bench_finder/services/image_storage.py`

Create an abstract base class for image storage:

```python
from abc import ABC, abstractmethod

class ImageStorageService(ABC):
    @abstractmethod
    async def upload_image(self, file_path: str, filename: str) -> str:
        """Upload image and return public URL"""

    @abstractmethod
    async def get_image_url(self, filename: str) -> str:
        """Get public URL for an image"""

    @abstractmethod
    async def delete_image(self, filename: str) -> bool:
        """Delete an image"""
```

Implementations:
1. `LocalImageStorage` - Current filesystem-based storage
2. `FirebaseImageStorage` - Firebase Storage integration

#### 2.2 Firebase Storage Integration
**Dependencies**: `firebase-admin` package

- Initialize Firebase Admin SDK
- Create storage bucket reference
- Implement upload/download/delete methods
- Generate signed URLs for public access

#### 2.3 Update Image Model
**File**: `bench_finder/models/unified_models.py`

Add optional field to `Image` model:
- `firebase_url: str | None` - Firebase Storage URL
- Keep `filepath` for backward compatibility
- Prefer `firebase_url` when available

#### 2.4 Update Image Serving Endpoint
**File**: `api/fastapi_server.py`

Modify `/images/{filename}` endpoint:
- Check if image has Firebase URL → redirect or proxy
- Fallback to local file serving if no Firebase URL
- Support both local and cloud images seamlessly

### Phase 3: Migration Scripts

#### 3.1 Database Migration Script
**New File**: `tools/migrate_to_supabase.py`

Features:
- Export all data from SQLite database
- Create tables in Supabase (via SQLModel)
- Insert data in batches to Supabase
- Handle foreign key relationships correctly
- Progress tracking and error handling
- Dry-run mode for testing

**Usage**:
```bash
python tools/migrate_to_supabase.py \
    --sqlite-path data/benches.db \
    --supabase-url $SUPABASE_DB_URL \
    [--dry-run]
```

#### 3.2 Image Sync Script
**New File**: `tools/sync_images_to_firebase.py`

Features:
- Scan local `images/` directory
- Upload each image to Firebase Storage
- Update database records with Firebase URLs
- Skip already-uploaded images (check by filename)
- Progress tracking with resume capability
- Handle missing files gracefully

**Usage**:
```bash
python tools/sync_images_to_firebase.py \
    --images-dir images \
    --firebase-credentials path/to/serviceAccount.json \
    --bucket-name bench-finder-images \
    [--resume]
```

### Phase 4: Configuration Management

#### 4.1 Environment Variables
Create `.env.example` with all required variables:

```bash
# Database Configuration
USE_SUPABASE=false  # Set to true for production
DATABASE_PATH=data/benches.db  # For SQLite (local)
SUPABASE_DB_URL=postgresql://user:pass@host/db  # For Supabase (production)

# Image Storage Configuration
IMAGE_STORAGE_BACKEND=local  # 'local' or 'firebase'
FIREBASE_STORAGE_BUCKET=bench-finder-images.appspot.com
FIREBASE_CREDENTIALS_PATH=path/to/serviceAccount.json

# Existing variables...
GOOGLE_MAPS_API_KEY=...
ROBOFLOW_API_KEY=...
```

#### 4.2 Vercel Configuration
**File**: `vercel.json`

Update to include environment variables and proper routing:

```json
{
    "version": 2,
    "builds": [
        {
            "src": "api/index.py",
            "use": "@vercel/python"
        }
    ],
    "routes": [
        {
            "src": "/api/(.*)",
            "dest": "/api/index.py"
        },
        {
            "src": "/images/(.*)",
            "dest": "/api/index.py"
        },
        {
            "src": "/(.*)",
            "dest": "/api/index.py"
        }
    ],
    "env": {
        "PYTHONPATH": ".",
        "USE_SUPABASE": "true",
        "IMAGE_STORAGE_BACKEND": "firebase"
    }
}
```

### Phase 5: Firebase Setup

#### 5.1 Firebase Project Setup
1. Create Firebase project
2. Enable Firebase Storage
3. Create storage bucket: `bench-finder-images`
4. Set bucket rules for public read access
5. Generate service account JSON key

#### 5.2 Firebase Storage Rules
```json
{
  "rules": {
    "images": {
      ".read": true,
      ".write": "request.auth != null || request.resource.size < 5 * 1024 * 1024"
    }
  }
}
```

### Phase 6: Supabase Setup

#### 6.1 Supabase Project Setup
1. Create Supabase project
2. Get database connection string from Settings → Database
3. Note connection pooler URL for serverless (recommended for Vercel)

#### 6.2 Database Schema
- Run SQLModel `metadata.create_all()` against Supabase
- Or use migration script to create tables
- Ensure all indexes are created

#### 6.3 Connection Pooling
- Use Supabase connection pooler for Vercel (serverless-friendly)
- Connection string format: `postgresql://user:pass@host/db?pgbouncer=true`

## Implementation Checklist

### Database
- [ ] Update `create_database_engine()` to support PostgreSQL
- [ ] Add `DATABASE_URL` and `USE_SUPABASE` configuration
- [ ] Test BenchDatabase with Supabase connection
- [ ] Create database migration script
- [ ] Test migration script with sample data
- [ ] Document Supabase setup process

### Images
- [ ] Create `ImageStorageService` abstract base class
- [ ] Implement `LocalImageStorage` service
- [ ] Implement `FirebaseImageStorage` service
- [ ] Add `firebase_url` field to Image model
- [ ] Update image serving endpoint to handle both sources
- [ ] Create image sync script
- [ ] Test image upload/download
- [ ] Document Firebase setup process

### Configuration
- [ ] Add environment variables to `config.py`
- [ ] Update `.env.example`
- [ ] Configure Vercel environment variables
- [ ] Test local development with both backends
- [ ] Test production deployment on Vercel

### Migration
- [ ] Test database migration script
- [ ] Test image sync script
- [ ] Create backup before migration
- [ ] Run migration in staging environment
- [ ] Verify data integrity
- [ ] Run production migration

## Testing Strategy

### Local Testing
1. Test SQLite (current setup) - should work as before
2. Test Supabase connection locally
3. Test Firebase image upload locally
4. Test switching between backends via environment variables

### Staging Testing
1. Deploy to Vercel staging environment
2. Migrate sample data to Supabase
3. Upload sample images to Firebase
4. Test all endpoints
5. Verify performance

### Production Deployment
1. Create Supabase production database
2. Run database migration
3. Run image sync
4. Deploy to Vercel production
5. Monitor for issues

## Rollback Plan

If issues occur:
1. **Database**: Keep SQLite backup, can switch back via `USE_SUPABASE=false`
2. **Images**: Images remain in local filesystem, can serve locally
3. **Deployment**: Can revert Vercel deployment to previous version

## Cost Considerations

### Supabase
- Free tier: 500MB database, 1GB bandwidth/month
- Paid plans start at $25/month for production

### Firebase Storage
- Free tier: 5GB storage, 1GB/day download
- Perfect for initial deployment

### Vercel
- Free tier: 100GB bandwidth/month
- Serverless functions: 100GB-hours compute
- Should be sufficient for moderate traffic

## Next Steps

1. Start with Phase 1 (Database Abstraction) - can be done incrementally
2. Test Supabase connection locally before full migration
3. Implement image service abstraction in parallel
4. Create migration scripts and test thoroughly
5. Deploy to staging first, then production

## Dependencies to Add

```toml
# Add to pyproject.toml dependencies
firebase-admin>=6.0.0
psycopg2-binary>=2.9.0  # PostgreSQL driver for SQLAlchemy
```

## Questions to Resolve

1. Should we keep SQLite for local development or fully migrate?
   - **Recommendation**: Keep SQLite as default for local dev, use Supabase for production

2. How to handle missing images during migration?
   - **Recommendation**: Log missing files, continue migration, allow manual fixes

3. Should we support both image sources simultaneously?
   - **Recommendation**: Yes, prefer Firebase URL if available, fallback to local

4. Connection pooling strategy for Vercel?
   - **Recommendation**: Use Supabase connection pooler (pgbouncer) for serverless
