import { useId } from "react"
import { isKnown, windName } from "../../data/facing"
import type { BenchProps } from "../../data/types"

const W = 74
const H = 88
const HOLE_R = 2.4
const STEP = 7.4
const CX = 37
const CY = 37
const RING = 21

type FacingProps = Pick<
  BenchProps,
  "facing" | "facing_method" | "facing_confidence"
>

interface StampProps {
  bench: FacingProps
  selected?: boolean
  large?: boolean
  /** Decorative copies (e.g. the small stamp on the address side). */
  decorative?: boolean
}

const range = (from: number, to: number, step: number): number[] => {
  const out: number[] = []
  for (let v = from; v < to; v += step) out.push(v)
  return out
}

const PERFORATIONS = [
  ...range(STEP / 2, W, STEP).flatMap((x) => [
    { cx: x, cy: 0 },
    { cx: x, cy: H },
  ]),
  ...range(STEP / 2, H, STEP).flatMap((y) => [
    { cx: 0, cy: y },
    { cx: W, cy: y },
  ]),
]

const TICKS = Array.from({ length: 16 }, (_, i) => {
  const a = (i * 22.5 * Math.PI) / 180
  const len = i % 4 === 0 ? 4 : 2
  return {
    x1: CX + Math.sin(a) * RING,
    y1: CY - Math.cos(a) * RING,
    x2: CX + Math.sin(a) * (RING - len),
    y2: CY - Math.cos(a) * (RING - len),
  }
})

export function stampTitle(bench: FacingProps): string {
  if (bench.facing === null) return "Facing direction not known yet"
  const w = windName(bench.facing)
  if (isKnown(bench)) {
    return bench.facing_method === "human"
      ? `Faces ${w} (${bench.facing}°), confirmed by a visitor`
      : `Faces ${w} (${bench.facing}°), from the OpenStreetMap direction tag`
  }
  const pct = Math.round((bench.facing_confidence ?? 0) * 100)
  return `Probably faces ${w} (${bench.facing}°), estimated with ${pct}% confidence`
}

/**
 * A perforated postage stamp whose printed face is a compass, cancelled by a
 * postmark ring. Known facing: solid ink arrow. Estimated: dashed airmail
 * hairline arrow. Selected: vermilion, with the strike animation.
 */
export function Stamp({
  bench,
  selected = false,
  large = false,
  decorative = false,
}: StampProps) {
  const uid = useId().replace(/[^a-zA-Z0-9]/g, "")
  const maskId = `${uid}m`
  const known = isKnown(bench)
  const facing = bench.facing
  const accent = selected
    ? "var(--color-vermilion)"
    : known
      ? "var(--color-ink)"
      : "var(--color-airmail)"
  const title = stampTitle(bench)
  const label =
    facing === null
      ? "No facing"
      : known
        ? `${windName(facing)} ${facing}°`
        : `≈ ${windName(facing)}`

  return (
    <svg
      className={`stamp${large ? " lg" : ""}${selected ? " stamping" : ""}`}
      viewBox={`0 0 ${W} ${H}`}
      overflow="visible"
      role={decorative ? undefined : "img"}
      aria-label={decorative ? undefined : title}
      aria-hidden={decorative || undefined}
    >
      {decorative ? null : <title>{title}</title>}
      <defs>
        <mask id={maskId}>
          <rect width={W} height={H} fill="#fff" />
          <g fill="#000">
            {PERFORATIONS.map((p) => (
              <circle key={`${p.cx}-${p.cy}`} cx={p.cx} cy={p.cy} r={HOLE_R} />
            ))}
          </g>
        </mask>
      </defs>
      <rect
        width={W}
        height={H}
        fill="var(--color-stamp-paper)"
        mask={`url(#${maskId})`}
      />
      <rect
        x={5.5}
        y={5.5}
        width={W - 11}
        height={H - 11}
        fill="none"
        stroke="var(--color-ink)"
        strokeWidth={0.7}
      />
      <circle
        cx={CX}
        cy={CY}
        r={RING}
        fill="none"
        stroke="var(--color-ink)"
        strokeWidth={0.8}
      />
      <g stroke="var(--color-ink)" strokeWidth={0.8}>
        {TICKS.map((t) => (
          <line key={`${t.x1}-${t.y1}`} {...t} />
        ))}
      </g>
      <text
        x={CX}
        y={CY - RING - 3.2}
        textAnchor="middle"
        fontSize={6.2}
        fontWeight={800}
        fontFamily="Archivo Variable, sans-serif"
        style={{ fontVariationSettings: "'wdth' 125" }}
        fill="var(--color-ink)"
      >
        N
      </text>
      {facing === null ? null : (
        <Arrow facing={facing} known={known} accent={accent} />
      )}
      <text
        x={CX}
        y={76}
        textAnchor="middle"
        fontSize={8.6}
        fontWeight={700}
        fontFamily="Archivo Variable, sans-serif"
        style={{
          fontVariationSettings: "'wdth' 118",
          fontVariantNumeric: "tabular-nums",
        }}
        fill={known || selected ? accent : "var(--color-ink)"}
      >
        {label}
      </text>
      {facing === null ? null : (
        <Postmark facing={facing} known={known} selected={selected} uid={uid} />
      )}
    </svg>
  )
}

function Arrow({
  facing,
  known,
  accent,
}: {
  facing: number
  known: boolean
  accent: string
}) {
  const t = `rotate(${facing} ${CX} ${CY})`
  if (known) {
    return (
      <g transform={t} stroke={accent} fill={accent}>
        <line x1={CX} y1={CY + 9} x2={CX} y2={CY - 12} strokeWidth={2.2} />
        <path d={`M${CX} ${CY - 18} l-5 8 h10z`} stroke="none" />
        <circle cx={CX} cy={CY} r={2.4} stroke="none" />
      </g>
    )
  }
  return (
    <g transform={t} stroke={accent} fill="none">
      <line
        x1={CX}
        y1={CY + 9}
        x2={CX}
        y2={CY - 11}
        strokeWidth={1.1}
        strokeDasharray="2.4 2"
      />
      <path d={`M${CX} ${CY - 18} l-4.5 7.5 h9z`} strokeWidth={1.1} />
      <circle cx={CX} cy={CY} r={2} strokeWidth={1.1} />
    </g>
  )
}

/** The cancellation carries the facing: arc text names it, bars run along it. */
function Postmark({
  facing,
  known,
  selected,
  uid,
}: {
  facing: number
  known: boolean
  selected: boolean
  uid: string
}) {
  const ink = selected ? "var(--color-vermilion)" : "var(--color-ink)"
  const x = 4
  const y = 78
  const r = 15
  const sw = known ? 0.95 : 0.6
  const pathId = `${uid}t`
  const arcText = `${known ? "" : "≈ "}${windName(facing)} · ${facing}°`
  const rot = `rotate(${facing} ${x} ${y})`
  return (
    <g
      opacity={0.78}
      stroke={ink}
      fill="none"
      strokeWidth={sw}
      strokeDasharray={known ? undefined : "1.6 1.4"}
    >
      <g transform={rot}>
        {[-4.5, 0, 4.5].map((o) => (
          <path
            key={o}
            d={`M${x + o} ${y - r - 2} q -2 -3.5 0 -7 t 0 -7 t 0 -7`}
          />
        ))}
      </g>
      <circle cx={x} cy={y} r={r} fill="rgb(251 251 247 / .55)" />
      <circle cx={x} cy={y} r={r - 4.6} />
      <path
        id={pathId}
        d={`M${x - r + 2.3} ${y} a ${r - 2.3} ${r - 2.3} 0 0 1 ${2 * (r - 2.3)} 0`}
        stroke="none"
      />
      <text
        fontSize={3.7}
        fontWeight={700}
        fontFamily="Archivo Variable, sans-serif"
        style={{ fontVariationSettings: "'wdth' 118", letterSpacing: ".2px" }}
        fill={ink}
        stroke="none"
      >
        <textPath href={`#${pathId}`} startOffset="50%" textAnchor="middle">
          {arcText}
        </textPath>
      </text>
      <g transform={rot} strokeDasharray="none">
        <line
          x1={x}
          y1={y + 4}
          x2={x}
          y2={y - 6}
          strokeWidth={known ? 1.3 : 0.8}
        />
        <path
          d={`M${x} ${y - 8.5} l-2.2 3.4 h4.4z`}
          fill={known ? ink : "none"}
        />
      </g>
    </g>
  )
}
