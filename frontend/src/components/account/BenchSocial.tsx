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
import { ReportBenchDialog } from "./ReportDialogs"

/** The public score under the bench's title: average rating, counts, and a
 * link down to the notes. Quiet until someone has rated or written. */
export function BenchScore({ benchId }: { benchId: number }) {
  const { data } = useSocial(benchId)
  if (!data) return <p className="score" />
  const { count, average } = data.ratings
  const notes = data.comments.length
  return (
    <p className="score">
      {count > 0 && average != null ? (
        <span className="score-avg">
          <StarIcon />
          <b>{average.toFixed(1)}</b>
          <span>
            {count} {count === 1 ? "rating" : "ratings"}
          </span>
        </span>
      ) : (
        <span>Not rated yet</span>
      )}
      <a href="#h-notes">
        {notes === 0
          ? "No notes yet"
          : `${notes} ${notes === 1 ? "note" : "notes"}`}
      </a>
    </p>
  )
}

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
              // Clicking your current rating again clears it.
              onClick={() => (mine === n ? rate.mutate(null) : undefined)}
            />
            <StarIcon />
            <span className="sr">{n === 1 ? "1 star" : `${n} stars`}</span>
          </label>
        ))}
        <span id="rating-summary" className="rating-summary">
          <span>
            {mine ? `Your rating: ${mine}` : "Your rating"}
            {mine ? (
              <>
                {" · "}
                <button
                  type="button"
                  className="linkbtn"
                  onClick={() => rate.mutate(null)}
                >
                  Clear
                </button>
              </>
            ) : null}
          </span>
          <span>
            {count > 0 && avg != null
              ? `Average ${avg.toFixed(1)} from ${count}`
              : "No ratings yet"}
          </span>
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
            ["want", "Want to sit here"],
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

/** Read-only stars, e.g. beside a note. */
export function Stars({ n }: { n: number }) {
  return (
    <span className="mestars" role="img" aria-label={`${n} of 5 stars`}>
      {"★".repeat(n)}
      <span aria-hidden="true">{"★".repeat(5 - n)}</span>
    </span>
  )
}

/** Five star radios that can be cleared again (clicking the chosen star). */

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
  const myRating = data?.me?.rating ?? null
  const [flagged, setFlagged] = useState<number[]>([])
  const comments = data?.comments ?? []

  const submit = (e: FormEvent) => {
    e.preventDefault()
    const text = body.trim()
    if (!text) return
    add.mutate(
      { body: text, ...(myRating ? { rating: myRating } : {}) },
      { onSuccess: () => setBody("") }
    )
  }

  return (
    <section className="block" aria-labelledby="h-notes">
      <div className="blockhead">
        <h2 id="h-notes">Notes</h2>
        <p>Public notes from people who sat here</p>
      </div>
      <div className={comments.length ? "notes" : "notes empty"}>
        <div>
          {isPending ? (
            <p>Loading notes...</p>
          ) : error ? (
            <p className="hint">Notes are unavailable right now.</p>
          ) : comments.length === 0 ? (
            <p className="hint">No notes yet. Be the first.</p>
          ) : (
            <ul className="comments">
              {comments.map((c) => (
                <li key={c.id}>
                  {c.rating ? <Stars n={c.rating} /> : null}
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
            <label htmlFor="note-body" className="sr">
              Add a note
            </label>
            <textarea
              id="note-body"
              rows={2}
              maxLength={2000}
              placeholder="Sat here? What's the light like, when is it quiet?"
              value={body}
              onChange={(e) => setBody(e.target.value)}
            />
            <div className="notes-send">
              <span className="hint">
                {myRating
                  ? "Your stars above show with your note."
                  : "Rate it above to show stars with your note."}
              </span>
              <button
                type="submit"
                className="btn primary"
                disabled={add.isPending || !body.trim()}
              >
                {add.isPending ? "Posting..." : "Post note"}
              </button>
            </div>
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
