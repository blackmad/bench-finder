/**
 * Firebase is only needed for sign-in, so it is imported on demand and never
 * lands in the entry chunk. Sign-in itself arrives with task 5.5.
 */
export async function loadFirebaseAuth() {
  const apiKey = import.meta.env.VITE_FIREBASE_API_KEY
  if (!apiKey) throw new Error("Firebase is not configured")
  const [{ initializeApp, getApps }, { getAuth }] = await Promise.all([
    import("firebase/app"),
    import("firebase/auth"),
  ])
  const app =
    getApps()[0] ??
    initializeApp({
      apiKey,
      authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
      projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
    })
  return getAuth(app)
}
