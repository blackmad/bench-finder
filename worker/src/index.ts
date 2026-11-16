import * as Sentry from "@sentry/cloudflare";
import { createApp } from "./app";
import type { Env } from "./env";

export type { AppType, Deps } from "./app";
export type { Env } from "./env";

const app = createApp();

// Errors go to Sentry (bench-finder-worker) when SENTRY_DSN is set; no request
// bodies, cookies or user data, and no tracing.
export default Sentry.withSentry(
  (env: Env) => ({
    dsn: env.SENTRY_DSN,
    enabled: Boolean(env.SENTRY_DSN),
    sendDefaultPii: false,
    tracesSampleRate: 0,
  }),
  { fetch: app.fetch } satisfies ExportedHandler<Env>,
);
