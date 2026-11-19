import { type FormEvent, useState } from "react"
import {
  useAddComment,
  useDeleteComment,
  useFlagComment,
  useRate,
  useSetStatus,
  useSocial,
} from "../../data/social"
import { useAuth } from "../../lib/auth"
import { CheckTick } from "../Icons"
import { FlagIcon, StarIcon } from "./icons"
import { MissingBenchDialog, ReportBenchDialog } from "./ReportDialogs"

/** Rating + visited/favourite, mounted inside the bench card. */
export function BenchActions({ benchId }: { benchId: number }) {
  const { user, openSignIn } = useAuth()
  const { data } = useSocial(benchId)
  const rate = useRate(benchId)
  const status = useSetStatus(benchId)
  const [hover, setHover] = useState<number | null>(null)
  const mine = data?.me?.rating ?? null
  const shown = hover ?? mine ?? 0
  const avg = data?.ratings.average
  const count = data?.ratings.count ?? 0

  return (
    <div className="acts">
      <fieldset
        className="stars"
        onMouseLeave={() => setHover(null)}
        aria-describedby="rating-summary"
      >
        <legend className="sr">Rate this bench</legend>
        {[1, 2, 3, 4, 5].map((n) => (
          <label
            key={n}
            className={n <= shown ? "on" : undefined}
            onMouseEnter={() => setHover(n)}
          >
            <input
              type="radio"
              name={`rating-${benchId}`}
              value={n}
              checked={mine === n}
              onChange={() => (user ? rate.mutate(n) : openSignIn())}
            />
            <StarIcon />
            <span className="sr">{n === 1 ? "1 star" : `${n} stars`}</span>
          </label>
        ))}
        <span id="rating-summary" className="rating-summary">
          <span>
            {count > 0 && avg != null
              ? `${avg.toFixed(1)} · ${count} ${count === 1 ? "rating" : "ratings"}`
              : "No ratings yet"}
          </span>
          {mine ? <span>Yours: {mine}</span> : null}
        </span>
      </fieldset>
      {rate.error ? (
        <p role="alert" className="form-error">
          {rate.error.message}
        </p>
      ) : null}
      <div className="row">
        {(
          [
            ["visited", "I've sat here"],
            ["favorite", "Favourite"],
          ] as const
        ).map(([field, label]) => (
          <label key={field} className="check">
            <input
              type="checkbox"
              checked={data?.me?.[field] ?? false}
              onChange={(e) =>
                user
                  ? status.mutate({ [field]: e.target.checked })
                  : openSignIn()
              }
            />
            <span className="box">
              <CheckTick />
            </span>
            {label}
          </label>
        ))}
      </div>
      {user ? null : (
        <p className="hint">
          <button type="button" className="linkbtn" onClick={openSignIn}>
            Sign in
          </button>{" "}
          to rate this bench and keep your own lists.
        </p>
      )}
    </div>
  )
}

const when = (iso: string) =>
  new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  })

/** Public notes under the bench. */
export function BenchNotes({ benchId }: { benchId: number }) {
  const { user, openSignIn } = useAuth()
  const { data, isPending, error } = useSocial(benchId)
  const add = useAddComment(benchId)
  const del = useDeleteComment(benchId)
  const flag = useFlagComment()
  const [body, setBody] = useState("")
  const [flagged, setFlagged] = useState<number[]>([])
  const comments = data?.comments ?? []

  const submit = (e: FormEvent) => {
    e.preventDefault()
    const text = body.trim()
    if (!text) return
    add.mutate(text, { onSuccess: () => setBody("") })
  }

  return (
    <section className="block" aria-labelledby="h-notes">
      <div className="blockhead">
        <h2 id="h-notes">Notes</h2>
        <p>Public notes from people who sat here</p>
      </div>
      <div className="notes">
        <div>
          {isPending ? (
            <p>Loading notes...</p>
          ) : error ? (
            <p className="hint">Notes are unavailable right now.</p>
          ) : comments.length === 0 ? (
            <p>
              <strong>No notes yet.</strong>
              Sat here? Say what the light is like, or when it's quiet.
            </p>
          ) : (
            <ul className="comments">
              {comments.map((c) => (
                <li key={c.id}>
                  <p className="cbody">{c.body}</p>
                  <p className="cmeta">
                    {c.displayName} · {when(c.createdAt)}
                    {c.mine ? (
                      <button
                        type="button"
                        className="linkbtn"
                        onClick={() => del.mutate(c.id)}
                      >
                        Delete
                      </button>
                    ) : user ? (
                      flagged.includes(c.id) ? (
                        <span>Flagged, thanks</span>
                      ) : (
                        <button
                          type="button"
                          className="linkbtn"
                          onClick={() =>
                            flag.mutate(c.id, {
                              onSuccess: () => setFlagged((f) => [...f, c.id]),
                            })
                          }
                        >
                          Flag
                        </button>
                      )
                    ) : null}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </div>
        {user ? (
          <form className="stack notes-form" onSubmit={submit}>
            <label htmlFor="note-body" className="caps">
              Add a note
            </label>
            <textarea
              id="note-body"
              rows={3}
              maxLength={2000}
              value={body}
              onChange={(e) => setBody(e.target.value)}
            />
            <button
              type="submit"
              className="btn primary"
              disabled={add.isPending || !body.trim()}
            >
              {add.isPending ? "Posting..." : "Post note"}
            </button>
            {add.error ? (
              <p role="alert" className="form-error">
                {add.error.message}
              </p>
            ) : null}
          </form>
        ) : (
          <button type="button" className="btn" onClick={openSignIn}>
            Sign in to write a note
          </button>
        )}
      </div>
    </section>
  )
}

/** "Report this bench" row + its dialog. Missing benches are reported from the map. */
export function ReportRow({ benchId }: { benchId: number }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <div className="report">
        <FlagIcon />
        <span>Wrong bench, wrong facing, or no bench at all?</span>
        <button type="button" onClick={() => setOpen(true)}>
          Report this bench
        </button>
      </div>
      {open ? (
        <ReportBenchDialog benchId={benchId} onClose={() => setOpen(false)} />
      ) : null}
    </>
  )
}
