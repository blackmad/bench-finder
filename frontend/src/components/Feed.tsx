import { useState } from "react"
import { Link } from "react-router-dom"
import { headline } from "../data/describe"
import { useBenchIndex } from "../data/hooks"
import { type FeedItem, useFeed } from "../data/social"
import type { BenchFeature } from "../data/types"
import { timeAgo } from "../lib/timeAgo"

/** Recent notes, ratings and public favourites, across the whole map. */
export function Feed({ onOpen }: { onOpen: (id: number) => void }) {
  const { data } = useFeed()
  // Any bench, not just the photographed place leaders on the map.
  const byId = useBenchIndex()
  // Benches the current data no longer has (hidden since) are left out.
  const [more, setMore] = useState(false)
  const all = (data?.items ?? []).filter((i) => byId.has(i.benchId))
  const items = all.slice(0, more ? 12 : 4)
  if (!items.length) return null
  return (
    <section className="feed" aria-labelledby="h-feed">
      <h2 id="h-feed" className="caps">
        Lately on Bench Finder
      </h2>
      <ul>
        {items.map((i) => (
          <li key={i.key}>
            <FeedLine
              item={i}
              name={headline((byId.get(i.benchId) as BenchFeature).properties)}
              onOpen={onOpen}
            />
            <time dateTime={i.at}>{timeAgo(i.at)}</time>
          </li>
        ))}
      </ul>
      {all.length > 4 ? (
        <button
          type="button"
          className="linkbtn feedmore"
          aria-expanded={more}
          onClick={() => setMore((m) => !m)}
        >
          {more ? "Less" : "More"}
        </button>
      ) : null}
    </section>
  )
}

function FeedLine({
  item: i,
  name,
  onOpen,
}: {
  item: FeedItem
  name: string
  onOpen: (id: number) => void
}) {
  const bench = (
    <button type="button" className="linkbtn" onClick={() => onOpen(i.benchId)}>
      {name}
    </button>
  )
  if (i.kind === "note") {
    return (
      <p>
        <b>{i.who}</b>{" "}
        {i.rating ? (
          <>
            <span role="img" aria-label={`${i.rating} of 5 stars`}>
              {"★".repeat(i.rating)}
            </span>{" "}
          </>
        ) : null}
        on {bench}: <q>{i.text}</q>
      </p>
    )
  }
  if (i.kind === "rating") {
    return (
      <p>
        {i.who ? (
          <>
            <b>{i.who}</b> gave {bench}{" "}
          </>
        ) : (
          <>{bench} got </>
        )}
        <span role="img" aria-label={`${i.rating} of 5 stars`}>
          {"★".repeat(i.rating)}
        </span>
      </p>
    )
  }
  return (
    <p>
      <Link to={`/u/${i.page}`}>
        <b>{i.who}</b>
      </Link>{" "}
      added {bench} to their favourites
    </p>
  )
}
