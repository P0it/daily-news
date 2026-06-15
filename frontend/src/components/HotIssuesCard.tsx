'use client'

import { useState, type CSSProperties } from 'react'
import type { HotIssue, Scope, TickerPick } from '@/lib/types'
import { resolveTickerToSymbol } from '@/lib/tradingview'
import { PhaseTag } from '@/components/PhaseTag'
import { buildTickerLinks } from '@/lib/deeplinks'
import { TradingViewWidget } from '@/components/TradingViewWidget'
import { StockLogo } from '@/components/StockLogo'

const DIRECTION_CONFIG = {
  positive: { emoji: '📈', label: '상승 기대', dot: '#F04452', textColor: '#F04452', bg: 'rgba(240,68,82,0.1)' },
  negative: { emoji: '📉', label: '하락 주의', dot: '#3182F6', textColor: '#3182F6', bg: 'rgba(49,130,246,0.1)' },
  mixed:    { emoji: '↔️',  label: '방향 혼재', dot: '#F5A623', textColor: '#F5A623', bg: 'rgba(245,166,35,0.1)' },
}

type StockQuote = { price: string; change: string; changeRate: string; isUp: boolean; currency?: string }

// 코드 칩 — 종목 티커·ETF 코드 공용 (동일 스타일 유지)
const CODE_CHIP_STYLE: CSSProperties = {
  fontSize: 10,
  fontWeight: 700,
  color: 'var(--badge-text)',
  background: 'var(--badge-bg)',
  padding: '1px 6px',
  borderRadius: 5,
  letterSpacing: '0.02em',
  flexShrink: 0,
}

function PickRow({ pick, isForeign }: { pick: TickerPick; isForeign: boolean }) {
  const [open, setOpen] = useState(false)
  const [quote, setQuote] = useState<StockQuote | null>(null)
  const symbol = resolveTickerToSymbol(pick.ticker)
  const isKrx = symbol?.startsWith('KRX:') ?? false
  const chartUrl = isKrx
    ? `https://finance.naver.com/item/main.naver?code=${pick.ticker}`
    : null
  const alts = pick.domestic
    ? Array.isArray(pick.domestic) ? pick.domestic : [pick.domestic]
    : []
  const relatedEtf = pick.related_etf ?? null

  function handleChartClick(e: React.MouseEvent) {
    e.stopPropagation()
    if (!symbol) return
    const next = !open
    setOpen(next)
    if (next && !quote) {
      if (isKrx) {
        fetch(`/api/naver-stock/${pick.ticker}/`)
          .then((r) => r.json())
          .then((d) => {
            if (!d.closePrice) return
            setQuote({
              price: d.closePrice,
              change: d.compareToPreviousClosePrice,
              changeRate: d.fluctuationsRatio,
              isUp: d.compareToPreviousPrice?.code === '2',
            })
          })
          .catch(() => null)
      } else {
        fetch(`/api/yahoo-stock/${pick.ticker}/`)
          .then((r) => r.json())
          .then((d) => {
            const meta = d?.chart?.result?.[0]?.meta
            if (!meta) return
            const price = meta.regularMarketPrice
            const prev = meta.chartPreviousClose ?? meta.previousClose
            if (!price || !prev) return
            const diff = price - prev
            setQuote({
              price: price.toFixed(2),
              change: Math.abs(diff).toFixed(2),
              changeRate: Math.abs((diff / prev) * 100).toFixed(2),
              isUp: diff >= 0,
              currency: meta.currency ?? 'USD',
            })
          })
          .catch(() => null)
      }
    }
  }

  return (
    <div
      style={{
        background: 'var(--bg-inset)',
        borderRadius: 10,
        padding: '14px 14px',
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
      }}
    >
      {/* 종목명 + 티커 코드 칩 + 차트 버튼 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <StockLogo ticker={pick.ticker} name={pick.name} size={24} />
        <span style={{
          fontSize: 14,
          fontWeight: 700,
          color: 'var(--text-primary)',
          lineHeight: 1.2,
        }}>
          {pick.name}
        </span>
        <span style={CODE_CHIP_STYLE}>
          {pick.ticker}
        </span>
        {pick.verifyStatus === 'review' && (
          <span
            title={pick.verifyNote || '테마 연결고리를 추가로 확인해 주세요'}
            style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-tertiary)' }}
          >
            ⚠️ 추가 확인
          </span>
        )}
        {symbol && (
          <button
            onClick={handleChartClick}
            title={open ? '차트 닫기' : isKrx ? '네이버 증권 차트' : '차트 보기'}
            style={{
              marginLeft: 'auto',
              background: open ? 'var(--bg-card)' : 'transparent',
              border: 'none',
              borderRadius: 6,
              padding: '2px 6px',
              cursor: 'pointer',
              fontSize: 15,
              lineHeight: 1,
              flexShrink: 0,
              display: 'inline-flex',
              alignItems: 'center',
            }}
          >
            📊
          </button>
        )}
      </div>

      {/* 추천 이유 설명 */}
      {pick.description && (
        <p style={{
          margin: 0,
          fontSize: 12,
          color: 'var(--text-secondary)',
          lineHeight: 1.6,
        }}>
          {pick.description}
        </p>
      )}

      {/* 추가 확인 사유 — 왜 검증이 필요한지 */}
      {pick.verifyStatus === 'review' && pick.verifyNote && (
        <p style={{
          margin: '4px 0 0',
          fontSize: 11,
          color: 'var(--text-tertiary)',
          lineHeight: 1.5,
        }}>
          ⚠️ {pick.verifyNote}
        </p>
      )}

      {/* 미발굴 근거 */}
      {pick.why_undiscovered && (
        <p style={{
          margin: '4px 0 0',
          fontSize: 11,
          color: 'var(--text-tertiary)',
          lineHeight: 1.5,
          fontStyle: 'italic',
        }}>
          {pick.why_undiscovered}
        </p>
      )}

      {/* 차트 펼침 */}
      {open && symbol && (
        <div
          style={{
            marginTop: 4,
            paddingTop: 12,
            borderTop: '1px solid var(--border-subtle)',
          }}
        >
          {isKrx ? (() => {
            const color = quote ? (quote.isUp ? '#F04452' : '#3182F6') : 'var(--text-tertiary)'
            return (
              <a href={`https://finance.naver.com/item/main.naver?code=${pick.ticker}`}
                target="_blank" rel="noopener noreferrer"
                style={{ display: 'block', borderRadius: 10, overflow: 'hidden', textDecoration: 'none' }}>
                {quote && (
                  <div style={{ padding: '12px 16px 10px', background: 'var(--bg-card)' }}>
                    <div style={{ fontSize: 24, fontWeight: 700, color, lineHeight: 1.2 }}>
                      {quote.price}원
                    </div>
                    <div style={{ marginTop: 4, display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>전일대비</span>
                      <span style={{ fontSize: 13, fontWeight: 600, color }}>
                        {quote.isUp ? '▲' : '▼'} {quote.change.replace('-', '')}
                      </span>
                      <span style={{ fontSize: 13, color }}>
                        ({quote.changeRate.replace('-', '')}%)
                      </span>
                    </div>
                  </div>
                )}
                <img
                  src={`https://ssl.pstatic.net/imgfinance/chart/item/candle/day/${pick.ticker}.png`}
                  alt={`${pick.name} 차트`}
                  width="100%"
                  style={{ display: 'block' }}
                />
              </a>
            )
          })() : (() => {
            const color = quote ? (quote.isUp ? '#00B341' : '#F04452') : 'var(--text-tertiary)'
            const unit = quote?.currency ?? 'USD'
            return (
              <>
                {quote && (
                  <div style={{ padding: '12px 16px 10px', background: 'var(--bg-card)', borderRadius: 10 }}>
                    <div style={{ fontSize: 24, fontWeight: 700, color, lineHeight: 1.2 }}>
                      {quote.price} {unit}
                    </div>
                    <div style={{ marginTop: 4, display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>전일대비</span>
                      <span style={{ fontSize: 13, fontWeight: 600, color }}>
                        {quote.isUp ? '▲' : '▼'} {quote.change}
                      </span>
                      <span style={{ fontSize: 13, color }}>
                        ({quote.changeRate}%)
                      </span>
                    </div>
                  </div>
                )}
                <TradingViewWidget symbol={symbol} height={280} />
              </>
            )
          })()}
        </div>
      )}

      {/* ETF 섹션 — 관련 ETF(양 스코프) + 추종 ETF(해외만). 구분선 하나, 두 줄은 좁게 */}
      <div style={{
        paddingTop: 8,
        borderTop: '1px solid var(--border-subtle)',
        marginTop: 2,
        display: 'flex',
        flexDirection: 'column',
        gap: 4,
      }}>
        {/* 관련 ETF — 종목을 많이 담은 동일 시장 ETF (해외→🇺🇸, 국내→🇰🇷). 없어도 항상 표시 */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, alignItems: 'center' }}>
          <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-tertiary)' }}>
            {isForeign ? '🇺🇸' : '🇰🇷'} ETF
          </span>
          {relatedEtf ? (
            <>
              <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-secondary)' }}>
                {relatedEtf.name}
              </span>
              {relatedEtf.ticker && <span style={CODE_CHIP_STYLE}>{relatedEtf.ticker}</span>}
              {relatedEtf.confidence === 'low' && (
                <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>⚠️ 추가 확인 필요</span>
              )}
            </>
          ) : (
            <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>없음</span>
          )}
        </div>

        {/* 추종 ETF — 해외 종목일 때만 (ISA·연금 계좌용). 없어도 항상 표시 */}
        {isForeign && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, alignItems: 'center' }}>
            <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-tertiary)' }}>
              🇰🇷 ETF
            </span>
            {alts.length > 0 ? (
              alts.map((alt) => (
                <span key={alt.ticker} style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
                  <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-secondary)' }}>
                    {alt.name}
                  </span>
                  {alt.ticker && <span style={CODE_CHIP_STYLE}>{alt.ticker}</span>}
                </span>
              ))
            ) : (
              <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>없음</span>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export function HotIssuesCard({ issues, scope }: { issues: HotIssue[]; scope: Scope }) {
  if (!issues || issues.length === 0) return null
  const isForeign = scope === 'foreign'

  return (
    <section className="mx-4 mb-2.5" style={{ background: 'var(--bg-card)', borderRadius: 'var(--radius-card)', padding: '20px 22px' }}>
      <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-tertiary)', marginBottom: 18 }}>
        🔥 오늘 주목할 종목·테마
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 28 }}>
        {issues.map((issue, idx) => {
          const assetName = issue.asset || issue.title || ''
          const dir = DIRECTION_CONFIG[issue.direction] ?? DIRECTION_CONFIG.mixed
          const picks = issue.picks ?? []
          const isLast = idx === issues.length - 1

          return (
            <div key={issue.rank}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>

                {/* 순위 */}
                <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-tertiary)' }}>
                  {issue.rank}위
                </span>

                {/* 자산명 + 방향 뱃지 */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                  <span style={{
                    fontSize: 17,
                    fontWeight: 700,
                    color: 'var(--text-primary)',
                    letterSpacing: '-0.02em',
                    lineHeight: 1.2,
                  }}>
                    {assetName}
                  </span>
                  {issue.direction && (
                    <span style={{
                      display: 'inline-flex', alignItems: 'center', gap: 5,
                      padding: '4px 10px', borderRadius: 999,
                      background: dir.bg,
                      fontSize: 11, fontWeight: 700, color: dir.textColor,
                      flexShrink: 0,
                    }}>
                      <span style={{ fontSize: 12, lineHeight: 1 }}>{dir.emoji}</span>
                      {dir.label}
                    </span>
                  )}
                  {(() => {
                    const risks = (issue.picks ?? []).map((p: { consensus_risk?: string }) => p.consensus_risk).filter(Boolean)
                    const risk = risks.includes('low') ? 'low' : risks.includes('medium') ? 'medium' : null
                    return risk ? <PhaseTag risk={risk} /> : null
                  })()}
                </div>

                {/* 부제목 */}
                {issue.signal && (
                  <span style={{ fontSize: 13, color: 'var(--text-secondary)', fontWeight: 600 }}>
                    {issue.signal}
                  </span>
                )}

                {/* 분석 텍스트 */}
                <p style={{
                  margin: 0,
                  fontSize: 13, color: 'var(--text-secondary)',
                  lineHeight: 1.65,
                }}>
                  {issue.reason}
                </p>

                {/* 수혜 종목 picks */}
                {picks.length > 0 && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                    <span style={{
                      fontSize: 11, fontWeight: 700,
                      color: 'var(--text-tertiary)',
                      letterSpacing: '0.04em',
                      marginBottom: 4,
                    }}>
                      💡 주목 종목
                    </span>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      {picks.map((pick) => (
                        <PickRow key={pick.ticker} pick={pick} isForeign={isForeign} />
                      ))}
                    </div>
                  </div>
                )}

                {/* 주의사항 */}
                {issue.cautions && (
                  <div style={{
                    background: 'rgba(245,166,35,0.08)',
                    borderRadius: 10,
                    padding: '12px 14px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 6,
                  }}>
                    <span style={{ fontSize: 11, fontWeight: 700, color: '#B07D10', letterSpacing: '0.04em' }}>
                      주의사항
                    </span>
                    <p style={{ margin: 0, fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.65 }}>
                      {issue.cautions}
                    </p>
                  </div>
                )}

                {/* 출처 */}
                <div>
                  {issue.url ? (
                    <a
                      href={issue.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{
                        display: 'inline-flex', alignItems: 'center', gap: 4,
                        fontSize: 12, fontWeight: 600, color: 'var(--text-tertiary)',
                        textDecoration: 'none',
                      }}
                    >
                      {issue.source}
                      <span style={{ fontSize: 10 }}>↗</span>
                    </a>
                  ) : (
                    <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>{issue.source}</span>
                  )}
                </div>
              </div>

              {!isLast && (
                <div style={{ height: 1, background: 'var(--border-subtle)', marginTop: 28 }} />
              )}
            </div>
          )
        })}
      </div>
    </section>
  )
}
