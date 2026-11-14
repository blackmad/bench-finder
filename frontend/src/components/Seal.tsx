import { facingKind } from "../data/facing"
import type { BenchProps } from "../data/types"
import { stampTitle } from "./postmark/Stamp"

type FacingProps = Pick<
  BenchProps,
  "facing" | "facing_method" | "facing_confidence"
>

const R = 15
const TICKS = Array.from({ length: 8 }, (_, i) => {
  const a = (i * 45 * Math.PI) / 180
  const l = i % 2 ? 1.8 : 3
  return {
    x1: Math.sin(a) * R,
    y1: -Math.cos(a) * R,
    x2: Math.sin(a) * (R - l),
    y2: -Math.cos(a) * (R - l),
  }
})

/**
 * The stamp simplified to a round postmark-compass that sits on a photo.
 * Solid ink needle: mapped facing. Dashed airmail needle: estimated.
 * Vermilion: the selected bench. No facing, no seal: nothing is drawn.
 */
export function Seal({
  bench,
  size = 38,
  selected = false,
}: {
  bench: FacingProps
  size?: number
  selected?: boolean
}) {
  const kind = facingKind(bench)
  if (kind === null || bench.facing === null) return null
  const col = selected
    ? "var(--color-vermilion)"
    : kind === "mapped"
      ? "var(--color-ink)"
      : "var(--color-airmail)"
  const label = stampTitle(bench)
  return (
    <svg
      className="seal"
      viewBox="-19 -19 38 38"
      width={size}
      height={size}
      role="img"
      aria-label={label}
    >
      <title>{label}</title>
      <circle r="18" fill="var(--color-stamp-paper)" />
      <circle r={R} fill="none" stroke="var(--color-ink)" strokeWidth=".8" />
      <g stroke="var(--color-ink)" strokeWidth=".8">
        {TICKS.map((t) => (
          <line key={`${t.x1}`} {...t} />
        ))}
      </g>
      <text
        y="-8.4"
        textAnchor="middle"
        fontSize="4.8"
        fontWeight="800"
        fontFamily="Archivo Variable, sans-serif"
        fill="var(--color-ink)"
      >
        N
      </text>
      <g
        transform={`rotate(${bench.facing})`}
        stroke={col}
        fill="none"
        strokeLinecap="round"
      >
        {kind === "mapped" ? (
          <>
            <line y1="5" y2="-8" strokeWidth="2" />
            <path d="M0 -12.5 l-3.6 5.6 h7.2z" fill={col} stroke="none" />
          </>
        ) : (
          <>
            <line y1="5" y2="-7.5" strokeWidth="1.3" strokeDasharray="2 1.6" />
            <path
              d="M0 -12.5 l-3.4 5.4 h6.8z"
              fill="var(--color-stamp-paper)"
              strokeWidth="1.2"
            />
          </>
        )}
        <circle r="1.9" fill={col} stroke="none" />
      </g>
    </svg>
  )
}
