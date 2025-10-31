# Setup Guide: Supabase & Firebase

This guide walks you through setting up Supabase (database) and Firebase Storage (images) for production hosting.

## Prerequisites

- A GitHub account (for Vercel deployment)
- A credit card (both services have free tiers, but may require card for verification)

## Part 1: Supabase Setup (Database)

### Step 1: Create Supabase Project

1. Go to [https://supabase.com](https://supabase.com)
2. Sign up or log in
3. Click "New Project"
4. Fill in:
   - **Organization**: Create or select one
   - **Name**: `bench-finder` (or your preferred name)
   - **Database Password**: Create a strong password (SAVE THIS!)
   - **Region**: Choose closest to your users
   - **Pricing Plan**: Free tier is fine to start

5. Click "Create new project"
6. Wait 2-3 minutes for project to initialize

### Step 2: Get Database Connection String

1. In your Supabase project dashboard, go to **Settings** → **Database**
2. Scroll down to **Connection string**
3. Select **Connection pooling** (recommended for serverless/Vercel)
4. Copy the connection string. It will look like:
   ```
   postgresql://postgres.xxxxx:[YOUR-PASSWORD]@aws-0-us-west-1.pooler.supabase.com:6543/postgres
   ```

5. **Important**: Replace `[YOUR-PASSWORD]` with the password you created in Step 1
6. Save this connection string securely - you'll need it for environment variables

### Step 3: Test Connection (Optional)

You can test the connection locally:

```bash
# Set environment variable temporarily
export SUPABASE_DB_URL="postgresql://postgres.xxxxx:YOUR-PASSWORD@aws-0-us-west-1.pooler.supabase.com:6543/postgres"
export USE_SUPABASE=true

# Test connection
python -c "from bench_finder.services.database import BenchDatabase; db = BenchDatabase(); print('✓ Connected to Supabase!')"
```

## Part 2: Firebase Setup (Image Storage)

### Step 1: Create Firebase Project

1. Go to [https://console.firebase.google.com](https://console.firebase.google.com)
2. Click "Add project" or "Create a project"
3. Fill in:
   - **Project name**: `bench-finder` (or your preferred name)
   - **Google Analytics**: Optional (can disable for now)
4. Click "Create project"
5. Wait for project to be created

### Step 2: Enable Firebase Storage

1. In Firebase Console, click **Storage** in the left sidebar
2. Click "Get started"
3. Choose **Start in production mode** (we'll set up rules next)
4. Select a location (choose same region as Supabase if possible)
5. Click "Done"

### Step 3: Configure Storage Rules

1. In Firebase Storage, go to the **Rules** tab
2. Replace the rules with:

```json
rules_version = '2';
service firebase.storage {
  match /b/{bucket}/o {
    match /images/{filename} {
      // Allow public read access
      allow read: if true;
      // Only allow authenticated writes (or use Firebase Admin SDK)
      allow write: if request.auth != null || request.resource.size < 5 * 1024 * 1024;
    }
  }
}
```

3. Click "Publish"

### Step 4: Create Storage Bucket (if not auto-created)

1. If no bucket exists, Firebase will create one automatically
2. Note the bucket name (usually `your-project-id.appspot.com`)

### Step 5: Create Service Account Key

1. In Firebase Console, go to **Project Settings** (gear icon)
2. Go to **Service accounts** tab
3. Click **Generate new private key**
4. A JSON file will download - **SAVE THIS SECURELY**!
5. This file contains your credentials for the sync script

### Step 6: Test Firebase Connection (Optional)

```bash
# Set environment variables
export FIREBASE_STORAGE_BUCKET="your-project-id.appspot.com"
export FIREBASE_CREDENTIALS_PATH="/path/to/downloaded/serviceAccountKey.json"
export IMAGE_STORAGE_BACKEND=firebase

# Test connection
python -c "from bench_finder.services.image_storage import FirebaseImageStorage; storage = FirebaseImageStorage('$FIREBASE_STORAGE_BUCKET', '$FIREBASE_CREDENTIALS_PATH'); print('✓ Firebase initialized!')"
```

## Part 3: Migrate Your Data

### Step 1: Backup Your Current Database

```bash
# Backup SQLite database
cp data/benches.db data/benches.db.backup.$(date +%Y%m%d)
```

### Step 2: Run Database Migration

```bash
# Dry run first (recommended)
python tools/migrate_to_supabase.py \
    --sqlite-path data/benches.db \
    --supabase-url "$SUPABASE_DB_URL" \
    --dry-run

# Actual migration (remove --dry-run)
python tools/migrate_to_supabase.py \
    --sqlite-path data/benches.db \
    --supabase-url "$SUPABASE_DB_URL"
```

### Step 3: Sync Images to Firebase

```bash
# Dry run first (recommended)
python tools/sync_images_to_firebase.py \
    --images-dir images \
    --firebase-bucket "your-project-id.appspot.com" \
    --firebase-credentials "/path/to/serviceAccountKey.json" \
    --dry-run

# Actual sync (remove --dry-run)
python tools/sync_images_to_firebase.py \
    --images-dir images \
    --firebase-bucket "your-project-id.appspot.com" \
    --firebase-credentials "/path/to/serviceAccountKey.json"
```

**Note**: Image sync may take a while depending on number of images. You can use `--resume` flag if interrupted.

## Part 4: Configure Vercel

### Step 1: Connect Repository to Vercel

1. Go to [https://vercel.com](https://vercel.com)
2. Import your GitHub repository
3. Configure project settings (usually auto-detected)

### Step 2: Set Environment Variables

In Vercel project settings → **Environment Variables**, add:

**Database:**
```
USE_SUPABASE=true
SUPABASE_DB_URL=postgresql://postgres.xxxxx:YOUR-PASSWORD@aws-0-us-west-1.pooler.supabase.com:6543/postgres
```

**Images:**
```
IMAGE_STORAGE_BACKEND=firebase
FIREBASE_STORAGE_BUCKET=your-project-id.appspot.com
FIREBASE_STORAGE_PREFIX=images
```

**Firebase Credentials:**
You have two options:

**Option A**: Upload service account file and reference it
- Upload `serviceAccountKey.json` to Vercel (using their file system or as an environment variable)
- Set `FIREBASE_CREDENTIALS_PATH=/path/to/serviceAccountKey.json`

**Option B**: Use environment variable (recommended)
- Copy the entire contents of `serviceAccountKey.json`
- In Vercel, create a new environment variable:
  - Name: `GOOGLE_APPLICATION_CREDENTIALS_JSON`
  - Value: Paste the entire JSON content
- The code will read from this environment variable

**Other Required Variables:**
```
GOOGLE_MAPS_API_KEY=your_key
ROBOFLOW_API_KEY=your_key (if using)
ULTRALYTICS_API_KEY=your_key (if using)
```

### Step 3: Deploy

1. Push your code to GitHub
2. Vercel will automatically deploy
3. Check deployment logs for any errors
4. Test your deployed site!

## Verification Checklist

After deployment, verify:

- [ ] Database queries work (check API endpoints)
- [ ] Images load from Firebase Storage
- [ ] New images upload correctly
- [ ] No errors in Vercel function logs
- [ ] Site loads in browser

## Troubleshooting

### Database Connection Issues

- Verify `SUPABASE_DB_URL` includes the correct password
- Make sure you're using the **Connection pooling** URL (port 6543) not direct connection
- Check Supabase dashboard for connection limits

### Firebase Storage Issues

- Verify bucket name is correct
- Check storage rules allow public read access
- Ensure service account key has proper permissions
- Check Firebase Console → Storage for uploaded files

### Image Sync Issues

- Use `--resume` flag if sync was interrupted
- Check Firebase Storage console for uploaded files
- Verify database `firebase_url` fields are populated

## Cost Estimation

### Supabase Free Tier
- 500MB database
- 2GB bandwidth/month
- Should be sufficient for initial deployment

### Firebase Free Tier
- 5GB storage
- 1GB downloads/day
- Perfect for image hosting

### Vercel Free Tier
- 100GB bandwidth/month
- 100GB-hours compute
- Should be sufficient for moderate traffic

All three services have generous free tiers that should work well for starting out!

## Support

If you run into issues:
1. Check the deployment logs in Vercel
2. Test locally with production environment variables
3. Verify all environment variables are set correctly
4. Check service dashboards (Supabase/Firebase) for errors
