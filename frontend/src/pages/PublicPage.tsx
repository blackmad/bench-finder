import { Link, useParams } from "react-router-dom"
import { Photo } from "../components/Photo"
import { TopBar } from "../components/TopBar"
import { focusStyle } from "../data/api"
import { headline } from "../data/describe"
import { useBenchIndex } from "../data/hooks"
import { usePublicPage } from "../data/social"
import type { BenchFeature } from "../data/types"

const TOP = 3

/** Someone's public favourites: their top three as cards, then the rest. */
export default function PublicPage() {
  const { key = "" } = useParams()
  const { data, isPending, error } = usePublicPage(key)
  const byId = useBenchIndex()
  const benches = (data?.favorites ?? [])
    .map((id) => ({ id, f: byId.get(id) }))
    .filter((b): b is { id: number; f: BenchFeature } => Boolean(b.f))
  const title = data
    ? `${data.displayName}'s favourite benches`
    : "Favourite benches"
  if (data) document.title = `${title} · Bench Finder`

  return (
    <>
      <TopBar />
      <main className="mx-auto max-w-[1240px] px-4 py-10 md:px-8 pub">
        <h1 className="pubtitle">{title}</h1>
        {isPending ? (
          <p className="state">Loading...</p>
        ) : error || !data ? (
          <p className="state">
            There is no public page here. It may have been made private.{" "}
            <Link to="/">Find benches on the map</Link>
          </p>
        ) : benches.length === 0 ? (
          <p className="state">No favourites yet.</p>
        ) : (
          <>
            <ol className="pubtop">
              {benches.slice(0, TOP).map(({ id, f }, i) => (
                <li key={id}>
                  <Link to={`/?bench=${id}`}>
                    <span className="pubrank num">{i + 1}</span>
                    {f.properties.hero_urls ? (
                      <Photo
                        urls={f.properties.hero_urls}
                        webp={f.properties.hero_urls_webp}
                        sizes="(max-width: 760px) 100vw, 400px"
                        alt={`The bench at ${headline(f.properties)}`}
                        width={400}
                        height={300}
                        style={focusStyle(f.properties.hero_focus)}
                        loading="lazy"
                      />
                    ) : (
                      <span className="pubnophoto" />
                    )}
                    <span className="pubname">{headline(f.properties)}</span>
                  </Link>
                </li>
              ))}
            </ol>
            {benches.length > TOP ? (
              <ol className="me-list pubrest" start={TOP + 1}>
                {benches.slice(TOP).map(({ id, f }, i) => (
                  <li key={id}>
                    <span className="rank num">{i + TOP + 1}</span>
                    <Link to={`/?bench=${id}`}>
                      <span className="caps">{headline(f.properties)}</span>
                      <span className="serial">No.&nbsp;{id}</span>
                    </Link>
                  </li>
                ))}
              </ol>
            ) : null}
            <p className="pubfoot">
              <Link to="/me">Make your own list</Link> on Bench Finder.
            </p>
          </>
        )}
      </main>
    </>
  )
}
