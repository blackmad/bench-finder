import type { Env } from "./env";

/** The action every Turnstile widget in the frontend renders with (report dialogs, photo uploads). */
export const TURNSTILE_ACTION = "report";

export type TurnstileVerifier = (
  token: string,
  ip: string,
  env: Env,
  action: string,
) => Promise<boolean>;

const SITEVERIFY = "https://challenges.cloudflare.com/turnstile/v0/siteverify";

/**
 * Hostnames a token may come from: `TURNSTILE_HOSTNAMES` (comma-separated, e.g. "localhost"
 * in `.dev.vars`) or else the hosts in `ALLOWED_ORIGINS`. Never list localhost in production.
 */
export function expectedHostnames(env: Env): string[] {
  const raw = env.TURNSTILE_HOSTNAMES ?? env.ALLOWED_ORIGINS ?? "";
  return raw
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean)
    .map((s) => {
      try {
        return new URL(s.includes("://") ? s : `https://${s}`).hostname;
      } catch {
        return s;
      }
    });
}

export const verifyTurnstile: TurnstileVerifier = async (token, ip, env, action) => {
  if (!env.TURNSTILE_SECRET || !token) return false;
  const body = new URLSearchParams({
    secret: env.TURNSTILE_SECRET,
    response: token,
    idempotency_key: crypto.randomUUID(),
  });
  if (ip && ip !== "unknown") body.set("remoteip", ip);
  try {
    const res = await fetch(SITEVERIFY, { method: "POST", body });
    if (!res.ok) return false;
    const json = (await res.json()) as { success?: boolean; action?: string; hostname?: string };
    return (
      json.success === true &&
      json.action === action &&
      typeof json.hostname === "string" &&
      expectedHostnames(env).includes(json.hostname)
    );
  } catch {
    return false;
  }
};
