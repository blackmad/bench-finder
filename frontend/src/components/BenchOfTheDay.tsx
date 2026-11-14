import { Link } from "react-router-dom"
import { headline, lede, seatText } from "../data/describe"
import { facingKind, facingShort } from "../data/facing"
import { useBench } from "../data/hooks"
import { useSocial } from "../data/social"
import type { BenchProps } from "../data/types"
import { Photo } from "./Photo"
import { Seal } from "./Seal"

/**
 * The hero: one photographed bench a day, its photo full width with a paper
 * title card over the bottom edge. The headline is the address; the lede is
 * assembled from the bench's own map data and nothing else.
 */
export function BenchOfTheDay({ bench }: { bench: BenchProps }) {
  const { data: detail } = useBench(bench.id)
  const { data: social } = useSocial(bench.id)
  const name = headline(bench)
  const facing = facingShort(bench)
  const kind = facingKind(bench)
  const seat = seatText(bench.backrest)
  const ratings = social?.ratings
  return (
    <Link className="feature" to={`/bench/${bench.id}`}>
      <div className="ph">
        <Photo
          urls={bench.hero_urls}
          webp={bench.hero_urls_webp}
          sizes="(max-width: 760px) 100vw, 58vw"
          alt={`Street view of the bench at ${name}`}
          width={bench.hero_width ?? 800}
          height={bench.hero_height ?? 800}
          fetchPriority="high"
          decoding="async"
        />
        <span className="sealslot">
          <Seal bench={bench} size={64} />
        </span>
      </div>
      <div className="titlecard">
        <p className="kicker caps">Bench of the day</p>
        <h2>{name}</h2>
        <p className="lede">{detail ? lede(detail) : " "}</p>
        <p className="facts">
          {facing ? (
            <span className={kind === "estimated" ? "est" : undefined}>
              <b className="num">{facing}</b>{" "}
              {kind === "mapped" ? "mapped" : "estimated"}
            </span>
          ) : null}
          {seat ? (
            <span>
              <b>{seat}</b>
            </span>
          ) : null}
          {ratings && ratings.count > 0 && ratings.average != null ? (
            <span>
              <b className="num">{ratings.average.toFixed(1)}</b> from{" "}
              {ratings.count} {ratings.count === 1 ? "rating" : "ratings"}
            </span>
          ) : null}
        </p>
      </div>
    </Link>
  )
}
