import type { MarketIndex } from '@/lib/types'

export function MarketIndices({
  indices,
  dict,
}: {
  indices: MarketIndex[]
  dict: import('@/lib/i18n/ko').Dict
}) {
  if (indices.length === 0) return null

  return (
    <section
      className="mx-4 mb-2.5"
      style={{
        background: 'var(--bg-card)',
        borderRadius: 'var(--radius-card)',
        padding: '24px 22px',
      }}
    >
      <div
        style={{
          fontSize: 12,
          fontWeight: 700,
          letterSpacing: '0.02em',
          textTransform: 'uppercase',
          color: 'var(--text-tertiary)',
          marginBottom: 16,
        }}
      >
        {dict.marketIndicesTitle}
      </div>
      <div
        className="grid grid-cols-3"
        style={{ columnGap: 16 }}
      >
        {indices.map((m) => {
          const color =
            m.direction === 'up'
              ? '#F04452'
              : m.direction === 'down'
              ? '#3182F6'
              : 'var(--text-tertiary)'
          return (
            <div key={m.name}>
              <div
                style={{
                  fontSize: 12,
                  fontWeight: 500,
                  color: 'var(--text-tertiary)',
                  marginBottom: 6,
                }}
              >
                {m.name}
              </div>
              <div
                style={{
                  fontSize: 22,
                  fontWeight: 700,
                  color: 'var(--text-primary)',
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                {m.value}
              </div>
              <div style={{ fontSize: 13, fontWeight: 700, color, marginTop: 4 }}>
                {m.change}
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}
