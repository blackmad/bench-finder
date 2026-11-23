import { beforeEach, describe, expect, it } from "vitest";
import { ADMIN_UID, bearer, makeClient, named, PNG, resetDb } from "./helpers";

beforeEach(resetDb);

const post = (api: ReturnType<typeof makeClient>, h: Record<string, string>, body: Uint8Array = PNG) =>
  api.request("/api/bench/7/photos?w=800&h=600", {
    method: "POST",
    headers: { ...h, "Content-Type": "image/png" },
    body,
  });

describe("bench photos", () => {
  it("need a username; stay pending (seen by the uploader only) until a moderator approves", async () => {
    const api = makeClient();
    const u = await bearer({ uid: "u1" });
    const other = await bearer({ uid: "u2" });
    const admin = await bearer({ uid: ADMIN_UID });

    expect((await post(api, {})).status).toBe(401);
    expect((await post(api, u)).status).toBe(428);
    await named(["u1", "bankje"]);
    const res = await post(api, u);
    expect(res.status).toBe(201);
    const { id } = (await res.json()) as { id: number };

    type List = { photos: { id: number; path: string; who: string; state: string; mine: boolean }[] };
    const mine = (await (await api.request("/api/bench/7/photos", { headers: u })).json()) as List;
    expect(mine.photos).toEqual([expect.objectContaining({ id, who: "bankje", state: "pending", mine: true })]);
    const path = mine.photos[0].path;
    expect((await api.request(path, { headers: u })).status).toBe(200);
    expect((await api.request(path)).status).toBe(404);
    expect(((await (await api.request("/api/bench/7/photos", { headers: other })).json()) as List).photos).toEqual([]);

    expect((await api.request("/api/admin/bench-photos", { headers: other })).status).toBe(403);
    const queue = (await (await api.request("/api/admin/bench-photos", { headers: admin })).json()) as {
      photos: { id: number; benchId: number }[];
    };
    expect(queue.photos).toEqual([expect.objectContaining({ id, benchId: 7 })]);
    expect((await api.json("POST", `/api/admin/bench-photos/${id}/approve`, undefined, admin)).status).toBe(200);

    expect(((await (await api.request("/api/bench/7/photos")).json()) as List).photos).toHaveLength(1);
    const pub = await api.request(path);
    expect(pub.status).toBe(200);
    expect(pub.headers.get("Content-Type")).toBe("image/png");

    expect((await api.json("DELETE", `/api/bench-photos/${id}`, undefined, other)).status).toBe(404);
    expect((await api.json("DELETE", `/api/bench-photos/${id}`, undefined, u)).status).toBe(200);
    expect((await api.request(path)).status).toBe(404);
  });

  it("rejects files that are not images", async () => {
    const api = makeClient();
    await named("u1");
    const res = await post(api, await bearer({ uid: "u1" }), new TextEncoder().encode("<html>"));
    expect(res.status).toBe(415);
  });
});
