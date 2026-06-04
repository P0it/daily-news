'use client'

import type { SignalItem } from '@/lib/types'
import { StockLogo } from '@/components/StockLogo'

const SOURCE_LABEL: Record<string, string> = {
  dart: 'DART',
  edgar: 'SEC',
  edgar_cluster: '내부자',
  gov_contracts: '정부계약',
  research: '리서치',
}

const PHASE_COLOR: Record<number, string> = {
  1: '#2AC769',  // 초기 — 초록
  2: '#F5A623',  // 상승 초반 — 주황
  3: '#9B9B9B',  // 주류 — 회색
  4: '#9B9B9B',  // 고점 — 회색
}

interface Props {
  signals: SignalItem[]
}

export function TodayPicksList({ signals }: Props) {
  if (signals.length === 0) {
    return (
      <p
        style={{
          padding: '12px 20px',
          fontSize: 13,
          color: 'var(--text-tertiary)',
        }}
      >
        오늘 새로운 시그널이 없어요.
      </p>
    )
  }

  // Phase 1 → 2 → 3 순, 같은 phase 내 score 내림차순
  const sorted = [...signals].sort((a, b) => {
    const pa = a.attentionPhase ?? 2
    const pb = b.attentionPhase ?? 2
    if (pa !== pb) return pa - pb
    return b.score - a.score
  })

  return (
    <div style={{ padding: '0 20px' }}>
      {sorted.map((s) => {
        const phase = s.attentionPhase ?? 2
        const phaseColor = PHASE_COLOR[phase] ?? '#9B9B9B'
        const srcLabel = SOURCE_LABEL[s.source] ?? s.source.toUpperCase()
        const priceLead = s.priceLead ?? 0
        const priceStr =
          priceLead !== 0
            ? `${priceLead >= 0 ? '+' : ''}${(priceLead * 100).toFixed(1)}%`
            : null

        return (
          <a
            key={s.id}
            href={s.url}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: '11px 0',
              borderBottom: '1px solid var(--border-subtle)',
              textDecoration: 'none',
              color: 'inherit',
            }}
          >
            {/* Phase 도트 */}
            <span
              style={{
                width: 7,
                height: 7,
                borderRadius: '50%',
                background: phaseColor,
                flexShrink: 0,
                marginTop: 1,
              }}
            />

            {/* 종목 로고 + 종목명 */}
            <StockLogo ticker={s.companyCode} name={s.company || '—'} size={20} />
            <span
              style={{
                fontSize: 15,
                fontWeight: 700,
                color: 'var(--text-primary)',
                minWidth: 0,
                flexShrink: 0,
              }}
            >
              {s.company || '—'}
            </span>

            {/* 헤드라인 */}
            <span
              style={{
                fontSize: 13,
                color: 'var(--text-secondary)',
                flex: 1,
                minWidth: 0,
                overflow: 'hidden',
                whiteSpace: 'nowrap',
                textOverflow: 'ellipsis',
              }}
            >
              {s.headline}
            </span>

            {/* 우측: 소스 태그 + 가격선반영 */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                flexShrink: 0,
              }}
            >
              {priceStr && (
                <span
                  style={{
                    fontSize: 12,
                    fontWeight: 600,
                    color: priceLead >= 0 ? '#E22D3A' : '#2AC769',
                    fontVariantNumeric: 'tabular-nums',
                  }}
                >
                  {priceStr}
                </span>
              )}
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 600,
                  color: 'var(--text-tertiary)',
                  background: 'var(--bg-subtle)',
                  borderRadius: 4,
                  padding: '2px 5px',
                  letterSpacing: '0.04em',
                }}
              >
                {srcLabel}
              </span>
            </div>
          </a>
        )
      })}
    </div>
  )
}
