import { env } from "cloudflare:test";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createVerifier } from "../src/auth";
import { verifyTurnstile } from "../src/turnstile";
import { ADMIN_UID, bearer, named, makeClient, makeToken, PNG, PROJECT, resetDb, testJwks, testJwksJson } from "./helpers";

beforeEach(resetDb);

describe("auth", () => {
  it("accepts a valid token and exposes the uid", async () => {
    const api = makeClient();
    const res = await api.request("/api/me", { headers: await bearer({ uid: "u1" }) });
    expect(res.status).toBe(200);
    expect(((await res.json()) as { uid: string }).uid).toBe("u1");
  });

  it("rejects a missing token on protected routes", async () => {
    const res = await makeClient().request("/api/me");
    expect(res.status).toBe(401);
  });

  it.each([
    ["expired", { expIn: -60 }],
    ["wrong issuer", { iss: "https://securetoken.google.com/other-project" }],
    ["wrong audience", { aud: "other-project" }],
    ["signed by an unknown key", { signWithOtherKey: true }],
    ["missing sub", { omitSub: true }],
  ])("rejects a token that is %s", async (_name, opts) => {
    const res = await makeClient().request("/api/me", { headers: await bearer(opts) });
    expect(res.status).toBe(401);
  });

  it("rejects garbage and malformed headers", async () => {
    const api = makeClient();
    expect((await api.request("/api/me", { headers: { Authorization: "Bearer nope" } })).status).toBe(401);
    expect((await api.request("/api/me", { headers: { Authorization: "Basic abc" } })).status).toBe(401);
  });

  it("an invalid token on an optional-auth route is a 401, not silently anonymous", async () => {
    const res = await makeClient().request("/api/bench/1/social", { headers: { Authorization: "Bearer nope" } });
    expect(res.status).toBe(401);
  });

  it("verifier takes project id and key source as parameters", async () => {
    const verify = createVerifier({ projectId: "another", jwks: testJwks });
    await expect(verify(await makeToken())).rejects.toThrow();
    const ok = createVerifier({ projectId: PROJECT, jwks: testJwks });
    await expect(ok(await makeToken({ uid: "x" }))).resolves.toMatchObject({ uid: "x" });
  });
});

describe("ratings and status", () => {
  it("rating upsert is idempotent and updates in place", async () => {
    const api = makeClient();
    const h = await bearer({ uid: "u1" });
    for (let i = 0; i < 3; i++) expect((await api.json("PUT", "/api/bench/7/rating", { rating: 4 }, h)).status).toBe(200);
    expect((await api.json("PUT", "/api/bench/7/rating", { rating: 2 }, h)).status).toBe(200);
    await api.json("PUT", "/api/bench/7/rating", { rating: 5 }, await bearer({ uid: "u2" }));

    const rows = await env.DB.prepare("SELECT COUNT(*) AS n FROM ratings WHERE bench_id = 7").first<{ n: number }>();
    expect(rows?.n).toBe(2);
    const social = (await (await api.request("/api/bench/7/social", { headers: h })).json()) as {
      ratings: { count: number; average: number };
      me: { rating: number };
    };
    expect(social.ratings).toEqual({ count: 2, average: 3.5 });
    expect(social.me.rating).toBe(2);
  });

  it("validates rating range and bench id", async () => {
    const api = makeClient();
    const h = await bearer();
    expect((await api.json("PUT", "/api/bench/7/rating", { rating: 6 }, h)).status).toBe(400);
    expect((await api.json("PUT", "/api/bench/7/rating", { rating: 0 }, h)).status).toBe(400);
    expect((await api.json("PUT", "/api/bench/abc/rating", { rating: 3 }, h)).status).toBe(400);
    expect((await api.json("PUT", "/api/bench/7/rating", { rating: 3 })).status).toBe(401);
  });

  it("status updates are partial and show up in /api/me", async () => {
    const api = makeClient();
    const h = await bearer({ uid: "u1" });
    await api.json("PUT", "/api/bench/3/status", { visited: true }, h);
    const r = await api.json("PUT", "/api/bench/3/status", { favorite: true }, h);
    expect(await r.json()).toMatchObject({ visited: true, favorite: true });
    await api.json("PUT", "/api/bench/4/status", { favorite: true }, h);
    await api.json("PUT", "/api/bench/4/status", { favorite: false }, h);
    await api.json("PUT", "/api/bench/5/rating", { rating: 5 }, h);
    const w = await api.json("PUT", "/api/bench/6/status", { want: true }, h);
    expect(await w.json()).toMatchObject({ visited: false, favorite: false, want: true });

    const me = (await (await api.request("/api/me", { headers: h })).json()) as {
      ratings: { benchId: number; rating: number }[];
      visited: number[];
      favorites: number[];
      want: number[];
    };
    expect(me.visited).toEqual([3]);
    expect(me.favorites).toEqual([3]);
    expect(me.want).toEqual([6]);
    expect(me.ratings).toEqual([{ benchId: 5, rating: 5 }]);
    expect((await api.json("PUT", "/api/bench/3/status", {}, h)).status).toBe(400);
  });

  it("anonymous social view has no `me`", async () => {
    const res = await makeClient().request("/api/bench/9/social");
    expect(await res.json()).toMatchObject({ me: null, comments: [], ratings: { count: 0, average: null } });
  });
});

describe("comments", () => {
  it("creates, lists, and lets the author delete (soft)", async () => {
    const api = makeClient();
    await named(["u1", "ann"]);
    const h = await bearer({ uid: "u1", name: "Ann" });
    const created = await api.json("POST", "/api/bench/1/comments", { body: "  Nice view  " }, h);
    expect(created.status).toBe(201);
    const { id } = (await created.json()) as { id: number };

    const list = (await (await api.request("/api/bench/1/social", { headers: h })).json()) as {
      comments: { id: number; body: string; displayName: string; mine: boolean }[];
    };
    expect(list.comments).toMatchObject([{ id, body: "Nice view", displayName: "ann", mine: true }]);

    const anon = (await (await api.request("/api/bench/1/social")).json()) as { comments: { mine: boolean }[] };
    expect(anon.comments[0].mine).toBe(false);

    expect((await api.json("DELETE", `/api/comments/${id}`, undefined, h)).status).toBe(200);
    const row = await env.DB.prepare("SELECT deleted_at FROM comments WHERE id = ?").bind(id).first<{ deleted_at: string }>();
    expect(row?.deleted_at).toBeTruthy(); // soft delete: row kept
    const after = (await (await api.request("/api/bench/1/social")).json()) as { comments: unknown[] };
    expect(after.comments).toEqual([]);
    expect((await api.json("DELETE", `/api/comments/${id}`, undefined, h)).status).toBe(404);
  });

  it("cannot delete someone else's comment", async () => {
    const api = makeClient();
    await named("u1");
    const c = await api.json("POST", "/api/bench/1/comments", { body: "mine" }, await bearer({ uid: "u1" }));
    const { id } = (await c.json()) as { id: number };
    const res = await api.json("DELETE", `/api/comments/${id}`, undefined, await bearer({ uid: "u2" }));
    expect(res.status).toBe(403);
    expect((await api.json("DELETE", `/api/comments/${id}`)).status).toBe(401);
    const row = await env.DB.prepare("SELECT deleted_at FROM comments WHERE id = ?").bind(id).first<{ deleted_at: string | null }>();
    expect(row?.deleted_at).toBeNull();
  });

  it("requires sign-in and validates body", async () => {
    const api = makeClient();
    expect((await api.json("POST", "/api/bench/1/comments", { body: "x" })).status).toBe(401);
    const h = await bearer();
    expect((await api.json("POST", "/api/bench/1/comments", { body: "   " }, h)).status).toBe(400);
    expect((await api.json("POST", "/api/bench/1/comments", { body: "x".repeat(2001) }, h)).status).toBe(400);
  });

  it("rate limits comments per user", async () => {
    const api = makeClient({}, { RATE_LIMIT_COMMENTS_PER_HOUR: "2" });
    await named("spammer");
    const h = await bearer({ uid: "spammer" });
    const codes = [];
    for (let i = 0; i < 3; i++) codes.push((await api.json("POST", "/api/bench/1/comments", { body: `c${i}` }, h)).status);
    expect(codes).toEqual([201, 201, 429]);
  });
});

describe("reports", () => {
  const ip = { "CF-Connecting-IP": "203.0.113.5" };

  it("anonymous bench report with a valid Turnstile token is stored", async () => {
    const api = makeClient();
    const res = await api.json("POST", "/api/reports/bench", { benchId: 12, reason: "not_a_bench", note: "a bin", turnstileToken: "good-token" }, ip);
    expect(res.status).toBe(201);
    const row = await env.DB.prepare("SELECT * FROM bench_reports").first<Record<string, unknown>>();
    expect(row).toMatchObject({ bench_id: 12, reason: "not_a_bench", user_id: null, status: "pending" });
  });

  it("anonymous report without or with a bad Turnstile token is refused", async () => {
    const api = makeClient();
    const base = { benchId: 12, reason: "other" };
    expect((await api.json("POST", "/api/reports/bench", base, ip)).status).toBe(403);
    expect((await api.json("POST", "/api/reports/bench", { ...base, turnstileToken: "bad" }, ip)).status).toBe(403);
    const c = await env.DB.prepare("SELECT COUNT(*) AS n FROM bench_reports").first<{ n: number }>();
    expect(c?.n).toBe(0);
  });

  it("token may be sent in the X-Turnstile-Token header", async () => {
    const res = await makeClient().json("POST", "/api/reports/missing", { lat: 52.37, lng: 4.9 }, { ...ip, "X-Turnstile-Token": "good-token" });
    expect(res.status).toBe(201);
    expect(await env.DB.prepare("SELECT lat FROM missing_bench_reports").first()).toEqual({ lat: 52.37 });
  });

  it("signed-in users skip Turnstile", async () => {
    const res = await makeClient().json("POST", "/api/reports/missing", { lat: 1, lng: 2 }, { ...ip, ...(await bearer({ uid: "u9" })) });
    expect(res.status).toBe(201);
    expect(await env.DB.prepare("SELECT user_id FROM missing_bench_reports").first()).toEqual({ user_id: "u9" });
  });

  it("stores the panorama a missing bench shows in", async () => {
    const pano = { source: "amsterdam", id: "2025_09_26_10_36_44_00869", heading: 212.5 };
    const res = await makeClient().json("POST", "/api/reports/missing", { lat: 52.3645, lng: 4.8578, pano }, { ...ip, ...(await bearer({ uid: "u9" })) });
    expect(res.status).toBe(201);
    expect(
      await env.DB.prepare("SELECT pano_source, pano_id, pano_heading FROM missing_bench_reports").first(),
    ).toEqual({ pano_source: "amsterdam", pano_id: pano.id, pano_heading: 212.5 });
    const bad = await makeClient().json("POST", "/api/reports/missing", { lat: 1, lng: 2, pano: { ...pano, heading: 360 } }, { ...ip, ...(await bearer({ uid: "u9" })) });
    expect(bad.status).toBe(400);
  });

  it("refuses everything anonymous when the Turnstile secret is not configured (default verifier)", async () => {
    const api = makeClient({ verifyTurnstile });
    const res = await api.json("POST", "/api/reports/bench", { benchId: 1, reason: "other", turnstileToken: "x" }, ip);
    expect(res.status).toBe(403);
  });

  it("default verifier calls siteverify with the secret", async () => {
    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(Response.json({ success: true, action: "report", hostname: "bench.blackmad.com" }));
    const env = { TURNSTILE_SECRET: "s3cret", ALLOWED_ORIGINS: "https://bench.blackmad.com" } as never;
    const ok = await verifyTurnstile("tok", "1.2.3.4", env, "report");
    expect(ok).toBe(true);
    const [url, init] = spy.mock.calls[0];
    expect(String(url)).toContain("challenges.cloudflare.com/turnstile/v0/siteverify");
    expect(String((init as RequestInit).body)).toContain("secret=s3cret");
    spy.mockRestore();
  });

  it("default verifier rejects a token for another action or hostname", async () => {
    const env = { TURNSTILE_SECRET: "s", ALLOWED_ORIGINS: "https://bench.blackmad.com" } as never;
    const reply = (body: object) => vi.spyOn(globalThis, "fetch").mockResolvedValue(Response.json(body));
    let spy = reply({ success: true, action: "login", hostname: "bench.blackmad.com" });
    expect(await verifyTurnstile("tok", "", env, "report")).toBe(false);
    spy.mockRestore();
    spy = reply({ success: true, action: "report", hostname: "localhost" });
    expect(await verifyTurnstile("tok", "", env, "report")).toBe(false);
    spy.mockRestore();
    spy = reply({ success: true, action: "report", hostname: "localhost" });
    expect(await verifyTurnstile("tok", "", { ...(env as object), TURNSTILE_HOSTNAMES: "localhost" } as never, "report")).toBe(true);
    spy.mockRestore();
  });

  it("validates input (reason, coordinates, photo key)", async () => {
    const api = makeClient();
    const t = { ...ip, ...(await bearer()) };
    expect((await api.json("POST", "/api/reports/bench", { benchId: 1, reason: "nope" }, t)).status).toBe(400);
    expect((await api.json("POST", "/api/reports/missing", { lat: 91, lng: 0 }, t)).status).toBe(400);
    expect((await api.json("POST", "/api/reports/bench", { benchId: 1, reason: "other", photoKey: "../etc" }, t)).status).toBe(400);
    const unknownKey = `reports/${crypto.randomUUID()}.png`;
    expect((await api.json("POST", "/api/reports/bench", { benchId: 1, reason: "other", photoKey: unknownKey }, t)).status).toBe(400);
  });

  it("rate limit kicks in per IP and is independent across IPs", async () => {
    const api = makeClient({}, { RATE_LIMIT_REPORTS_PER_HOUR: "3" });
    const send = (addr: string) =>
      api.json("POST", "/api/reports/missing", { lat: 1, lng: 2, turnstileToken: "good-token" }, { "CF-Connecting-IP": addr });
    const codes = [];
    for (let i = 0; i < 5; i++) codes.push((await send("198.51.100.1")).status);
    expect(codes).toEqual([201, 201, 201, 429, 429]);
    expect((await send("198.51.100.2")).status).toBe(201);
    const limited = await send("198.51.100.1");
    expect(limited.headers.get("Retry-After")).toBe("3600");
  });
});

describe("uploads", () => {
  const ip = { "CF-Connecting-IP": "203.0.113.9" };

  it("stores a valid image and the key can be attached to a report", async () => {
    const api = makeClient();
    const up = await api.request("/api/uploads", { method: "POST", headers: { ...ip, "Content-Type": "image/png", "X-Turnstile-Token": "good-token" }, body: PNG });
    expect(up.status).toBe(201);
    const { key } = (await up.json()) as { key: string };
    expect(key).toMatch(/^reports\/[0-9a-f-]{36}\.png$/);
    expect(await env.UPLOADS.head(key)).not.toBeNull();
    const rep = await api.json("POST", "/api/reports/bench", { benchId: 1, reason: "bad_image", photoKey: key, turnstileToken: "good-token" }, ip);
    expect(rep.status).toBe(201);
  });

  it("rejects anonymous without Turnstile, wrong types, spoofed content, and oversize", async () => {
    const api = makeClient();
    const post = (headers: Record<string, string>, body: BodyInit) => api.request("/api/uploads", { method: "POST", headers: { ...ip, ...headers }, body });
    expect((await post({ "Content-Type": "image/png" }, PNG)).status).toBe(403);
    const auth = await bearer();
    expect((await post({ ...auth, "Content-Type": "text/html" }, "<script>")).status).toBe(415);
    expect((await post({ ...auth, "Content-Type": "image/jpeg" }, PNG)).status).toBe(415); // declared != actual
    expect((await post({ ...auth, "Content-Type": "image/png" }, new Uint8Array(0))).status).toBe(400);
    const big = new Uint8Array(5 * 1024 * 1024 + 1);
    big.set(PNG);
    expect((await post({ ...auth, "Content-Type": "image/png" }, big)).status).toBe(413);
  });
});

describe("admin", () => {
  const seed = async () => {
    await env.DB.prepare("INSERT INTO bench_reports (bench_id, reason, created_at) VALUES (5, 'other', '2026-01-01')").run();
    await env.DB.prepare("INSERT INTO missing_bench_reports (lat, lng, created_at) VALUES (1, 2, '2026-01-01')").run();
    await env.DB.prepare("INSERT INTO comments (bench_id, user_id, body, created_at) VALUES (5, 'u1', 'rude', '2026-01-01')").run();
  };

  it("is enforced by the uid allowlist on every admin route", async () => {
    await seed();
    const api = makeClient();
    const user = await bearer({ uid: "regular" });
    const routes: [string, string][] = [
      ["GET", "/api/admin/reports"],
      ["GET", "/api/admin/comments"],
      ["POST", "/api/admin/reports/bench/1/resolve"],
      ["POST", "/api/admin/comments/1/hide"],
      ["GET", "/api/admin/photos/x"],
    ];
    for (const [m, p] of routes) {
      expect((await api.json(m, p)).status, `${m} ${p} anon`).toBe(401);
      expect((await api.json(m, p, undefined, user)).status, `${m} ${p} user`).toBe(403);
    }
    const st = await env.DB.prepare("SELECT status FROM bench_reports").first<{ status: string }>();
    expect(st?.status).toBe("pending");
    expect((await api.json("GET", "/api/admin/reports", undefined, await bearer({ uid: ADMIN_UID }))).status).toBe(200);
  });

  it("empty allowlist means nobody is admin", async () => {
    const api = makeClient({}, { ADMIN_UIDS: "" });
    expect((await api.json("GET", "/api/admin/reports", undefined, await bearer({ uid: ADMIN_UID }))).status).toBe(403);
  });

  it("lists pending reports, resolves and dismisses them", async () => {
    await seed();
    const api = makeClient();
    const admin = await bearer({ uid: ADMIN_UID });
    const list = (await (await api.json("GET", "/api/admin/reports", undefined, admin)).json()) as { bench: { id: number }[]; missing: { id: number }[] };
    expect(list.bench).toHaveLength(1);
    expect(list.missing).toHaveLength(1);

    const r1 = await api.json("POST", `/api/admin/reports/bench/${list.bench[0].id}/resolve`, { adminNotes: "fixed" }, admin);
    expect(await r1.json()).toMatchObject({ status: "resolved" });
    await api.json("POST", `/api/admin/reports/missing/${list.missing[0].id}/dismiss`, {}, admin);

    const after = (await (await api.json("GET", "/api/admin/reports", undefined, admin)).json()) as { bench: unknown[]; missing: unknown[] };
    expect(after.bench).toHaveLength(0);
    expect(after.missing).toHaveLength(0);
    const row = await env.DB.prepare("SELECT status, admin_notes, resolved_by FROM bench_reports").first();
    expect(row).toEqual({ status: "resolved", admin_notes: "fixed", resolved_by: ADMIN_UID });
    expect((await api.json("POST", "/api/admin/reports/bench/999/resolve", undefined, admin)).status).toBe(404);
  });

  it("flagged comments are queued; admin can hide them and they vanish publicly", async () => {
    await seed();
    const api = makeClient();
    const admin = await bearer({ uid: ADMIN_UID });
    expect(((await (await api.json("GET", "/api/admin/comments", undefined, admin)).json()) as { comments: unknown[] }).comments).toHaveLength(0);

    const cid = (await env.DB.prepare("SELECT id FROM comments").first<{ id: number }>())?.id;
    const flag = await api.json("POST", `/api/comments/${cid}/flag`, undefined, await bearer({ uid: "reader" }));
    expect(await flag.json()).toMatchObject({ flagged: true });
    const queue = (await (await api.json("GET", "/api/admin/comments", undefined, admin)).json()) as { comments: { id: number }[] };
    expect(queue.comments).toHaveLength(1);

    await api.json("POST", `/api/admin/comments/${queue.comments[0].id}/hide`, undefined, admin);
    const pub = (await (await api.request("/api/bench/5/social")).json()) as { comments: unknown[] };
    expect(pub.comments).toHaveLength(0);
  });
});

describe("misc", () => {
  it("CORS allows localhost:5173 and configured origins only", async () => {
    const api = makeClient({}, { ALLOWED_ORIGINS: "https://bench.example.org" });
    const pre = (origin: string) =>
      api.request("/api/bench/1/rating", { method: "OPTIONS", headers: { Origin: origin, "Access-Control-Request-Method": "PUT" } });
    expect((await pre("http://localhost:5173")).headers.get("Access-Control-Allow-Origin")).toBe("http://localhost:5173");
    expect((await pre("https://bench.example.org")).headers.get("Access-Control-Allow-Origin")).toBe("https://bench.example.org");
    expect((await pre("https://evil.example")).headers.get("Access-Control-Allow-Origin")).toBeNull();
  });

  it("unknown routes return JSON 404", async () => {
    const res = await makeClient().request("/api/nope");
    expect(res.status).toBe(404);
    expect(await res.json()).toEqual({ error: "Not found" });
  });
});

describe("AUTH_TEST_JWKS", () => {
  it("is ignored unless set", async () => {
    const c = makeClient({ jwks: undefined });
    const res = await c.request("/api/me", { headers: await bearer() });
    expect(res.status).toBe(401);
  });

  it("verifies tokens against the supplied keys when set", async () => {
    const c = makeClient({ jwks: undefined }, { AUTH_TEST_JWKS: testJwksJson });
    const res = await c.request("/api/me", { headers: await bearer({ uid: ADMIN_UID }) });
    expect(res.status).toBe(200);
    expect(((await res.json()) as { isAdmin: boolean }).isAdmin).toBe(true);
    const bad = await c.request("/api/me", { headers: await bearer({ signWithOtherKey: true }) });
    expect(bad.status).toBe(401);
  });
});

describe("ratings", () => {
  it("can be cleared", async () => {
    const api = makeClient();
    const h = await bearer({ uid: "u1" });
    expect((await api.json("PUT", "/api/bench/3/rating", { rating: 2 }, h)).status).toBe(200);
    expect((await api.json("DELETE", "/api/bench/3/rating", undefined, h)).status).toBe(200);
    const s = (await (await api.request("/api/bench/3/social", { headers: h })).json()) as {
      ratings: { count: number };
      me: { rating: number | null };
    };
    expect([s.ratings.count, s.me.rating]).toEqual([0, null]);
  });
});
