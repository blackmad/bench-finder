import { describe, expect, it } from "vitest"
import { timeAgo } from "./timeAgo"

const NOW = Date.parse("2026-11-22T12:00:00Z")
const ago = (s: number) => new Date(NOW - s * 1000).toISOString()

describe("timeAgo", () => {
  it("steps from seconds to days", () => {
    expect(timeAgo(ago(5), NOW)).toBe("just now")
    expect(timeAgo(ago(5 * 60), NOW)).toBe("5 min ago")
    expect(timeAgo(ago(3 * 3600), NOW)).toBe("3 h ago")
    expect(timeAgo(ago(86400 + 60), NOW)).toBe("yesterday")
    expect(timeAgo(ago(3 * 86400), NOW)).toBe("3 days ago")
  })
  it("clock skew (a future time) reads as just now", () => {
    expect(timeAgo(ago(-30), NOW)).toBe("just now")
  })
})
