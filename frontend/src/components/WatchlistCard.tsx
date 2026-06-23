'use client'

import type { WatchItem, Direction, Beneficiary } from '@/lib/types'

// 방향은 dot + 텍스트로만 표현 (DESIGN.md: 배경·테두리·컬러스트립 금지)
const DIR: Record<Direction, { dot: string; label: string }> = {
  positive: { dot: '#F04452', label: '호재' },
  negative: { dot: '#3182F6', label: '주의' },
  mixed: { dot: '#F5A623', label: '복합' },
  neutral: { dot: 'var(--text-tertiary)', label: '중립' },
}

function BeneficiaryList({ list }: { list: Beneficiary[] }) {
  return (
    <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--border-subtle)', display: 'flex', flexDirection: 'column', gap: 8 }}>
      <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-tertiary)', letterSpacing: '0.04em' }}>
        잠재 수혜주 · 추론이라 확인이 필요해요
      </span>
      {list.map((b) => (
        <div key={(b.code ?? '') + b.name} style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>{b.name}</span>
            {b.code && (
              <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--badge-text)', background: 'var(--badge-bg)', padding: '1px 6px', borderRadius: 5 }}>
                {b.code}
              </span>
            )}
            {b.confidence === 'low' && (
              <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>추론</span>
            )}
          </div>
          {b.reason && (
            <p style={{ margin: 0, fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>{b.reason}</p>
          )}
        </div>
      ))}
    </div>
  )
}

function WatchRow({ item }: { item: WatchItem }) {
  const dir = DIR[item.direction] ?? DIR.neutral
  const head = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)', lineHeight: 1.2 }}>
          {item.company}
        </span>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
          <span style={{ width: 6, height: 6, borderRadius: 999, background: dir.dot, flexShrink: 0 }} />
          <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-tertiary)' }}>{dir.label}</span>
        </span>
      </div>
      <p style={{ margin: 0, fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.55 }}>
        {item.title}
      </p>
      <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
        {item.source}
        {item.url ? ' ↗' : ''}
      </span>
    </div>
  )

  const beneficiaries = item.beneficiaries ?? []

  return (
    <div style={{ background: 'var(--bg-inset)', borderRadius: 10, padding: '16px 16px' }}>
      {item.url ? (
        <a href={item.url} target="_blank" rel="noopener noreferrer" style={{ textDecoration: 'none', display: 'block' }}>
          {head}
        </a>
      ) : (
        head
      )}
      {beneficiaries.length > 0 && <BeneficiaryList list={beneficiaries} />}
    </div>
  )
}

export function WatchlistCard({ items }: { items: WatchItem[] }) {
  if (!items || items.length === 0) return null

  return (
    <section
      className="mx-4 mb-2.5"
      style={{ background: 'var(--bg-card)', borderRadius: 'var(--radius-card)', padding: '22px' }}
    >
      <div style={{ marginBottom: 6 }}>
        <p style={{ margin: 0, fontSize: 17, fontWeight: 700, color: 'var(--text-primary)', lineHeight: 1.3 }}>
          강한 촉매는 없지만, 지켜볼 만한 곳
        </p>
        <p style={{ margin: '6px 0 0', fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
          오늘 점수가 높았던 공시들이에요. 강한 촉매는 아니지만 흐름은 살펴두면 좋아요.
        </p>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 18 }}>
        {items.map((item) => (
          <WatchRow key={(item.code ?? '') + item.title} item={item} />
        ))}
      </div>
    </section>
  )
}
