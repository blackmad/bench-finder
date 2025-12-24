# Firebase Authentication Setup

This guide explains how to configure Firebase Authentication for the bench_finder application.

## Step 1: Firebase Console Setup

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Select your project (or create one)
3. Navigate to **Authentication** → **Sign-in method**

## Step 2: Enable OAuth Providers

Enable the providers you want to support:

### Google
1. Click "Google" → Toggle "Enable"
2. Select a support email
3. Save

### GitHub
1. Click "GitHub" → Toggle "Enable"
2. Get Client ID and Secret from [GitHub Developer Settings](https://github.com/settings/developers)
3. Add the callback URL shown in Firebase to your GitHub app
4. Enter credentials in Firebase and Save

### Apple (optional)
1. Click "Apple" → Toggle "Enable"
2. Follow Apple's setup for Sign in with Apple

## Step 3: Get Firebase Config

1. Go to **Project Settings** (gear icon)
2. Under "Your apps", click the web app (or create one)
3. Copy the Firebase config object

## Step 4: Set Environment Variables

### Backend (.env)
```bash
# Path to service account JSON (download from Project Settings → Service accounts)
FIREBASE_CREDENTIALS_PATH=path/to/firebase_creds.json

# Or use base64-encoded credentials (for serverless)
# FIREBASE_CREDENTIALS_BASE64=base64_encoded_json
```

### Frontend (Vite)
Add to your `.env` file:
```bash
VITE_FIREBASE_API_KEY=your_api_key
VITE_FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=your-project-id
VITE_FIREBASE_STORAGE_BUCKET=your-project.appspot.com
VITE_FIREBASE_MESSAGING_SENDER_ID=your_sender_id
VITE_FIREBASE_APP_ID=your_app_id
```

### Production (Vercel)
Add the same variables in Vercel Dashboard → Settings → Environment Variables.

## Step 5: Test Your Setup

```bash
# Backend
python scripts/test_cloud_setup.py

# Frontend
cd frontend && npm run dev
```

## Troubleshooting

**"Firebase credentials not configured" warning:**
- Ensure `FIREBASE_CREDENTIALS_PATH` or `FIREBASE_CREDENTIALS_BASE64` is set
- Restart the development server

**Frontend auth not working:**
- Check browser console for errors
- Verify all `VITE_FIREBASE_*` variables are set
- Ensure OAuth providers are enabled in Firebase Console
