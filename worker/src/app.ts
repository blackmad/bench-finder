import { zValidator } from "@hono/zod-validator";
import { type Context, Hono } from "hono";
import { cors } from "hono/cors";
import { HTTPException } from "hono/http-exception";
import type { JWTVerifyGetKey } from "jose";
import { z } from "zod";
import { type AuthUser, googleJwks, testJwksFromEnv, verifierFromEnv } from "./auth";
import * as Sentry from "@sentry/cloudflare";
import { csv, type Env } from "./env";
import { hit, num } from "./rate-limit";
import { TURNSTILE_ACTION, type TurnstileVerifier, verifyTurnstile } from "./turnstile";

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

/** A published image rendition path, e.g. img/12276b213fb43d16-800.avif. */
const IMG_PATH = /^img\/([0-9a-f]{16})-\d{2,4}\.(avif|webp)$/;
const urlSet = z.record(z.string().regex(/^\d{2,4}$/), z.string().regex(IMG_PATH)).refine((u) => Object.keys(u).length > 0);
const heroPhoto = z
  .object({
    urls: urlSet,
    urls_webp: urlSet.optional(),
    width: z.number().int().positive().max(10000),
    height: z.number().int().positive().max(10000),
  })
  // All renditions are of one image.
  .refine((p) => new Set([...Object.values(p.urls), ...Object.values(p.urls_webp ?? {})].map((u) => u.match(IMG_PATH)?.[1])).size === 1, {
    message: "Photo URLs must all be one image",
  });
type HeroPhoto = z.infer<typeof heroPhoto>;
const heroBody = z.object({ imageId: z.number().int().positive(), photo: heroPhoto });
const heroKey = (p: HeroPhoto) => (Object.values(p.urls)[0].match(IMG_PATH) as RegExpMatchArray)[1];

interface PickRow {
  bench_id: number;
  image_id: number;
  image_key: string;
  photo: string;
}

async function setPick(db: D1Database, benchId: number, imageId: number, photo: HeroPhoto, by: string) {
  const clean = { urls: photo.urls, urls_webp: photo.urls_webp, width: photo.width, height: photo.height };
  await db
    .prepare(
      `INSERT INTO hero_picks (bench_id, image_id, image_key, photo, picked_by, picked_at) VALUES (?1, ?2, ?3, ?4, ?5, ?6)
       ON CONFLICT (bench_id) DO UPDATE SET image_id = excluded.image_id, image_key = excluded.image_key,
         photo = excluded.photo, picked_by = excluded.picked_by, picked_at = excluded.picked_at`,
    )
    .bind(benchId, imageId, heroKey(photo), JSON.stringify(clean), by, now())
    .run();
}

/** Favourites in the user's order, then the unranked ones newest first. */
const FAVORITE_ORDER = "fav_rank IS NULL, fav_rank, favorited_at DESC, updated_at DESC";

interface ProfileRow {
  slug: string;
  handle: string | null;
  display_name: string;
  public: number;
}

const profileOut = (p: ProfileRow) => ({
  slug: p.slug,
  handle: p.handle,
  displayName: p.display_name,
  public: p.public === 1,
});

/** A rating this close to a starred note by the same person is that note's. */
const NOTE_RATING_MS = 60 * 60 * 1000;

export type FeedItem =
  | { kind: "note"; key: string; benchId: number; at: string; who: string; text: string; rating: number | null }
  | { kind: "rating"; key: string; benchId: number; at: string; rating: number }
  | { kind: "fave"; key: string; benchId: number; at: string; who: string; page: string };

/** Paths and words a handle may not take (it shares /u/ with share slugs). */
const RESERVED_HANDLES = new Set([
  "admin", "api", "me", "u", "bench", "benches", "about", "help", "settings", "login", "signin",
  "signup", "logout", "moderate", "moderator", "support", "bench-finder", "benchfinder", "official",
  "null", "undefined", "anonymous",
]);

/** Why a handle is not allowed, or null when it is fine. Handles are lowercase. */
export function handleProblem(h: string): string | null {
  if (!/^[a-z0-9][a-z0-9_-]{2,23}$/.test(h)) {
    return "Use 3-24 letters, numbers, - or _ (starting with a letter or number)";
  }
  if (RESERVED_HANDLES.has(h)) return "That name is reserved";
  return null;
}

/** First name only by default: the page is public. */
export const defaultDisplayName = (name: string | null) =>
  (name ?? "").trim().split(/\s+/)[0]?.slice(0, 40) || "A bench lover";

const SLUG_CHARS = "abcdefghjkmnpqrstuvwxyz23456789";

/** A random share id that is no one's slug or handle. */
async function freshSlug(db: D1Database): Promise<string> {
  for (;;) {
    const bytes = crypto.getRandomValues(new Uint8Array(8));
    const slug = [...bytes].map((b) => SLUG_CHARS[b % SLUG_CHARS.length]).join("");
    const clash = await db.prepare("SELECT 1 FROM profiles WHERE slug = ?1 OR handle = ?1").bind(slug).first();
    if (!clash) return slug;
  }
}
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
    if (!user && !(await checkTurnstile(token ?? "", ip, c.env, TURNSTILE_ACTION))) {
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
      // Hono catches it before withSentry can: report it here.
      Sentry.captureException(err);
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
            `SELECT id, display_name, body, created_at, user_id, rating FROM comments
             WHERE bench_id = ?1 AND deleted_at IS NULL AND state IN ('visible','flagged')
             ORDER BY created_at DESC, id DESC LIMIT 200`,
          )
          .bind(id),
        c.env.DB.prepare("SELECT rating FROM ratings WHERE bench_id = ?1 AND user_id = ?2").bind(id, uid),
        c.env.DB.prepare("SELECT visited, favorite, want FROM user_status WHERE bench_id = ?1 AND user_id = ?2").bind(id, uid),
      ]);
      const s = (summary.results[0] ?? {}) as { count?: number; average?: number | null };
      const myRating = (mine.results[0] as { rating: number } | undefined)?.rating ?? null;
      const st = status.results[0] as { visited: number; favorite: number; want: number } | undefined;
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
            rating: number | null;
          }[]
        ).map((r) => ({
          id: r.id,
          displayName: r.display_name,
          body: r.body,
          createdAt: r.created_at,
          rating: r.rating,
          mine: uid !== null && r.user_id === uid,
        })),
        me: user
          ? { rating: myRating, visited: st?.visited === 1, favorite: st?.favorite === 1, want: st?.want === 1 }
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
          .object({ visited: z.boolean().optional(), favorite: z.boolean().optional(), want: z.boolean().optional() })
          .refine(
            (v) => v.visited !== undefined || v.favorite !== undefined || v.want !== undefined,
            "visited, favorite or want required",
          ),
        validationHook,
      ),
      async (c) => {
        const user = await requireUser(c);
        const { id } = c.req.valid("param");
        const { visited, favorite, want } = c.req.valid("json");
        const t = now();
        // Partial update: omitted fields keep their current value.
        const row = await c.env.DB
          .prepare(
            // favorited_at marks when a bench became a favourite (the feed);
            // un-favouriting clears it and the bench's place in the order.
            `INSERT INTO user_status (bench_id, user_id, visited, favorite, want, created_at, updated_at, favorited_at)
             VALUES (?1, ?2, COALESCE(?3, 0), COALESCE(?4, 0), COALESCE(?6, 0), ?5, ?5, CASE WHEN ?4 = 1 THEN ?5 END)
             ON CONFLICT(bench_id, user_id) DO UPDATE SET
               visited = COALESCE(?3, visited), favorite = COALESCE(?4, favorite), want = COALESCE(?6, want),
               favorited_at = CASE WHEN ?4 = 1 AND favorite = 0 THEN ?5 WHEN ?4 = 0 THEN NULL ELSE favorited_at END,
               fav_rank = CASE WHEN ?4 = 0 THEN NULL ELSE fav_rank END,
               updated_at = excluded.updated_at
             RETURNING visited, favorite, want`,
          )
          .bind(
            id,
            user.uid,
            visited === undefined ? null : +visited,
            favorite === undefined ? null : +favorite,
            t,
            want === undefined ? null : +want,
          )
          .first<{ visited: number; favorite: number; want: number }>();
        return c.json({ benchId: id, visited: row?.visited === 1, favorite: row?.favorite === 1, want: row?.want === 1 });
      },
    )

    .post(
      "/api/bench/:id/comments",
      zValidator("param", idParam, validationHook),
      zValidator(
        "json",
        // Stars sent with a note also set the user's rating, and show with the note.
        z.object({ body: z.string().trim().min(1).max(2000), rating: z.number().int().min(1).max(5).optional() }),
        validationHook,
      ),
      async (c) => {
        const user = await requireUser(c);
        const { id } = c.req.valid("param");
        const { body, rating } = c.req.valid("json");
        const { allowed } = await hit(c.env.DB, "comment", user.uid, num(c.env.RATE_LIMIT_COMMENTS_PER_HOUR, 20));
        if (!allowed) throw new HTTPException(429, { message: "Too many comments, try again later" });
        const t = now();
        const displayName = user.name?.trim() || "Anonymous";
        const [inserted] = await c.env.DB.batch([
          c.env.DB
            .prepare(
              `INSERT INTO comments (bench_id, user_id, display_name, body, created_at, rating) VALUES (?1, ?2, ?3, ?4, ?5, ?6)
               RETURNING id`,
            )
            .bind(id, user.uid, displayName, body, t, rating ?? null),
          ...(rating
            ? [
                c.env.DB
                  .prepare(
                    `INSERT INTO ratings (bench_id, user_id, rating, created_at, updated_at) VALUES (?1, ?2, ?3, ?4, ?4)
                     ON CONFLICT(bench_id, user_id) DO UPDATE SET rating = excluded.rating, updated_at = excluded.updated_at`,
                  )
                  .bind(id, user.uid, rating, t),
              ]
            : []),
        ]);
        const newId = (inserted.results[0] as { id: number } | undefined)?.id ?? 0;
        return c.json({ id: newId, displayName, body, createdAt: t, mine: true, rating: rating ?? null }, 201);
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
      const [ratings, statuses, profile] = await c.env.DB.batch([
        c.env.DB.prepare("SELECT bench_id, rating, updated_at FROM ratings WHERE user_id = ?1 ORDER BY updated_at DESC").bind(user.uid),
        c.env.DB
          .prepare(
            `SELECT bench_id, visited, favorite, want FROM user_status
             WHERE user_id = ?1 AND (visited = 1 OR favorite = 1 OR want = 1)
             ORDER BY ${FAVORITE_ORDER}`,
          )
          .bind(user.uid),
        c.env.DB.prepare("SELECT slug, handle, display_name, public FROM profiles WHERE user_id = ?1").bind(user.uid),
      ]);
      const st = statuses.results as { bench_id: number; visited: number; favorite: number; want: number }[];
      const p = profile.results[0] as ProfileRow | undefined;
      return c.json({
        uid: user.uid,
        isAdmin: csv(c.env.ADMIN_UIDS).includes(user.uid),
        ratings: (ratings.results as { bench_id: number; rating: number }[]).map((r) => ({
          benchId: r.bench_id,
          rating: r.rating,
        })),
        visited: st.filter((r) => r.visited === 1).map((r) => r.bench_id),
        favorites: st.filter((r) => r.favorite === 1).map((r) => r.bench_id),
        want: st.filter((r) => r.want === 1).map((r) => r.bench_id),
        profile: p ? profileOut(p) : null,
      });
    })

    // ---- Public favourites pages ------------------------------------------------
    .put(
      "/api/me/profile",
      zValidator(
        "json",
        z.object({
          public: z.boolean().optional(),
          // null clears the handle (the page falls back to its slug).
          handle: z.string().trim().toLowerCase().nullable().optional(),
          displayName: z.string().trim().min(1).max(40).optional(),
        }),
        validationHook,
      ),
      async (c) => {
        const user = await requireUser(c);
        const req = c.req.valid("json");
        const t = now();
        let row = await c.env.DB
          .prepare("SELECT slug, handle, display_name, public FROM profiles WHERE user_id = ?1")
          .bind(user.uid)
          .first<ProfileRow>();
        if (!row) {
          const slug = await freshSlug(c.env.DB);
          row = { slug, handle: null, display_name: defaultDisplayName(user.name), public: 0 };
          await c.env.DB
            .prepare(
              "INSERT INTO profiles (user_id, slug, display_name, public, created_at, updated_at) VALUES (?1, ?2, ?3, 0, ?4, ?4)",
            )
            .bind(user.uid, slug, row.display_name, t)
            .run();
        }
        if (req.handle !== undefined && req.handle !== row.handle) {
          if (req.handle !== null) {
            const problem = handleProblem(req.handle);
            if (problem) throw new HTTPException(400, { message: problem });
            const taken = await c.env.DB
              .prepare("SELECT 1 FROM profiles WHERE (handle = ?1 OR slug = ?1) AND user_id != ?2")
              .bind(req.handle, user.uid)
              .first();
            if (taken) throw new HTTPException(409, { message: "That name is taken" });
          }
          row.handle = req.handle;
        }
        if (req.displayName !== undefined) row.display_name = req.displayName;
        if (req.public !== undefined) row.public = +req.public;
        await c.env.DB
          .prepare("UPDATE profiles SET handle = ?2, display_name = ?3, public = ?4, updated_at = ?5 WHERE user_id = ?1")
          .bind(user.uid, row.handle, row.display_name, row.public, t)
          .run();
        return c.json(profileOut(row));
      },
    )

    .put(
      "/api/me/favorites/order",
      zValidator("json", z.object({ ids: z.array(benchId).max(1000) }), validationHook),
      async (c) => {
        const user = await requireUser(c);
        const { ids } = c.req.valid("json");
        const t = now();
        // Listed favourites take their position; any not listed lose their rank.
        await c.env.DB.batch([
          c.env.DB.prepare("UPDATE user_status SET fav_rank = NULL WHERE user_id = ?1 AND favorite = 1").bind(user.uid),
          ...ids.map((id, i) =>
            c.env.DB
              .prepare("UPDATE user_status SET fav_rank = ?3, updated_at = ?4 WHERE user_id = ?1 AND bench_id = ?2 AND favorite = 1")
              .bind(user.uid, id, i, t),
          ),
        ]);
        return c.json({ ok: true });
      },
    )

    .get("/api/u/:key", zValidator("param", z.object({ key: z.string().min(1).max(40) }), validationHook), async (c) => {
      const key = c.req.valid("param").key.toLowerCase();
      const p = await c.env.DB
        .prepare("SELECT user_id, slug, handle, display_name FROM profiles WHERE public = 1 AND (slug = ?1 OR handle = ?1)")
        .bind(key)
        .first<{ user_id: string; slug: string; handle: string | null; display_name: string }>();
      if (!p) throw new HTTPException(404, { message: "No public page here" });
      const favs = await c.env.DB
        .prepare(`SELECT bench_id FROM user_status WHERE user_id = ?1 AND favorite = 1 ORDER BY ${FAVORITE_ORDER}`)
        .bind(p.user_id)
        .all<{ bench_id: number }>();
      c.header("Cache-Control", "public, max-age=60");
      return c.json({
        displayName: p.display_name,
        handle: p.handle,
        slug: p.slug,
        favorites: favs.results.map((r) => r.bench_id),
      });
    })

    // ---- Homepage feed: notes, ratings (anonymous), public favourites -----------
    .get(
      "/api/feed",
      zValidator("query", z.object({ limit: z.coerce.number().int().min(1).max(50).optional() }), validationHook),
      async (c) => {
        const limit = c.req.valid("query").limit ?? 20;
        const [notes, ratings, faves] = await c.env.DB.batch([
          c.env.DB
            .prepare(
              `SELECT id, bench_id, user_id, display_name, body, created_at, rating FROM comments
               WHERE state = 'visible' AND deleted_at IS NULL ORDER BY created_at DESC LIMIT ?1`,
            )
            .bind(limit),
          c.env.DB
            .prepare("SELECT bench_id, user_id, rating, updated_at FROM ratings ORDER BY updated_at DESC LIMIT ?1")
            .bind(limit),
          // Only from people who made their favourites public.
          c.env.DB
            .prepare(
              `SELECT s.bench_id, s.favorited_at, p.display_name, COALESCE(p.handle, p.slug) AS page
               FROM user_status s JOIN profiles p ON p.user_id = s.user_id AND p.public = 1
               WHERE s.favorite = 1 AND s.favorited_at IS NOT NULL ORDER BY s.favorited_at DESC LIMIT ?1`,
            )
            .bind(limit),
        ]);
        type NoteRow = {
          id: number;
          bench_id: number;
          user_id: string;
          display_name: string;
          body: string;
          created_at: string;
          rating: number | null;
        };
        const noteRows = notes.results as NoteRow[];
        // A rating given with a note is shown on the note's line, not again on its own.
        const withNote = (r: { bench_id: number; user_id: string; updated_at: string }) =>
          noteRows.some(
            (n) =>
              n.rating !== null &&
              n.bench_id === r.bench_id &&
              n.user_id === r.user_id &&
              Math.abs(Date.parse(n.created_at) - Date.parse(r.updated_at)) < NOTE_RATING_MS,
          );
        const items: FeedItem[] = [
          ...noteRows.map(
            (r): FeedItem => ({
              kind: "note",
              key: `n${r.id}`,
              benchId: r.bench_id,
              at: r.created_at,
              who: r.display_name,
              text: r.body.length > 180 ? `${r.body.slice(0, 177)}...` : r.body,
              rating: r.rating,
            }),
          ),
          ...(ratings.results as { bench_id: number; user_id: string; rating: number; updated_at: string }[])
            .filter((r) => !withNote(r))
            .map(
              (r, i): FeedItem => ({
                kind: "rating",
                key: `r${r.bench_id}-${i}`,
                benchId: r.bench_id,
                at: r.updated_at,
                rating: r.rating,
              }),
            ),
          ...(faves.results as { bench_id: number; favorited_at: string; display_name: string; page: string }[]).map(
            (r): FeedItem => ({
              kind: "fave",
              key: `f${r.page}-${r.bench_id}`,
              benchId: r.bench_id,
              at: r.favorited_at,
              who: r.display_name,
              page: r.page,
            }),
          ),
        ];
        items.sort((a, b) => (a.at < b.at ? 1 : a.at > b.at ? -1 : 0));
        c.header("Cache-Control", "public, max-age=60");
        return c.json({ items: items.slice(0, limit) });
      },
    )

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
          // Where the bench shows in a street panorama (optional).
          pano: z
            .object({
              source: z.enum(["amsterdam", "google"]),
              id: z.string().min(1).max(200),
              heading: z.number().min(0).lt(360),
              url: z.string().url().max(2048).optional(),
            })
            .optional(),
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
            `INSERT INTO missing_bench_reports (lat, lng, accuracy_meters, note, photo_key, user_id, created_at,
               pano_source, pano_id, pano_heading, pano_url)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11) RETURNING id`,
          )
          .bind(
            b.lat,
            b.lng,
            b.accuracyMeters ?? null,
            b.note || null,
            b.photoKey ?? null,
            user?.uid ?? null,
            now(),
            b.pano?.source ?? null,
            b.pano?.id ?? null,
            b.pano?.heading ?? null,
            b.pano?.url ?? null,
          )
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

    // ---- Lead photos: moderator picks and visitors' suggestions ------------------
    // Every pick, for the site to apply before the next publish includes it.
    .get("/api/heroes", async (c) => {
      const rows = await c.env.DB.prepare("SELECT bench_id, image_id, image_key, photo FROM hero_picks").all<PickRow>();
      c.header("Cache-Control", "public, max-age=60");
      return c.json({
        picks: Object.fromEntries(
          rows.results.map((r) => [r.bench_id, { imageId: r.image_id, key: r.image_key, ...JSON.parse(r.photo) }]),
        ) as Record<string, HeroPhoto & { imageId: number; key: string }>,
      });
    })

    .put(
      "/api/admin/bench/:id/hero",
      zValidator("param", idParam, validationHook),
      zValidator("json", heroBody, validationHook),
      async (c) => {
        const admin = await requireAdmin(c);
        const { id } = c.req.valid("param");
        const { imageId, photo } = c.req.valid("json");
        await setPick(c.env.DB, id, imageId, photo, admin.uid);
        return c.json({ benchId: id, imageId, key: heroKey(photo) });
      },
    )

    // Back to the automatic choice.
    .delete("/api/admin/bench/:id/hero", zValidator("param", idParam, validationHook), async (c) => {
      await requireAdmin(c);
      const { id } = c.req.valid("param");
      await c.env.DB.prepare("DELETE FROM hero_picks WHERE bench_id = ?1").bind(id).run();
      return c.json({ benchId: id });
    })

    .post(
      "/api/bench/:id/hero-suggestions",
      zValidator("param", idParam, validationHook),
      zValidator("json", heroBody, validationHook),
      async (c) => {
        const user = await requireUser(c);
        const { id } = c.req.valid("param");
        const { imageId, photo } = c.req.valid("json");
        const { allowed } = await hit(c.env.DB, "hero", user.uid, 30);
        if (!allowed) throw new HTTPException(429, { message: "Too many suggestions, try again later" });
        // Suggesting the same photo again re-opens it.
        await c.env.DB
          .prepare(
            `INSERT INTO hero_suggestions (bench_id, image_id, image_key, photo, user_id, display_name, created_at)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)
             ON CONFLICT (bench_id, image_id, user_id) DO UPDATE SET
               state = 'pending', created_at = excluded.created_at, resolved_at = NULL, resolved_by = NULL`,
          )
          .bind(id, imageId, heroKey(photo), JSON.stringify(photo), user.uid, user.name?.trim() || "Anonymous", now())
          .run();
        return c.json({ ok: true }, 201);
      },
    )

    // "Find a better view": a Street View camera to render offline.
    .post(
      "/api/bench/:id/view-suggestions",
      zValidator("param", idParam, validationHook),
      zValidator(
        "json",
        z.object({
          // Google panorama ids: 22 url-safe base64 characters (longer for some).
          panoId: z.string().regex(/^[A-Za-z0-9_-]{16,80}$/),
          heading: z.number().min(-720).max(720),
          pitch: z.number().min(-90).max(90),
          fov: z.number().min(10).max(120),
        }),
        validationHook,
      ),
      async (c) => {
        const user = await requireUser(c);
        const { id } = c.req.valid("param");
        const v = c.req.valid("json");
        const { allowed } = await hit(c.env.DB, "view", user.uid, 30);
        if (!allowed) throw new HTTPException(429, { message: "Too many suggestions, try again later" });
        const heading = ((v.heading % 360) + 360) % 360;
        await c.env.DB
          .prepare(
            `INSERT INTO view_suggestions (bench_id, pano_id, heading, pitch, fov, user_id, display_name, created_at)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)`,
          )
          .bind(id, v.panoId, heading, v.pitch, v.fov, user.uid, user.name?.trim() || "Anonymous", now())
          .run();
        return c.json({ ok: true }, 201);
      },
    )

    .get("/api/admin/view-suggestions", async (c) => {
      await requireAdmin(c);
      const rows = await c.env.DB
        .prepare(
          `SELECT id, bench_id, pano_id, heading, pitch, fov, display_name, state, image_id, error, created_at
           FROM view_suggestions WHERE state IN ('pending', 'rendered', 'failed') ORDER BY created_at DESC LIMIT 200`,
        )
        .all<{
          id: number;
          bench_id: number;
          pano_id: string;
          heading: number;
          pitch: number;
          fov: number;
          display_name: string;
          state: "pending" | "rendered" | "failed";
          image_id: number | null;
          error: string | null;
          created_at: string;
        }>();
      return c.json({
        views: rows.results.map((r) => ({
          id: r.id,
          benchId: r.bench_id,
          panoId: r.pano_id,
          heading: r.heading,
          pitch: r.pitch,
          fov: r.fov,
          who: r.display_name,
          state: r.state,
          imageId: r.image_id,
          error: r.error,
          createdAt: r.created_at,
        })),
      });
    })

    .post(
      "/api/admin/view-suggestions/:id/dismiss",
      zValidator("param", commentIdParam, validationHook),
      async (c) => {
        await requireAdmin(c);
        const { id } = c.req.valid("param");
        const r = await c.env.DB
          .prepare("UPDATE view_suggestions SET state = 'dismissed', resolved_at = ?2 WHERE id = ?1")
          .bind(id, now())
          .run();
        if (!r.meta.changes) throw new HTTPException(404, { message: "Suggestion not found" });
        return c.json({ id, state: "dismissed" });
      },
    )

    .get("/api/admin/hero-suggestions", async (c) => {
      await requireAdmin(c);
      const rows = await c.env.DB
        .prepare(
          `SELECT s.id, s.bench_id, s.image_id, s.image_key, s.photo, s.display_name, s.created_at,
                  p.photo AS current_photo
           FROM hero_suggestions s LEFT JOIN hero_picks p ON p.bench_id = s.bench_id
           WHERE s.state = 'pending' ORDER BY s.created_at LIMIT 200`,
        )
        .all<{
          id: number;
          bench_id: number;
          image_id: number;
          image_key: string;
          photo: string;
          display_name: string;
          created_at: string;
          current_photo: string | null;
        }>();
      return c.json({
        suggestions: rows.results.map((r) => ({
          id: r.id,
          benchId: r.bench_id,
          imageId: r.image_id,
          key: r.image_key,
          photo: JSON.parse(r.photo) as HeroPhoto,
          // A moderator pick already in place; else the published lead stands.
          current: r.current_photo ? (JSON.parse(r.current_photo) as HeroPhoto) : null,
          who: r.display_name,
          createdAt: r.created_at,
        })),
      });
    })

    .post(
      "/api/admin/hero-suggestions/:id/:action",
      zValidator("param", commentIdParam.extend({ action: z.enum(["accept", "dismiss"]) }), validationHook),
      async (c) => {
        const admin = await requireAdmin(c);
        const { id, action } = c.req.valid("param");
        const s = await c.env.DB
          .prepare("SELECT bench_id, image_id, photo FROM hero_suggestions WHERE id = ?1 AND state = 'pending'")
          .bind(id)
          .first<{ bench_id: number; image_id: number; photo: string }>();
        if (!s) throw new HTTPException(404, { message: "Suggestion not found" });
        const t = now();
        if (action === "accept") {
          await setPick(c.env.DB, s.bench_id, s.image_id, JSON.parse(s.photo) as HeroPhoto, admin.uid);
          // The bench is settled: the rest of its open suggestions close with it.
          await c.env.DB
            .prepare(
              `UPDATE hero_suggestions SET state = CASE WHEN image_id = ?2 THEN 'accepted' ELSE 'dismissed' END,
               resolved_at = ?3, resolved_by = ?4 WHERE bench_id = ?1 AND state = 'pending'`,
            )
            .bind(s.bench_id, s.image_id, t, admin.uid)
            .run();
        } else {
          await c.env.DB
            .prepare("UPDATE hero_suggestions SET state = 'dismissed', resolved_at = ?2, resolved_by = ?3 WHERE id = ?1")
            .bind(id, t, admin.uid)
            .run();
        }
        return c.json({ id, state: action === "accept" ? "accepted" : "dismissed" });
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
