import { describe, expect, it } from "vitest"
import { ApiError } from "./api"
import {
  registerUsernameAsker,
  suggestUsername,
  usernameProblem,
  withUsername,
} from "./username"

describe("username", () => {
  it("suggests one from the account name", () => {
    expect(suggestUsername("Ann de Vries")).toBe("ann-de-vries")
    expect(suggestUsername("Zoë")).toBe("zoe")
    expect(suggestUsername("Al")).toBe("")
    expect(suggestUsername(null)).toBe("")
  })
  it("checks the worker's rule", () => {
    expect(usernameProblem("bankje")).toBeNull()
    expect(usernameProblem("-no")).not.toBeNull()
    expect(usernameProblem("ab")).not.toBeNull()
  })
  it("asks on 428 and posts again", async () => {
    let calls = 0
    registerUsernameAsker((resolve) => resolve(true))
    const out = await withUsername(async () => {
      calls++
      if (calls === 1) throw new ApiError("Choose a username first", 428)
      return "ok"
    })
    expect([out, calls]).toEqual(["ok", 2])
  })
  it("gives up if they cancel", async () => {
    registerUsernameAsker((resolve) => resolve(false))
    await expect(
      withUsername(async () => {
        throw new ApiError("Choose a username first", 428)
      })
    ).rejects.toMatchObject({ status: 428 })
    registerUsernameAsker(null)
  })
})
