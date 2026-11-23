import { beforeEach, describe, expect, it } from "vitest";
import { ADMIN_UID, bearer, named, makeClient, resetDb } from "./helpers";

beforeEach(resetDb);

const photo = (key: string) => ({
  urls: { "400": `img/${key}-400.avif`, "800": `img/${key}-800.avif` },
  urls_webp: { "400": `img/${key}-400.webp` },
  width: 800,
  height: 800,
});
const A = "a78e32b62970c9c5";
const B = "12276b213fb43d16";

type Picks = { picks: Record<string, { imageId: number; key: string; urls: Record<string, string> }> };

describe("lead photo picks", () => {
  it("a moderator's pick shows at once; clearing it goes back to automatic", async () => {
    const api = makeClient();
    const admin = await bearer({ uid: ADMIN_UID });
    expect((await api.json("PUT", "/api/admin/bench/2160/hero", { imageId: 54438, photo: photo(A) }, admin)).status).toBe(200);
    let res = await api.request("/api/heroes");
    expect(res.headers.get("Cache-Control")).toContain("max-age");
    let { picks } = (await res.json()) as Picks;
    expect(picks["2160"]).toMatchObject({ imageId: 54438, key: A, urls: { "800": `img/${A}-800.avif` } });
    // Re-picking replaces.
    await api.json("PUT", "/api/admin/bench/2160/hero", { imageId: 54437, photo: photo(B) }, admin);
    ({ picks } = (await (await api.request("/api/heroes")).json()) as Picks);
    expect(picks["2160"].key).toBe(B);
    await api.request("/api/admin/bench/2160/hero", { method: "DELETE", headers: admin });
    ({ picks } = (await (await api.request("/api/heroes")).json()) as Picks);
    expect(picks).toEqual({});
  });

  it("only moderators pick; photos must be published renditions of one image", async () => {
    const api = makeClient();
    const user = await bearer({ uid: "u1" });
    const admin = await bearer({ uid: ADMIN_UID });
    expect((await api.json("PUT", "/api/admin/bench/1/hero", { imageId: 1, photo: photo(A) }, user)).status).toBe(403);
    expect((await api.json("PUT", "/api/admin/bench/1/hero", { imageId: 1, photo: photo(A) })).status).toBe(401);
    const bad = [
      { ...photo(A), urls: { "800": "https://evil.example/x.avif" } },
      { ...photo(A), urls_webp: { "400": `img/${B}-400.webp` } }, // two different images
      { ...photo(A), urls: {} },
    ];
    for (const p of bad) {
      expect((await api.json("PUT", "/api/admin/bench/1/hero", { imageId: 1, photo: p }, admin)).status).toBe(400);
    }
  });
});

describe("suggestions", () => {
  it("visitors suggest, moderators accept (others on the bench close) or dismiss", async () => {
    const api = makeClient();
    const u1 = await bearer({ uid: "u1", name: "Uma" });
    const u2 = await bearer({ uid: "u2", name: "Ugo" });
    await named(["u1", "uma"], ["u2", "ugo"]);
    const admin = await bearer({ uid: ADMIN_UID });
    expect((await api.json("POST", "/api/bench/2160/hero-suggestions", { imageId: 54438, photo: photo(A) })).status).toBe(401);
    expect((await api.json("POST", "/api/bench/2160/hero-suggestions", { imageId: 54438, photo: photo(A) }, u1)).status).toBe(201);
    expect((await api.json("POST", "/api/bench/2160/hero-suggestions", { imageId: 54437, photo: photo(B) }, u2)).status).toBe(201);
    expect((await api.json("POST", "/api/bench/7/hero-suggestions", { imageId: 9, photo: photo(B) }, u2)).status).toBe(201);
    // Same person, same photo: still one suggestion.
    await api.json("POST", "/api/bench/2160/hero-suggestions", { imageId: 54438, photo: photo(A) }, u1);

    expect((await api.request("/api/admin/hero-suggestions", { headers: u1 })).status).toBe(403);
    type S = { suggestions: { id: number; benchId: number; imageId: number; who: string }[] };
    let { suggestions } = (await (await api.request("/api/admin/hero-suggestions", { headers: admin })).json()) as S;
    expect(suggestions).toHaveLength(3);
    const uma = suggestions.find((s) => s.who === "uma");
    expect((await api.request(`/api/admin/hero-suggestions/${uma?.id}/accept`, { method: "POST", headers: admin })).status).toBe(200);

    ({ suggestions } = (await (await api.request("/api/admin/hero-suggestions", { headers: admin })).json()) as S);
    expect(suggestions.map((s) => s.benchId)).toEqual([7]); // Ugo's 2160 suggestion closed with it
    const { picks } = (await (await api.request("/api/heroes")).json()) as Picks;
    expect(picks["2160"].imageId).toBe(54438);

    await api.request(`/api/admin/hero-suggestions/${suggestions[0].id}/dismiss`, { method: "POST", headers: admin });
    ({ suggestions } = (await (await api.request("/api/admin/hero-suggestions", { headers: admin })).json()) as S);
    expect(suggestions).toEqual([]);
    expect((await api.request(`/api/admin/hero-suggestions/${uma?.id}/accept`, { method: "POST", headers: admin })).status).toBe(404);
  });
});

describe("view suggestions", () => {
  it("signed-in people suggest a Street View camera; moderators list and dismiss", async () => {
    const api = makeClient();
    const u = await bearer({ uid: "u1", name: "Uma" });
    await named(["u1", "uma"]);
    const admin = await bearer({ uid: ADMIN_UID });
    const view = { panoId: "_p0Cvw_lTj8_9BX1KvXN_Q", heading: -191, pitch: -4, fov: 75 };
    expect((await api.json("POST", "/api/bench/1743/view-suggestions", view)).status).toBe(401);
    expect((await api.json("POST", "/api/bench/1743/view-suggestions", view, u)).status).toBe(201);
    for (const bad of [{ ...view, panoId: "x" }, { ...view, pitch: 120 }, { ...view, fov: 2 }]) {
      expect((await api.json("POST", "/api/bench/1743/view-suggestions", bad, u)).status).toBe(400);
    }
    expect((await api.request("/api/admin/view-suggestions", { headers: u })).status).toBe(403);
    type V = { views: { id: number; benchId: number; heading: number; who: string; state: string }[] };
    let { views } = (await (await api.request("/api/admin/view-suggestions", { headers: admin })).json()) as V;
    expect(views).toEqual([expect.objectContaining({ benchId: 1743, heading: 169, who: "uma", state: "pending" })]);
    await api.request(`/api/admin/view-suggestions/${views[0].id}/dismiss`, { method: "POST", headers: admin });
    ({ views } = (await (await api.request("/api/admin/view-suggestions", { headers: admin })).json()) as V);
    expect(views).toEqual([]);
  });
});
