import { createLocalJWKSet, createRemoteJWKSet, type JWTVerifyGetKey, jwtVerify } from "jose";
import { DEFAULT_FIREBASE_PROJECT_ID, type Env } from "./env";

export const GOOGLE_JWKS_URL =
  "https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com";

export interface AuthUser {
  uid: string;
  name: string | null;
}

export type TokenVerifier = (token: string) => Promise<AuthUser>;

/**
 * Build a Firebase ID-token verifier. The key source is injectable so tests can
 * supply a locally generated key set (`jose.createLocalJWKSet`).
 */
export function createVerifier(opts: {
  projectId: string;
  jwks: JWTVerifyGetKey;
}): TokenVerifier {
  return async (token) => {
    const { payload } = await jwtVerify(token, opts.jwks, {
      issuer: `https://securetoken.google.com/${opts.projectId}`,
      audience: opts.projectId,
      algorithms: ["RS256"],
      requiredClaims: ["exp", "sub"],
    });
    const sub = payload.sub;
    if (typeof sub !== "string" || sub.length === 0 || sub.length > 128) {
      throw new Error("invalid sub");
    }
    // Firebase: auth_time must be in the past.
    const authTime = payload.auth_time;
    if (typeof authTime === "number" && authTime > Math.floor(Date.now() / 1000) + 60) {
      throw new Error("auth_time in the future");
    }
    const name = typeof payload.name === "string" ? payload.name.slice(0, 80) : null;
    return { uid: sub, name };
  };
}

// createRemoteJWKSet caches keys (honouring Cache-Control) across requests within an isolate.
let remoteJwks: JWTVerifyGetKey | undefined;
export function googleJwks(): JWTVerifyGetKey {
  remoteJwks ??= createRemoteJWKSet(new URL(GOOGLE_JWKS_URL), {
    cooldownDuration: 30_000,
  });
  return remoteJwks;
}

export function verifierFromEnv(env: Env, jwks: JWTVerifyGetKey = googleJwks()): TokenVerifier {
  return createVerifier({
    projectId: env.FIREBASE_PROJECT_ID || DEFAULT_FIREBASE_PROJECT_ID,
    jwks,
  });
}

/**
 * Local-development only: when `AUTH_TEST_JWKS` (a JSON JWKS string) is set, tokens are verified
 * against it instead of Google's keys. Unset by default; never set it in production.
 */
export function testJwksFromEnv(env: Env): JWTVerifyGetKey | undefined {
  if (!env.AUTH_TEST_JWKS) return undefined;
  return createLocalJWKSet(JSON.parse(env.AUTH_TEST_JWKS));
}
