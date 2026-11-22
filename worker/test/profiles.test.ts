import { env } from "cloudflare:test";
import { beforeEach, describe, expect, it } from "vitest";
import { defaultDisplayName, handleProblem } from "../src/app";
import { bearer, makeClient, resetDb } from "./helpers";

beforeEach(resetDb);

type Me = {
  favorites: number[];
  profile: { slug: string; handle: string | null; displayName: string; public: boolean } | null;
};

async function fave(api: ReturnType<typeof makeClient>, h: Record<string, string>, ...ids: number[]) {
  for (const id of ids) expect((await api.json("PUT", `/api/bench/${id}/status`, { favorite: true }, h)).status).toBe(200);
}
const me = async (api: ReturnType<typeof makeClient>, h: Record<string, string>) =>
  (await (await api.request("/api/me", { headers: h })).json()) as Me;

describe("public favourites page", () => {
  it("is private until switched on, then served by slug and by handle", async () => {
    const api = makeClient();
    const h = await bearer({ uid: "u1", name: "Lorenzo Rossi" });
    await fave(api, h, 3, 4);
    expect((await me(api, h)).profile).toBeNull();

    const p = (await (await api.json("PUT", "/api/me/profile", {}, h)).json()) as Me["profile"];
    expect(p?.public).toBe(false);
    expect(p?.displayName).toBe("Lorenzo"); // first name only by default
    expect(p?.slug).toMatch(/^[a-z2-9]{8}$/);
    expect((await api.request(`/api/u/${p?.slug}`)).status).toBe(404);

    await api.json("PUT", "/api/me/profile", { public: true }, h);
    const page = (await (await api.request(`/api/u/${p?.slug}`)).json()) as { displayName: string; favorites: number[] };
    expect(page).toMatchObject({ displayName: "Lorenzo", favorites: [4, 3] }); // newest first until ordered

    expect((await api.json("PUT", "/api/me/profile", { handle: "Lorenzo" }, h)).status).toBe(200);
    expect((await api.request("/api/u/lorenzo")).status).toBe(200); // handles are lowercase
    expect((await api.request(`/api/u/${p?.slug}`)).status).toBe(200); // the old link keeps working

    await api.json("PUT", "/api/me/profile", { public: false }, h);
    expect((await api.request("/api/u/lorenzo")).status).toBe(404);
  });

  it("rejects bad, reserved and taken handles, including another user's slug", async () => {
    const api = makeClient();
    const a = await bearer({ uid: "a" });
    const b = await bearer({ uid: "b" });
    await api.json("PUT", "/api/me/profile", { handle: "bench_fan" }, a);
    const bSlug = ((await (await api.json("PUT", "/api/me/profile", {}, b)).json()) as { slug: string }).slug;
    expect((await api.json("PUT", "/api/me/profile", { handle: "bench_fan" }, b)).status).toBe(409);
    expect((await api.json("PUT", "/api/me/profile", { handle: bSlug }, a)).status).toBe(409);
    for (const bad of ["ab", "admin", "-dash", "has space", "x".repeat(25)]) {
      expect((await api.json("PUT", "/api/me/profile", { handle: bad }, b)).status).toBe(400);
    }
    // Clearing a handle frees it.
    await api.json("PUT", "/api/me/profile", { handle: null }, a);
    expect((await api.json("PUT", "/api/me/profile", { handle: "bench_fan" }, b)).status).toBe(200);
  });

  it("keeps the chosen order; un-favouriting drops a bench from it", async () => {
    const api = makeClient();
    const h = await bearer({ uid: "u1" });
    await fave(api, h, 1, 2, 3, 4);
    expect((await api.json("PUT", "/api/me/favorites/order", { ids: [3, 1, 4] }, h)).status).toBe(200);
    expect((await me(api, h)).favorites).toEqual([3, 1, 4, 2]); // unranked after ranked
    await api.json("PUT", "/api/bench/1/status", { favorite: false }, h);
    await fave(api, h, 1); // back as a new, unranked favourite
    expect((await me(api, h)).favorites).toEqual([3, 4, 1, 2]);
    // Ordering someone else's or non-favourite benches changes nothing.
    await api.json("PUT", "/api/me/favorites/order", { ids: [99, 2] }, h);
    expect((await me(api, h)).favorites[0]).toBe(2);
  });

  it("handle and name helpers", () => {
    expect(handleProblem("good_name-1")).toBeNull();
    expect(handleProblem("api")).not.toBeNull();
    expect(defaultDisplayName("  Ana  Maria ")).toBe("Ana");
    expect(defaultDisplayName(null)).toBe("A bench lover");
  });
});

describe("homepage feed", () => {
  it("mixes notes, anonymous ratings and only public favourites, newest first", async () => {
    const api = makeClient();
    const pub = await bearer({ uid: "pub", name: "Pia" });
    const priv = await bearer({ uid: "priv", name: "Pat Private" });
    await api.json("PUT", "/api/me/profile", { public: true, handle: "pia" }, pub);
    await fave(api, pub, 10);
    await fave(api, priv, 11); // private: never in the feed
    await api.json("PUT", "/api/bench/12/rating", { rating: 4 }, priv);
    await api.json("POST", "/api/bench/13/comments", { body: "Sunny at noon" }, priv);

    const res = await api.request("/api/feed");
    expect(res.status).toBe(200);
    const { items } = (await res.json()) as { items: Record<string, unknown>[] };
    expect(items.map((i) => [i.kind, i.benchId]).sort()).toEqual([
      ["fave", 10],
      ["note", 13],
      ["rating", 12],
    ]);
    expect(items.find((i) => i.kind === "fave")).toMatchObject({ who: "Pia", page: "pia" });
    const rating = items.find((i) => i.kind === "rating");
    expect(rating).not.toHaveProperty("who"); // ratings are anonymous
    expect(JSON.stringify(items)).not.toContain("priv");
    const ats = items.map((i) => i.at as string);
    expect([...ats].sort().reverse()).toEqual(ats);
  });

  it("a note posted with stars is one line; a rating on its own stays anonymous", async () => {
    const api = makeClient();
    const sam = await bearer({ uid: "sam", name: "Sam" });
    const ann = await bearer({ uid: "ann", name: "Ann" });
    expect((await api.json("POST", "/api/bench/5/comments", { body: "Quiet after 8", rating: 4 }, sam)).status).toBe(201);
    await api.json("POST", "/api/bench/6/comments", { body: "No stars here" }, ann);
    await api.json("PUT", "/api/bench/6/rating", { rating: 2 }, ann); // rated separately: not tied to her note
    const { items } = (await (await api.request("/api/feed")).json()) as { items: Record<string, unknown>[] };
    expect(items.filter((i) => i.benchId === 5)).toEqual([expect.objectContaining({ kind: "note", who: "Sam", rating: 4 })]);
    expect(items.filter((i) => i.benchId === 6).map((i) => [i.kind, i.rating]).sort()).toEqual([
      ["note", null],
      ["rating", 2],
    ]);
    // The stars also count as Sam's rating, and show beside the note on the bench.
    const social = (await (await api.request("/api/bench/5/social")).json()) as {
      ratings: { count: number };
      comments: { rating: number | null }[];
    };
    expect(social.ratings.count).toBe(1);
    expect(social.comments[0].rating).toBe(4);
  });

  it("hidden and deleted notes stay out", async () => {
    const api = makeClient();
    const h = await bearer({ uid: "u1" });
    await api.json("POST", "/api/bench/1/comments", { body: "hide me" }, h);
    await env.DB.prepare("UPDATE comments SET state = 'hidden'").run();
    const { items } = (await (await api.request("/api/feed")).json()) as { items: unknown[] };
    expect(items).toEqual([]);
  });
});
