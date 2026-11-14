import { zValidator } from "@hono/zod-validator";
import { type Context, Hono } from "hono";
import { cors } from "hono/cors";
import { HTTPException } from "hono/http-exception";
import type { JWTVerifyGetKey } from "jose";
import { z } from "zod";
import { type AuthUser, googleJwks, testJwksFromEnv, verifierFromEnv } from "./auth";
import { csv, type Env } from "./env";
import { hit, num } from "./rate-limit";
import { type TurnstileVerifier, verifyTurnstile } from "./turnstile";

/** Injectable dependencies (tests replace these). */
export interface Deps {
  jwks?: JWTVerifyGetKey;
  verifyTurnstile?: TurnstileVerifier;
}

type C = Context<{ Bindings: Env }>;

const DEV_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"];
const MAX_UPLOAD_BYTES = 5 * 1024 * 1024;
const PHOTO_KEY_RE = /^reports\/[0-9a-f-]{36}\.(jpg|png|webp)$/;

const benchId = z.coerce.number().int().positive().max(2_147_483_647);
const idParam = z.object({ id: benchId });
const commentIdParam = z.object({ id: z.coerce.number().int().positive() });
const kindParam = z.object({ kind: z.enum(["bench", "missing"]), id: z.coerce.number().int().positive() });
const photoKey = z.string().regex(PHOTO_KEY_RE).optional();
const note = z.string().trim().max(1000).optional();
const turnstileToken = z.string().max(2048).optional();

const validationHook = (
  result: { success: boolean; error?: { issues: { path: PropertyKey[]; message: string }[] } },
  c: Context,
) => {
  if (!result.success) {
    const issue = result.error?.issues[0];
    const where = issue?.path.map(String).join(".");
    return c.json({ error: `Invalid input${where ? ` (${where})` : ""}: ${issue?.message ?? ""}` }, 400);
  }
};

const now = () => new Date().toISOString();
const ipOf = (c: C) => c.req.header("CF-Connecting-IP") ?? "unknown";

function sniffImage(b: Uint8Array): { type: string; ext: string } | null {
  if (b[0] === 0xff && b[1] === 0xd8 && b[2] === 0xff) return { type: "image/jpeg", ext: "jpg" };
  if (b[0] === 0x89 && b[1] === 0x50 && b[2] === 0x4e && b[3] === 0x47) {
    return { type: "image/png", ext: "png" };
  }
  const tag = (o: number) => String.fromCharCode(b[o], b[o + 1], b[o + 2], b[o + 3]);
  if (b.length > 12 && tag(0) === "RIFF" && tag(8) === "WEBP") return { type: "image/webp", ext: "webp" };
  return null;
}

export function createApp(deps: Deps = {}) {
  const checkTurnstile = deps.verifyTurnstile ?? verifyTurnstile;

  /** Returns the signed-in user, null when no Authorization header; throws 401 on a bad token. */
  async function optionalUser(c: C): Promise<AuthUser | null> {
    const header = c.req.header("Authorization");
    if (!header) return null;
    const m = /^Bearer (.+)$/i.exec(header);
    if (!m) throw new HTTPException(401, { message: "Malformed Authorization header" });
    try {
      return await verifierFromEnv(c.env, deps.jwks ?? testJwksFromEnv(c.env) ?? googleJwks())(m[1]);
    } catch {
      throw new HTTPException(401, { message: "Invalid or expired token" });
    }
  }

  async function requireUser(c: C): Promise<AuthUser> {
    const user = await optionalUser(c);
    if (!user) throw new HTTPException(401, { message: "Sign in required" });
    return user;
  }

  async function requireAdmin(c: C): Promise<AuthUser> {
    const user = await requireUser(c);
    if (!csv(c.env.ADMIN_UIDS).includes(user.uid)) {
      throw new HTTPException(403, { message: "Admin only" });
    }
    return user;
  }

  /** Per-IP rate limit, then Turnstile unless the caller is signed in. */
  async function guardPublicWrite(
    c: C,
    bucket: string,
    limit: number,
    token: string | undefined,
  ): Promise<AuthUser | null> {
    const ip = ipOf(c);
    const { allowed } = await hit(c.env.DB, bucket, ip, limit);
    if (!allowed) {
      c.header("Retry-After", "3600");
      throw new HTTPException(429, { message: "Too many requests, try again later" });
    }
    const user = await optionalUser(c);
    if (!user && !(await checkTurnstile(token ?? "", ip, c.env))) {
      throw new HTTPException(403, { message: "Turnstile verification failed" });
    }
    return user;
  }

  async function assertPhotoExists(c: C, key: string | undefined) {
    if (key && !(await c.env.UPLOADS.head(key))) {
      throw new HTTPException(400, { message: "Unknown photo key" });
    }
  }

  const app = new Hono<{ Bindings: Env }>()
    .use("/api/*", async (c, next) => {
      const allowed = [...DEV_ORIGINS, ...csv(c.env.ALLOWED_ORIGINS)];
      return cors({
        origin: (origin) => (allowed.includes(origin) ? origin : null),
        allowHeaders: ["Authorization", "Content-Type", "X-Turnstile-Token"],
        allowMethods: ["GET", "PUT", "POST", "DELETE", "OPTIONS"],
        maxAge: 86400,
      })(c, next);
    })
    .onError((err, c) => {
      if (err instanceof HTTPException) return c.json({ error: err.message }, err.status);
      console.error(err);
      return c.json({ error: "Internal error" }, 500);
    })
    .notFound((c) => c.json({ error: "Not found" }, 404))

    .get("/api/health", (c) => c.json({ ok: true }))

    // ---- Social ----------------------------------------------------------------
    .get("/api/bench/:id/social", zValidator("param", idParam, validationHook), async (c) => {
      const { id } = c.req.valid("param");
      const user = await optionalUser(c);
      const uid = user?.uid ?? null;
      const [summary, comments, mine, status] = await c.env.DB.batch([
        c.env.DB.prepare("SELECT COUNT(*) AS count, AVG(rating) AS average FROM ratings WHERE bench_id = ?1").bind(id),
        c.env.DB
          .prepare(
            `SELECT id, display_name, body, created_at, user_id FROM comments
             WHERE bench_id = ?1 AND deleted_at IS NULL AND state IN ('visible','flagged')
             ORDER BY created_at DESC, id DESC LIMIT 200`,
          )
          .bind(id),
        c.env.DB.prepare("SELECT rating FROM ratings WHERE bench_id = ?1 AND user_id = ?2").bind(id, uid),
        c.env.DB.prepare("SELECT visited, favorite FROM user_status WHERE bench_id = ?1 AND user_id = ?2").bind(id, uid),
      ]);
      const s = (summary.results[0] ?? {}) as { count?: number; average?: number | null };
      const myRating = (mine.results[0] as { rating: number } | undefined)?.rating ?? null;
      const st = status.results[0] as { visited: number; favorite: number } | undefined;
      return c.json({
        benchId: id,
        ratings: {
          count: s.count ?? 0,
          average: s.average == null ? null : Math.round(s.average * 100) / 100,
        },
        comments: (
          comments.results as {
            id: number;
            display_name: string;
            body: string;
            created_at: string;
            user_id: string;
          }[]
        ).map((r) => ({
          id: r.id,
          displayName: r.display_name,
          body: r.body,
          createdAt: r.created_at,
          mine: uid !== null && r.user_id === uid,
        })),
        me: user
          ? { rating: myRating, visited: st?.visited === 1, favorite: st?.favorite === 1 }
          : null,
      });
    })

    .put(
      "/api/bench/:id/rating",
      zValidator("param", idParam, validationHook),
      zValidator("json", z.object({ rating: z.number().int().min(1).max(5) }), validationHook),
      async (c) => {
        const user = await requireUser(c);
        const { id } = c.req.valid("param");
        const { rating } = c.req.valid("json");
        const t = now();
        await c.env.DB
          .prepare(
            `INSERT INTO ratings (bench_id, user_id, rating, created_at, updated_at) VALUES (?1, ?2, ?3, ?4, ?4)
             ON CONFLICT(bench_id, user_id) DO UPDATE SET rating = excluded.rating, updated_at = excluded.updated_at`,
          )
          .bind(id, user.uid, rating, t)
          .run();
        return c.json({ benchId: id, rating });
      },
    )

    .put(
      "/api/bench/:id/status",
      zValidator("param", idParam, validationHook),
      zValidator(
        "json",
        z
          .object({ visited: z.boolean().optional(), favorite: z.boolean().optional() })
          .refine((v) => v.visited !== undefined || v.favorite !== undefined, "visited or favorite required"),
        validationHook,
      ),
      async (c) => {
        const user = await requireUser(c);
        const { id } = c.req.valid("param");
        const { visited, favorite } = c.req.valid("json");
        const t = now();
        // Partial update: omitted fields keep their current value.
        const row = await c.env.DB
          .prepare(
            `INSERT INTO user_status (bench_id, user_id, visited, favorite, created_at, updated_at)
             VALUES (?1, ?2, COALESCE(?3, 0), COALESCE(?4, 0), ?5, ?5)
             ON CONFLICT(bench_id, user_id) DO UPDATE SET
               visited = COALESCE(?3, visited), favorite = COALESCE(?4, favorite), updated_at = excluded.updated_at
             RETURNING visited, favorite`,
          )
          .bind(id, user.uid, visited === undefined ? null : +visited, favorite === undefined ? null : +favorite, t)
          .first<{ visited: number; favorite: number }>();
        return c.json({ benchId: id, visited: row?.visited === 1, favorite: row?.favorite === 1 });
      },
    )

    .post(
      "/api/bench/:id/comments",
      zValidator("param", idParam, validationHook),
      zValidator("json", z.object({ body: z.string().trim().min(1).max(2000) }), validationHook),
      async (c) => {
        const user = await requireUser(c);
        const { id } = c.req.valid("param");
        const { body } = c.req.valid("json");
        const { allowed } = await hit(c.env.DB, "comment", user.uid, num(c.env.RATE_LIMIT_COMMENTS_PER_HOUR, 20));
        if (!allowed) throw new HTTPException(429, { message: "Too many comments, try again later" });
        const t = now();
        const displayName = user.name?.trim() || "Anonymous";
        const row = await c.env.DB
          .prepare(
            `INSERT INTO comments (bench_id, user_id, display_name, body, created_at) VALUES (?1, ?2, ?3, ?4, ?5)
             RETURNING id`,
          )
          .bind(id, user.uid, displayName, body, t)
          .first<{ id: number }>();
        return c.json({ id: row?.id ?? 0, displayName, body, createdAt: t, mine: true }, 201);
      },
    )

    .delete("/api/comments/:id", zValidator("param", commentIdParam, validationHook), async (c) => {
      const user = await requireUser(c);
      const { id } = c.req.valid("param");
      const row = await c.env.DB
        .prepare("SELECT user_id FROM comments WHERE id = ?1 AND deleted_at IS NULL")
        .bind(id)
        .first<{ user_id: string }>();
      if (!row) throw new HTTPException(404, { message: "Comment not found" });
      if (row.user_id !== user.uid) throw new HTTPException(403, { message: "Not your comment" });
      await c.env.DB.prepare("UPDATE comments SET deleted_at = ?2 WHERE id = ?1").bind(id, now()).run();
      return c.json({ id, deleted: true });
    })

    .post("/api/comments/:id/flag", zValidator("param", commentIdParam, validationHook), async (c) => {
      await requireUser(c);
      const { id } = c.req.valid("param");
      const r = await c.env.DB
        .prepare("UPDATE comments SET state = 'flagged' WHERE id = ?1 AND deleted_at IS NULL AND state = 'visible'")
        .bind(id)
        .run();
      return c.json({ id, flagged: (r.meta.changes ?? 0) > 0 });
    })

    .get("/api/me", async (c) => {
      const user = await requireUser(c);
      const [ratings, statuses] = await c.env.DB.batch([
        c.env.DB.prepare("SELECT bench_id, rating, updated_at FROM ratings WHERE user_id = ?1 ORDER BY updated_at DESC").bind(user.uid),
        c.env.DB
          .prepare(
            "SELECT bench_id, visited, favorite FROM user_status WHERE user_id = ?1 AND (visited = 1 OR favorite = 1) ORDER BY updated_at DESC",
          )
          .bind(user.uid),
      ]);
      const st = statuses.results as { bench_id: number; visited: number; favorite: number }[];
      return c.json({
        uid: user.uid,
        isAdmin: csv(c.env.ADMIN_UIDS).includes(user.uid),
        ratings: (ratings.results as { bench_id: number; rating: number }[]).map((r) => ({
          benchId: r.bench_id,
          rating: r.rating,
        })),
        visited: st.filter((r) => r.visited === 1).map((r) => r.bench_id),
        favorites: st.filter((r) => r.favorite === 1).map((r) => r.bench_id),
      });
    })

    // ---- Reports & uploads -------------------------------------------------------
    .post(
      "/api/reports/bench",
      zValidator(
        "json",
        z.object({
          benchId,
          reason: z.enum(["not_a_bench", "wrong_location", "wrong_facing", "bad_image", "other"]),
          note,
          photoKey,
          turnstileToken,
        }),
        validationHook,
      ),
      async (c) => {
        const b = c.req.valid("json");
        const user = await guardPublicWrite(
          c,
          "report",
          num(c.env.RATE_LIMIT_REPORTS_PER_HOUR, 10),
          b.turnstileToken ?? c.req.header("X-Turnstile-Token"),
        );
        await assertPhotoExists(c, b.photoKey);
        const row = await c.env.DB
          .prepare(
            `INSERT INTO bench_reports (bench_id, reason, note, photo_key, user_id, created_at)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6) RETURNING id`,
          )
          .bind(b.benchId, b.reason, b.note || null, b.photoKey ?? null, user?.uid ?? null, now())
          .first<{ id: number }>();
        return c.json({ id: row?.id ?? 0, status: "pending" as const }, 201);
      },
    )

    .post(
      "/api/reports/missing",
      zValidator(
        "json",
        z.object({
          lat: z.number().min(-90).max(90),
          lng: z.number().min(-180).max(180),
          accuracyMeters: z.number().min(0).max(100_000).optional(),
          note,
          photoKey,
          turnstileToken,
        }),
        validationHook,
      ),
      async (c) => {
        const b = c.req.valid("json");
        const user = await guardPublicWrite(
          c,
          "report",
          num(c.env.RATE_LIMIT_REPORTS_PER_HOUR, 10),
          b.turnstileToken ?? c.req.header("X-Turnstile-Token"),
        );
        await assertPhotoExists(c, b.photoKey);
        const row = await c.env.DB
          .prepare(
            `INSERT INTO missing_bench_reports (lat, lng, accuracy_meters, note, photo_key, user_id, created_at)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7) RETURNING id`,
          )
          .bind(b.lat, b.lng, b.accuracyMeters ?? null, b.note || null, b.photoKey ?? null, user?.uid ?? null, now())
          .first<{ id: number }>();
        return c.json({ id: row?.id ?? 0, status: "pending" as const }, 201);
      },
    )

    // Raw image body (Content-Type image/jpeg|png|webp, max 5 MB). Anonymous callers send the
    // Turnstile token in the X-Turnstile-Token header. Returns a key to attach to a report.
    .post("/api/uploads", async (c) => {
      const user = await guardPublicWrite(
        c,
        "upload",
        num(c.env.RATE_LIMIT_UPLOADS_PER_HOUR, 10),
        c.req.header("X-Turnstile-Token"),
      );
      const declared = Number(c.req.header("Content-Length") ?? "0");
      if (declared > MAX_UPLOAD_BYTES) throw new HTTPException(413, { message: "Image too large (max 5 MB)" });
      const bytes = new Uint8Array(await c.req.arrayBuffer());
      if (bytes.length === 0) throw new HTTPException(400, { message: "Empty body" });
      if (bytes.length > MAX_UPLOAD_BYTES) throw new HTTPException(413, { message: "Image too large (max 5 MB)" });
      const sniffed = sniffImage(bytes);
      const declaredType = (c.req.header("Content-Type") ?? "").split(";")[0].trim().toLowerCase();
      if (!sniffed || sniffed.type !== declaredType) {
        throw new HTTPException(415, { message: "Only JPEG, PNG or WebP images are accepted" });
      }
      const key = `reports/${crypto.randomUUID()}.${sniffed.ext}`;
      await c.env.UPLOADS.put(key, bytes, {
        httpMetadata: { contentType: sniffed.type },
        customMetadata: { uploader: user?.uid ?? "anonymous" },
      });
      return c.json({ key, size: bytes.length, contentType: sniffed.type }, 201);
    })

    // ---- Admin (uid allowlist) -----------------------------------------------------
    .get(
      "/api/admin/reports",
      zValidator(
        "query",
        z.object({ status: z.enum(["pending", "resolved", "dismissed"]).default("pending") }),
        validationHook,
      ),
      async (c) => {
        await requireAdmin(c);
        const { status } = c.req.valid("query");
        const [bench, missing] = await c.env.DB.batch([
          c.env.DB.prepare("SELECT * FROM bench_reports WHERE status = ?1 ORDER BY created_at LIMIT 200").bind(status),
          c.env.DB.prepare("SELECT * FROM missing_bench_reports WHERE status = ?1 ORDER BY created_at LIMIT 200").bind(status),
        ]);
        return c.json({ bench: bench.results, missing: missing.results });
      },
    )

    .post(
      "/api/admin/reports/:kind/:id/:action",
      zValidator(
        "param",
        kindParam.extend({ action: z.enum(["resolve", "dismiss"]) }),
        validationHook,
      ),
      async (c) => {
        const admin = await requireAdmin(c);
        const { kind, id, action } = c.req.valid("param");
        // Body is optional ({ adminNotes? }); parsed after the admin check.
        const parsed = z
          .object({ adminNotes: z.string().trim().max(1000).optional() })
          .safeParse(await c.req.json().catch(() => ({})));
        if (!parsed.success) throw new HTTPException(400, { message: "Invalid adminNotes" });
        const { adminNotes } = parsed.data;
        const table = kind === "bench" ? "bench_reports" : "missing_bench_reports";
        const status = action === "resolve" ? "resolved" : "dismissed";
        const r = await c.env.DB
          .prepare(
            `UPDATE ${table} SET status = ?2, admin_notes = COALESCE(?3, admin_notes), resolved_at = ?4, resolved_by = ?5 WHERE id = ?1`,
          )
          .bind(id, status, adminNotes ?? null, now(), admin.uid)
          .run();
        if (!r.meta.changes) throw new HTTPException(404, { message: "Report not found" });
        return c.json({ kind, id, status });
      },
    )

    .get(
      "/api/admin/comments",
      zValidator(
        "query",
        z.object({ state: z.enum(["visible", "flagged", "hidden"]).default("flagged") }),
        validationHook,
      ),
      async (c) => {
        await requireAdmin(c);
        const { state } = c.req.valid("query");
        const rows = await c.env.DB
          .prepare("SELECT * FROM comments WHERE state = ?1 AND deleted_at IS NULL ORDER BY created_at LIMIT 200")
          .bind(state)
          .all();
        return c.json({ comments: rows.results });
      },
    )

    .post(
      "/api/admin/comments/:id/:action",
      zValidator("param", commentIdParam.extend({ action: z.enum(["hide", "approve"]) }), validationHook),
      async (c) => {
        const admin = await requireAdmin(c);
        const { id, action } = c.req.valid("param");
        const state = action === "hide" ? "hidden" : "visible";
        const r = await c.env.DB
          .prepare("UPDATE comments SET state = ?2, moderated_by = ?3, moderated_at = ?4 WHERE id = ?1")
          .bind(id, state, admin.uid, now())
          .run();
        if (!r.meta.changes) throw new HTTPException(404, { message: "Comment not found" });
        return c.json({ id, state });
      },
    )

    // Moderators view report photos here (fetch with the Authorization header and use a blob URL).
    .get("/api/admin/photos/:name", async (c) => {
      await requireAdmin(c);
      const key = `reports/${c.req.param("name")}`;
      if (!PHOTO_KEY_RE.test(key)) throw new HTTPException(400, { message: "Bad photo name" });
      const obj = await c.env.UPLOADS.get(key);
      if (!obj) throw new HTTPException(404, { message: "Photo not found" });
      return new Response(obj.body, {
        headers: {
          "Content-Type": obj.httpMetadata?.contentType ?? "application/octet-stream",
          "Cache-Control": "private, max-age=3600",
        },
      });
    });

  return app;
}

export type AppType = ReturnType<typeof createApp>;
