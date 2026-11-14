const SECTORS = [0, 1, 2, 3, 4, 5, 6, 7] as const

export interface RoseProps {
  count: number
  /** Short count label such as "1.2k". */
  label: string
  /** Members per facing sector (index 0 = N, clockwise by 45 degrees). */
  sectors: readonly number[]
}

/** Cluster marker: a postmark rose with one tick per facing sector. */
export function Rose({ count, label, sectors }: RoseProps) {
  const R = count >= 100 ? 19 : count >= 20 ? 16 : 13
  const S = R + 18
  return (
    <svg
      viewBox={`${-S} ${-S} ${2 * S} ${2 * S}`}
      width={2 * S}
      height={2 * S}
      aria-hidden="true"
    >
      <g stroke="#141414" strokeWidth={2} strokeLinecap="round">
        {SECTORS.map((i) => {
          const share = (sectors[i] ?? 0) / count
          if (!share) return null
          const a = (i * 45 * Math.PI) / 180
          const l = 3 + share * 14
          return (
            <line
              key={i}
              x1={Math.sin(a) * R}
              y1={-Math.cos(a) * R}
              x2={Math.sin(a) * (R + l)}
              y2={-Math.cos(a) * (R + l)}
            />
          )
        })}
      </g>
      <circle r={R} fill="#fbfbf7" stroke="#141414" strokeWidth={1.5} />
      <circle r={R - 3.2} fill="none" stroke="#141414" strokeWidth={0.7} />
      <text
        textAnchor="middle"
        dominantBaseline="central"
        fontFamily="Archivo Variable, sans-serif"
        fontWeight={700}
        fontSize={R >= 16 ? 11 : 10}
        style={{
          fontVariationSettings: "'wdth' 112",
          fontVariantNumeric: "tabular-nums",
        }}
        fill="#141414"
      >
        {label}
      </text>
    </svg>
  )
}
