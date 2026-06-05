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

function fmtAsOf(iso: string): string {
  const d = new Date(iso)
  const h = d.getHours()
  const min = d.getMinutes()
  const ampm = h < 12 ? '오전' : '오후'
  const h12 = h % 12 === 0 ? 12 : h % 12
  return `${ampm} ${h12}시 ${String(min).padStart(2, '0')}분`
}

/**
 * 조회 시점의 현재가를 가져온다.
 *
 * 정적 export라 서버 라우트를 못 쓰므로, vercel.json에 정의된 시세 프록시
 * rewrite를 클라이언트에서 직접 호출한다(국내=네이버, 해외=야후). 프록시는
 * 서버 사이드 rewrite라 CORS에 걸리지 않는다. 단 `next dev`에서는 rewrite가
 * 적용되지 않아 로컬에선 실패할 수 있고, 그 경우 정적 값이 유지된다.
 */
async function fetchCurrentPrice(
  ticker: string,
  scope: 'domestic' | 'foreign',
): Promise<number | null> {
  try {
    if (scope === 'domestic') {
      const r = await fetch(`/api/naver-stock/${ticker}/`)
      if (!r.ok) return null
      const d = await r.json()
      if (!d?.closePrice) return null
      const n = Number(String(d.closePrice).replace(/,/g, ''))
      return Number.isFinite(n) ? n : null
    }
    const r = await fetch(`/api/yahoo-stock/${ticker}/`)
    if (!r.ok) return null
    const d = await r.json()
    const price = d?.chart?.result?.[0]?.meta?.regularMarketPrice
    return typeof price === 'number' ? price : null
  } catch {
    return null
  }
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
  const [asOf, setAsOf] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)

  useEffect(() => {
    let cancelled = false
    fetchPicksHistory().then(async (recs) => {
      if (cancelled) return
      setRecords(recs) // 정적 데이터를 먼저 그려 빈 화면을 피한다
      if (recs.length === 0) return

      // 티커별 1회만 조회 (같은 종목이 여러 날 추천될 수 있음)
      const uniq = new Map<string, 'domestic' | 'foreign'>()
      for (const r of recs) if (!uniq.has(r.ticker)) uniq.set(r.ticker, r.scope)

      setRefreshing(true)
      const entries = await Promise.all(
        [...uniq.entries()].map(async ([ticker, scope]) => {
          const price = await fetchCurrentPrice(ticker, scope)
          return [ticker, price] as const
        }),
      )
      if (cancelled) return

      const priceByTicker = new Map(entries.filter(([, p]) => p !== null))
      const nowIso = new Date().toISOString()
      setRecords(
        (prev) =>
          prev?.map((r) => {
            const cur = priceByTicker.get(r.ticker)
            if (cur == null) return r
            const changePct =
              r.priceAtRec != null && r.priceAtRec > 0
                ? Math.round(((cur - r.priceAtRec) / r.priceAtRec) * 10000) / 100
                : null
            return { ...r, currentPrice: cur, changePct, currentPriceAt: nowIso }
          }) ?? null,
      )
      if (priceByTicker.size > 0) setAsOf(nowIso)
      if (!cancelled) setRefreshing(false)
    })
    return () => {
      cancelled = true
    }
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
      <div
        style={{
          fontSize: 12,
          color: 'var(--text-tertiary)',
          marginBottom: 12,
          paddingLeft: 4,
        }}
      >
        {refreshing
          ? '지금 시세 불러오는 중이에요'
          : asOf
          ? `${fmtAsOf(asOf)} 기준 시세예요`
          : '저장된 시세예요'}
      </div>
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
