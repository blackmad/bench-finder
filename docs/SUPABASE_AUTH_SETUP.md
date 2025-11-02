# How to Get Supabase Authentication Credentials

This guide explains where to find the Supabase credentials needed for user authentication features.

## Step 1: Create or Access Your Supabase Project

1. Go to [https://supabase.com](https://supabase.com)
2. Sign up or log in to your account
3. If you don't have a project yet, click **"New Project"** and create one
4. Wait for the project to initialize (usually takes 1-2 minutes)

## Step 2: Get Your Supabase URL and API Keys

1. In your Supabase project dashboard, go to **Settings** (gear icon in the left sidebar)
2. Click on **API** in the settings menu
3. You'll see a section called **Project API keys** with the following information:

### Finding the Values:

**SUPABASE_URL** (and `VITE_SUPABASE_URL` for frontend):
- Look for the **Project URL** field
- It will look like: `https://xxxxxxxxxxxxx.supabase.co`
- Copy this entire URL

**SUPABASE_ANON_KEY** (and `VITE_SUPABASE_ANON_KEY` for frontend):
- Look for the **anon** `public` key
- It's a long JWT token that starts with `eyJ...`
- Click the **👁️ Reveal** button if it's hidden
- Copy the entire key

**SUPABASE_SERVICE_ROLE_KEY** (optional, for backend):
- Look for the **service_role** `secret` key
- ⚠️ **WARNING**: This key should **NEVER** be exposed in frontend code
- Only use this in secure backend environments
- Copy the entire key

## Step 3: Set Environment Variables

### For Local Development

Create or update your `.env` file in the project root:

```bash
# Backend environment variables
SUPABASE_URL=https://xxxxxxxxxxxxx.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# Frontend environment variables (Vite requires VITE_ prefix)
VITE_SUPABASE_URL=https://xxxxxxxxxxxxx.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### For Production (Vercel)

1. Go to your Vercel project dashboard
2. Navigate to **Settings** → **Environment Variables**
3. Add each variable:
   - `SUPABASE_URL` → Your Project URL
   - `SUPABASE_ANON_KEY` → Your anon public key
   - `VITE_SUPABASE_URL` → Your Project URL (same as above)
   - `VITE_SUPABASE_ANON_KEY` → Your anon public key (same as above)

**Note**: Both `SUPABASE_URL` and `VITE_SUPABASE_URL` will have the same value, but they need to be set separately because:
- `SUPABASE_URL` is used by the backend (FastAPI)
- `VITE_SUPABASE_URL` is used by the frontend (React/Vite)

## Important Notes

1. **anon key vs service_role key**:
   - The `anon` key is safe to use in frontend code (it has Row Level Security policies applied)
   - The `service_role` key bypasses all security - only use in backend/server-side code
   - For this project, you only need the `anon` key

2. **Security**:
   - Never commit your `.env` file to git (it should be in `.gitignore`)
   - The `anon` key is designed to be public, but still keep it secure
   - Never expose the `service_role` key publicly

3. **Enable Social Authentication Providers**:
   - Go to **Authentication** → **Providers** in your Supabase dashboard
   - Enable the providers you want to support:
     - **Google**: Click "Google" → Toggle "Enable Google provider" → Add your Google OAuth credentials
     - **GitHub**: Click "GitHub" → Toggle "Enable GitHub provider" → Add your GitHub OAuth app credentials
     - **Apple** or **Facebook**: Enable as needed
   - For each provider, you'll need to:
     1. Create an OAuth app in the provider's developer console
     2. Get the Client ID and Client Secret
     3. Add the redirect URL: `https://your-project-ref.supabase.co/auth/v1/callback`
     4. Enter these in Supabase's provider settings

## Testing Your Setup

After setting the environment variables, restart your development server:

```bash
# Backend
uvicorn api.fastapi_server:app --reload

# Frontend
cd frontend && npm run dev
```

You should now see:
- Login button in the mobile map page (top right)
- Social login options (Google, GitHub) when clicking login
- Ability to sign in with social providers
- User authentication working in the app

## Troubleshooting

**"Supabase credentials not configured" warning:**
- Check that you've set both `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY`
- Make sure there are no extra spaces or quotes in your `.env` file
- Restart your development server after adding variables

**Authentication not working:**
- Verify the URL and key are correct
- Check the browser console for errors
- Make sure email authentication is enabled in Supabase dashboard
- Check that your Supabase project is not paused (free tier projects pause after inactivity)
