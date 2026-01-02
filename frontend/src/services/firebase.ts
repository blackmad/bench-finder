import { initializeApp } from "firebase/app"
import {
  type Auth,
  FacebookAuthProvider,
  GithubAuthProvider,
  GoogleAuthProvider,
  getAuth,
  OAuthProvider,
} from "firebase/auth"

// Firebase configuration from environment variables
const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || "",
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || "",
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || "",
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || "",
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || "",
  appId: import.meta.env.VITE_FIREBASE_APP_ID || "",
}

// Check if Firebase is configured
const isConfigured =
  firebaseConfig.apiKey && firebaseConfig.authDomain && firebaseConfig.projectId

if (!isConfigured) {
  console.warn(
    "Firebase credentials not configured. Authentication features will be disabled."
  )
}

// Initialize Firebase app
const app = isConfigured ? initializeApp(firebaseConfig) : null

// Initialize Auth
export const auth: Auth | null = app ? getAuth(app) : null

// Auth providers
export const googleProvider = new GoogleAuthProvider()
export const githubProvider = new GithubAuthProvider()
export const appleProvider = new OAuthProvider("apple.com")
export const facebookProvider = new FacebookAuthProvider()

// Provider mapping for easy access
export const authProviders = {
  google: googleProvider,
  github: githubProvider,
  apple: appleProvider,
  facebook: facebookProvider,
} as const

export type AuthProviderType = keyof typeof authProviders
