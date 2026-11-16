import { Link } from "react-router-dom"
import { TopBar } from "../components/TopBar"
import { useBenchIndex } from "../data/hooks"
import { useMe } from "../data/social"
import type { BenchFeature } from "../data/types"
import { useAuth } from "../lib/auth"

const H1 =
  "mb-3 text-[clamp(30px,3.1vw,42px)] leading-[1.02] font-[750] tracking-[-0.015em] [font-variation-settings:'wdth'_112]"

export default function MePage() {
  const { user, ready, openSignIn, signOut } = useAuth()
  const { data: me, isPending, error } = useMe()
  // Saved ids may be any bench in a place, not just its leader.
  const byId = useBenchIndex()

  return (
    <>
      <TopBar />
      <main className="mx-auto max-w-[1240px] px-4 py-10 md:px-8">
        <h1 className={H1}>Your benches</h1>
        {!ready ? null : !user ? (
          <div className="stack me-intro">
            <p className="max-w-[44ch] text-[16.5px] text-ink-2">
              Sign in to keep a list of the benches you have sat on and the ones
              you want to visit. The map and every bench page stay open without
              an account.
            </p>
            <div>
              <button
                type="button"
                className="btn primary"
                onClick={openSignIn}
              >
                Sign in
              </button>
            </div>
          </div>
        ) : (
          <>
            <p className="me-who">
              Signed in as {user.name ?? user.email ?? "you"}.{" "}
              <button type="button" className="linkbtn" onClick={signOut}>
                Sign out
              </button>
              {me?.isAdmin ? (
                <>
                  {" "}
                  <Link to="/admin">Open moderation</Link>
                </>
              ) : null}
            </p>
            {isPending ? (
              <p className="state">Loading your lists...</p>
            ) : error || !me ? (
              <p role="alert" className="state">
                Could not load your lists: {error?.message}
              </p>
            ) : (
              <div className="me-lists">
                <BenchList
                  title="Favourites"
                  empty="Tick Favourite on a bench page and it lands here."
                  ids={me.favorites}
                  byId={byId}
                />
                <BenchList
                  title="Sat here"
                  empty="Benches you mark as visited show up here."
                  ids={me.visited}
                  byId={byId}
                />
                <BenchList
                  title="Rated"
                  empty="Give a bench some stars and it is listed here."
                  ids={me.ratings.map((r) => r.benchId)}
                  stars={Object.fromEntries(
                    me.ratings.map((r) => [r.benchId, r.rating])
                  )}
                  byId={byId}
                />
              </div>
            )}
          </>
        )}
      </main>
    </>
  )
}

function BenchList({
  title,
  empty,
  ids,
  stars,
  byId,
}: {
  title: string
  empty: string
  ids: number[]
  stars?: Record<number, number>
  byId: Map<number, BenchFeature>
}) {
  return (
    <section className="block" aria-label={title}>
      <div className="blockhead">
        <h2>{title}</h2>
        <p>{ids.length}</p>
      </div>
      {ids.length === 0 ? (
        <p className="hint">{empty}</p>
      ) : (
        <ul className="me-list">
          {ids.map((id) => {
            const p = byId.get(id)?.properties
            return (
              <li key={id}>
                <Link to={`/bench/${id}`}>
                  <span className="caps">{p?.address ?? "Unnamed path"}</span>
                  <span className="serial">No.&nbsp;{id}</span>
                </Link>
                {stars?.[id] ? (
                  <span
                    className="mestars"
                    role="img"
                    aria-label={`${stars[id]} of 5`}
                  >
                    {"★".repeat(stars[id])}
                    <span aria-hidden="true">{"★".repeat(5 - stars[id])}</span>
                  </span>
                ) : null}
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
