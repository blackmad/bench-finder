# Quick Start: Cloud Deployment

Quick reference for deploying to Vercel with Supabase + Firebase.

## 1. Install Dependencies ✅

```bash
uv sync
```

Already done! ✅

## 2. Set Up Accounts

### Supabase (Database)
- Go to [supabase.com](https://supabase.com) → Create project
- Settings → Database → Copy connection pooling URL
- Replace `[YOUR-PASSWORD]` with your database password

### Firebase (Images)
- Go to [console.firebase.google.com](https://console.firebase.google.com) → Create project
- Enable Storage
- Project Settings → Service Accounts → Download JSON key

## 3. Test Locally (Optional)

```bash
# Set environment variables
export USE_SUPABASE=true
export SUPABASE_DB_URL="postgresql://..."
export IMAGE_STORAGE_BACKEND=firebase
export FIREBASE_STORAGE_BUCKET="your-project.appspot.com"
export FIREBASE_CREDENTIALS_PATH="/path/to/serviceAccountKey.json"

# Test connections
python scripts/test_cloud_setup.py
```

## 4. Migrate Data

```bash
# Database migration (dry-run first!)
python tools/migrate_to_supabase.py \
    --sqlite-path data/benches.db \
    --supabase-url "$SUPABASE_DB_URL" \
    --dry-run

# Actual migration
python tools/migrate_to_supabase.py \
    --sqlite-path data/benches.db \
    --supabase-url "$SUPABASE_DB_URL"

# Image sync (dry-run first!)
python tools/sync_images_to_firebase.py \
    --images-dir images \
    --firebase-bucket "your-project.appspot.com" \
    --firebase-credentials "/path/to/serviceAccountKey.json" \
    --dry-run

# Actual sync
python tools/sync_images_to_firebase.py \
    --images-dir images \
    --firebase-bucket "your-project.appspot.com" \
    --firebase-credentials "/path/to/serviceAccountKey.json"
```

## 5. Deploy to Vercel

### Set Environment Variables in Vercel Dashboard

**Required:**
```
USE_SUPABASE=true
SUPABASE_DB_URL=postgresql://...
IMAGE_STORAGE_BACKEND=firebase
FIREBASE_STORAGE_BUCKET=your-project.appspot.com
GOOGLE_MAPS_API_KEY=your_key
```

**Firebase Credentials** (choose one):
- **Option A**: Upload serviceAccountKey.json and set `FIREBASE_CREDENTIALS_PATH`
- **Option B**: Set `GOOGLE_APPLICATION_CREDENTIALS_JSON` with full JSON content

**Optional:**
```
ROBOFLOW_API_KEY=your_key
ULTRALYTICS_API_KEY=your_key
```

### Deploy

```bash
git add .
git commit -m "Add cloud deployment support"
git push
```

Vercel will auto-deploy!

## Troubleshooting

**Connection issues?**
```bash
# Test locally with production env vars
python scripts/test_cloud_setup.py
```

**Migration issues?**
- Always use `--dry-run` first
- Check Supabase dashboard for connection limits
- Verify database password is correct

**Image sync issues?**
- Use `--resume` if interrupted
- Check Firebase Storage console
- Verify bucket name is correct

## Full Documentation

See [SETUP_SUPABASE_FIREBASE.md](./SETUP_SUPABASE_FIREBASE.md) for detailed instructions.
