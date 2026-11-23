import { ApiError } from "./api"

/**
 * Posting needs a username (the worker answers 428 without one). `withUsername`
 * runs a post; on 428 it asks for a username via the dialog mounted in App,
 * then sends the post again once.
 */
type Ask = (resolve: (ok: boolean) => void) => void
let asker: Ask | null = null

export function registerUsernameAsker(fn: Ask | null) {
  asker = fn
}

export function askUsername(): Promise<boolean> {
  return new Promise((resolve) => (asker ? asker(resolve) : resolve(false)))
}

export async function withUsername<T>(post: () => Promise<T>): Promise<T> {
  try {
    return await post()
  } catch (e) {
    if (!(e instanceof ApiError) || e.status !== 428) throw e
    if (!(await askUsername()))
      throw new ApiError("Choose a username to post", 428)
    return post()
  }
}

/** The worker's rule, so the form can say what's wrong before sending. */
export function usernameProblem(h: string): string | null {
  return /^[a-z0-9][a-z0-9_-]{2,23}$/.test(h)
    ? null
    : "Use 3-24 letters, numbers, - or _ (starting with a letter or number)"
}

/** A starting suggestion from the account name: "Ann de Vries" -> "ann-de-vries". */
export function suggestUsername(name: string | null | undefined): string {
  const s = (name ?? "")
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 24)
  return s.length >= 3 ? s : ""
}
