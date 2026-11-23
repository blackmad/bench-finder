import { env } from "cloudflare:test";
import { createLocalJWKSet, exportJWK, generateKeyPair, type JWK, SignJWT } from "jose";
import { createApp, type Deps } from "../src/app";
import type { Env } from "../src/env";

export const PROJECT = "bench-finder-a45db";
export const ADMIN_UID = "admin-uid";

const pair = await generateKeyPair("RS256", { extractable: true });
const otherPair = await generateKeyPair("RS256", { extractable: true });
const pub: JWK = { ...(await exportJWK(pair.publicKey)), kid: "test-key", alg: "RS256", use: "sig" };
export const testJwks = createLocalJWKSet({ keys: [pub] });

interface TokenOpts {
  uid?: string;
  name?: string;
  iss?: string;
  aud?: string;
  /** seconds from now; negative = expired */
  expIn?: number;
  signWithOtherKey?: boolean;
  omitSub?: boolean;
}

export async function makeToken(o: TokenOpts = {}): Promise<string> {
  const now = Math.floor(Date.now() / 1000);
  const jwt = new SignJWT({ name: o.name ?? "Test User", auth_time: now - 10 })
    .setProtectedHeader({ alg: "RS256", kid: "test-key" })
    .setIssuer(o.iss ?? `https://securetoken.google.com/${PROJECT}`)
    .setAudience(o.aud ?? PROJECT)
    .setIssuedAt(now - 20)
    .setExpirationTime(now + (o.expIn ?? 3600));
  if (!o.omitSub) jwt.setSubject(o.uid ?? "user-1");
  return jwt.sign(o.signWithOtherKey ? otherPair.privateKey : pair.privateKey);
}

export const bearer = async (o?: TokenOpts) => ({ Authorization: `Bearer ${await makeToken(o)}` });

export function testEnv(overrides: Partial<Env> = {}): Env {
  return { ...(env as unknown as Env), ADMIN_UIDS: ADMIN_UID, ...overrides };
}

export function makeClient(deps: Deps = {}, envOverrides: Partial<Env> = {}) {
  const app = createApp({ jwks: testJwks, verifyTurnstile: async (t) => t === "good-token", ...deps });
  const e = testEnv(envOverrides);
  return {
    env: e,
    request: (path: string, init: RequestInit & { headers?: Record<string, string> } = {}) =>
      app.request(path, init, e),
    json: (method: string, path: string, body?: unknown, headers: Record<string, string> = {}) =>
      app.request(
        path,
        {
          method,
          headers: { "Content-Type": "application/json", ...headers },
          body: body === undefined ? undefined : JSON.stringify(body),
        },
        e,
      ),
  };
}

export async function resetDb() {
  for (const t of ["ratings", "user_status", "profiles", "hero_picks", "hero_suggestions", "view_suggestions", "comments", "bench_reports", "missing_bench_reports", "rate_limits"]) {
    await env.DB.prepare(`DELETE FROM ${t}`).run();
  }
}

export const PNG = new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 1, 2, 3, 4]);

/** The public half of the test signing key, as the JSON string AUTH_TEST_JWKS expects. */
export const testJwksJson = JSON.stringify({ keys: [pub] });
