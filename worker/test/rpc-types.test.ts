import { hc } from "hono/client";
import { expect, it } from "vitest";
import type { AppType } from "../src/index";

// Compile-time check (via `tsc --noEmit`) that the exported app type supports hono/client RPC.
it("exposes a typed client", () => {
  const client = hc<AppType>("http://localhost:8787");
  const social = client.api.bench[":id"].social.$get;
  const rate = client.api.bench[":id"].rating.$put;
  expect(typeof social).toBe("function");
  expect(typeof rate).toBe("function");
  void (() => rate({ param: { id: "1" }, json: { rating: 5 } }));
});
