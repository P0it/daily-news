'use client'

import { useEffect, useState } from 'react'
import { fetchPicksHistory } from '@/lib/fetchBriefing'
import type { PickRecord } from '@/lib/types'
import { StockLogo } from '@/components/StockLogo'

function fmtPct(pct: number | null): string {
  if (pct === null) return '—'
  return `${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%`
}

function fmtPrice(price: number | null, currency: string): string {
  if (price === null) return '—'
  if (currency === 'KRW') return price.toLocaleString('ko-KR')
  return '$' + price.toFixed(2)
}

function fmtDate(dateStr: string): string {
  const [, m, d] = dateStr.split('-').map(Number)
  const date = new Date(dateStr + 'T00:00:00')
  const dayNames = ['일', '월', '화', '수', '목', '금', '토']
  return `${m}월 ${d}일 ${dayNames[date.getDay()]}요일`
}

function groupByDate(records: PickRecord[]): [string, PickRecord[]][] {
  const map = new Map<string, PickRecord[]>()
  for (const r of records) {
    const arr = map.get(r.date) ?? []
    arr.push(r)
    map.set(r.date, arr)
  }
  return [...map.entries()]
    .sort(([a], [b]) => b.localeCompare(a))
    .map(([date, rows]) => [
      date,
      [...rows].sort((a, b) => (b.changePct ?? -Infinity) - (a.changePct ?? -Infinity)),
    ])
}

const COL = '1fr 80px 80px 72px'

function TableHeader() {
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: COL,
        padding: '8px 16px',
        borderBottom: '1px solid var(--border-subtle)',
      }}
    >
      {['종목', '추천가', '현재가', '수익률'].map((h) => (
        <span
          key={h}
          style={{
            fontSize: 11,
            fontWeight: 600,
            color: 'var(--text-tertiary)',
            textAlign: h === '종목' ? 'left' : 'right',
            letterSpacing: '0.04em',
          }}
        >
          {h}
        </span>
      ))}
    </div>
  )
}

export function PicksHistoryView() {
  const [records, setRecords] = useState<PickRecord[] | null>(null)

  useEffect(() => {
    fetchPicksHistory().then(setRecords)
  }, [])

  if (records === null) {
    return (
      <p className="px-5 py-20 text-center" style={{ color: 'var(--text-tertiary)' }}>
        불러오는 중...
      </p>
    )
  }

  if (records.length === 0) {
    return (
      <p
        className="px-5 py-20 text-center"
        style={{ color: 'var(--text-secondary)', lineHeight: 1.7 }}
      >
        아직 추천 이력이 없어요.
        <br />
        매일 아침 브리핑 후 자동으로 추가돼요.
      </p>
    )
  }

  // 티커별 최신 추천 1건만 유지 (records는 이미 최신 순 정렬)
  const seen = new Set<string>()
  const deduped = records.filter((r) => {
    if (seen.has(r.ticker)) return false
    seen.add(r.ticker)
    return true
  })

  const cutoff = new Date()
  cutoff.setDate(cutoff.getDate() - 7)
  const cutoffStr = cutoff.toISOString().slice(0, 10)
  const recent = deduped.filter((r) => r.date >= cutoffStr)

  const grouped = groupByDate(recent.length > 0 ? recent : deduped.slice(0, 20))

  return (
    <div style={{ padding: '16px 20px 40px' }}>
      {grouped.map(([date, rows]) => (
        <div key={date} style={{ marginBottom: 24 }}>
          {/* 날짜 헤더 */}
          <div
            style={{
              fontSize: 13,
              fontWeight: 700,
              color: 'var(--text-secondary)',
              marginBottom: 8,
              paddingLeft: 4,
            }}
          >
            {fmtDate(date)}
          </div>

          {/* 카드 — 다른 탭과 동일한 radius/배경 */}
          <div
            style={{
              background: 'var(--bg-card)',
              borderRadius: 'var(--radius-card)',
              overflow: 'hidden',
            }}
          >
            <TableHeader />
            {(['domestic', 'foreign'] as const).map((scope) => {
              const scopeRows = rows.filter((r) => r.scope === scope)
              if (scopeRows.length === 0) return null
              return (
                <div key={scope}>
                  {/* 국내/해외 구분 레이블 */}
                  <div
                    style={{
                      fontSize: 11,
                      fontWeight: 600,
                      color: 'var(--text-tertiary)',
                      padding: '8px 16px 4px',
                      borderBottom: '1px solid var(--border-subtle)',
                      letterSpacing: '0.06em',
                    }}
                  >
                    {scope === 'domestic' ? '🇰🇷 국내' : '🌐 해외'}
                  </div>
                  {scopeRows.map((rec) => {
              const hasPct = rec.changePct !== null
              const pctColor = !hasPct
                ? 'var(--text-tertiary)'
                : rec.changePct! > 0
                ? '#E22D3A'
                : rec.changePct! < 0
                ? '#1A6FE8'
                : 'var(--text-tertiary)'

              const rowColor = hasPct && rec.changePct !== 0 ? pctColor : undefined

              return (
                <div
                  key={rec.id}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: COL,
                    alignItems: 'center',
                    padding: '10px 16px',
                    borderBottom: '1px solid var(--border-subtle)',
                    color: rowColor,
                  }}
                >
                  {/* 종목명 + 테마 */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 7, minWidth: 0, overflow: 'hidden' }}>
                    <StockLogo ticker={rec.ticker} name={rec.name} size={22} />
                    <div style={{ minWidth: 0, overflow: 'hidden', whiteSpace: 'nowrap', textOverflow: 'ellipsis' }}>
                    <span style={{ fontSize: 14, fontWeight: 700, marginRight: 5 }}>
                      {rec.name}
                    </span>
                    {rec.theme && (
                      <span style={{ fontSize: 11, opacity: 0.6 }}>
                        {rec.theme}
                      </span>
                    )}
                    </div>
                  </div>

                  {/* 추천가 */}
                  <span
                    style={{
                      fontSize: 13,
                      textAlign: 'right',
                      fontVariantNumeric: 'tabular-nums',
                      color: rowColor ?? 'var(--text-secondary)',
                    }}
                  >
                    {fmtPrice(rec.priceAtRec, rec.currency)}
                  </span>

                  {/* 현재가 */}
                  <span
                    style={{
                      fontSize: 13,
                      textAlign: 'right',
                      fontVariantNumeric: 'tabular-nums',
                      color: rowColor ?? 'var(--text-secondary)',
                    }}
                  >
                    {fmtPrice(rec.currentPrice, rec.currency)}
                  </span>

                  {/* 수익률 */}
                  <span
                    style={{
                      fontSize: 14,
                      fontWeight: 700,
                      textAlign: 'right',
                      fontVariantNumeric: 'tabular-nums',
                    }}
                  >
                    {fmtPct(rec.changePct)}
                  </span>
                </div>
              )
            })}
                </div>
              )
            })}
          </div>
        </div>
      ))}
    </div>
  )
}
