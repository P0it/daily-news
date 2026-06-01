'use client'

import { useState } from 'react'
import type { HotIssue, Scope, TickerPick } from '@/lib/types'
import { resolveTickerToSymbol } from '@/lib/tradingview'
import { buildTickerLinks } from '@/lib/deeplinks'
import { TradingViewWidget } from './TradingViewWidget'

const DIRECTION_CONFIG = {
  positive: { emoji: '📈', label: '상승 기대', dot: '#F04452', textColor: '#F04452', bg: 'rgba(240,68,82,0.1)' },
  negative: { emoji: '📉', label: '하락 주의', dot: '#3182F6', textColor: '#3182F6', bg: 'rgba(49,130,246,0.1)' },
  mixed:    { emoji: '↔️',  label: '방향 혼재', dot: '#F5A623', textColor: '#F5A623', bg: 'rgba(245,166,35,0.1)' },
}

function PickRow({ pick, isForeign }: { pick: TickerPick; isForeign: boolean }) {
  const [open, setOpen] = useState(false)
  const symbol = resolveTickerToSymbol(pick.ticker)
  const alts = pick.domestic
    ? Array.isArray(pick.domestic) ? pick.domestic : [pick.domestic]
    : []

  return (
    <div
      onClick={() => symbol && setOpen((v) => !v)}
      style={{
        background: 'var(--bg-inset)',
        borderRadius: 10,
        padding: '14px 14px',
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        cursor: symbol ? 'pointer' : 'default',
      }}
    >
      {/* 종목명 + 티커 코드 칩 + 펼침 힌트 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <span style={{
          fontSize: 14,
          fontWeight: 700,
          color: 'var(--text-primary)',
          lineHeight: 1.2,
        }}>
          {pick.name}
        </span>
        <span style={{
          fontSize: 11,
          fontWeight: 700,
          color: 'var(--text-primary)',
          background: '#E5E8EB',
          padding: '2px 7px',
          borderRadius: 5,
          letterSpacing: '0.02em',
          flexShrink: 0,
        }}>
          {pick.ticker}
        </span>
        {symbol && (
          <span style={{
            marginLeft: 'auto',
            fontSize: 11,
            color: 'var(--text-tertiary)',
            flexShrink: 0,
          }}>
            {open ? '▲' : '1D ▼'}
          </span>
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

      {/* 차트 펼침 */}
      {open && symbol && (
        <div
          onClick={(e) => e.stopPropagation()}
          style={{
            marginTop: 4,
            paddingTop: 12,
            borderTop: '1px solid var(--border-subtle)',
          }}
        >
          <TradingViewWidget symbol={symbol} height={240} />
        </div>
      )}

      {/* 국내 대안 — 해외 종목일 때만 표시 */}
      {isForeign && (
        <div style={{
          paddingTop: 8,
          borderTop: '1px solid var(--border-subtle)',
          marginTop: 2,
        }}>
          {alts.length > 0 ? (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center' }}>
              <span style={{ fontSize: 13 }}>🇰🇷</span>
              {alts.map((alt) => (
                <span key={alt.ticker} style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                  <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-secondary)' }}>
                    {alt.name}
                  </span>
                  <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
                    {alt.ticker}
                  </span>
                </span>
              ))}
            </div>
          ) : (
            <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>🚫 국내 추종 상품 없음</span>
          )}
        </div>
      )}
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
                </div>

                {/* 핵심 시그널 — 부제목 */}
                {issue.signal && (
                  <span style={{ fontSize: 12, color: 'var(--text-tertiary)', fontWeight: 500 }}>
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
