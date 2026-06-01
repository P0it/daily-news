'use client'

import type { HotIssue } from '@/lib/types'

const DIRECTION_CONFIG = {
  positive: { label: '상승 기대', dot: '#00C073', textColor: '#00C073', bg: 'rgba(0,192,115,0.1)' },
  negative: { label: '하락 주의', dot: '#FF4B4B', textColor: '#FF4B4B', bg: 'rgba(255,75,75,0.1)' },
  mixed:    { label: '방향 혼재', dot: '#F5A623', textColor: '#F5A623', bg: 'rgba(245,166,35,0.1)' },
}

const ASSET_TYPE_LABEL: Record<string, string> = {
  stock: '종목',
  theme: '테마',
  macro: '매크로',
}

export function HotIssuesCard({ issues }: { issues: HotIssue[] }) {
  if (!issues || issues.length === 0) return null

  return (
    <section className="mx-4 mb-2.5" style={{ background: 'var(--bg-card)', borderRadius: 'var(--radius-card)', padding: '20px 22px' }}>
      <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-tertiary)', marginBottom: 18 }}>
        오늘 주목할 종목·테마
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
        {issues.map((issue, idx) => {
          // 구버전 JSON 호환: title 필드가 있고 asset이 없거나 뉴스 제목처럼 길면 둘 다 표시
          const assetName = issue.asset || issue.title || ''
          const dir = DIRECTION_CONFIG[issue.direction] ?? DIRECTION_CONFIG.mixed
          const typeLabel = issue.assetType ? (ASSET_TYPE_LABEL[issue.assetType] ?? issue.assetType) : null
          const tickers = issue.tickers ?? []
          const isLast = idx === issues.length - 1

          return (
            <div key={issue.rank}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>

                {/* 순위 레이블 */}
                <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-tertiary)' }}>
                  {issue.rank}위
                </div>

                {/* 자산명 (대형) + 방향 뱃지 */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                  <span style={{
                    fontSize: 22,
                    fontWeight: 700,
                    color: 'var(--text-primary)',
                    letterSpacing: '-0.03em',
                    lineHeight: 1.15,
                  }}>
                    {assetName}
                  </span>

                  {issue.direction && (
                    <span style={{
                      display: 'inline-flex', alignItems: 'center', gap: 4,
                      padding: '4px 10px', borderRadius: 999,
                      background: dir.bg,
                      fontSize: 11, fontWeight: 700, color: dir.textColor,
                      flexShrink: 0,
                    }}>
                      <span style={{ width: 5, height: 5, borderRadius: '50%', background: dir.dot }} />
                      {dir.label}
                    </span>
                  )}
                </div>

                {/* 태그 행: 자산유형 + 핵심 시그널 */}
                {(typeLabel || issue.signal) && (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {typeLabel && (
                      <span style={{
                        padding: '4px 10px', borderRadius: 999,
                        background: 'var(--bg-inset)',
                        fontSize: 12, fontWeight: 600, color: 'var(--text-tertiary)',
                      }}>
                        {typeLabel}
                      </span>
                    )}
                    {issue.signal && (
                      <span style={{
                        padding: '4px 10px', borderRadius: 999,
                        background: 'var(--bg-inset)',
                        fontSize: 12, fontWeight: 700, color: 'var(--text-primary)',
                      }}>
                        {issue.signal}
                      </span>
                    )}
                  </div>
                )}

                {/* 관련 티커 chips */}
                {tickers.length > 0 && (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {tickers.map((ticker) => (
                      <span key={ticker} style={{
                        padding: '5px 11px', borderRadius: 8,
                        background: 'var(--bg-inset)',
                        fontSize: 13, fontWeight: 700,
                        color: 'var(--text-secondary)',
                        letterSpacing: '0.01em',
                        fontVariantNumeric: 'tabular-nums',
                      }}>
                        {ticker}
                      </span>
                    ))}
                  </div>
                )}

                {/* 근거 설명 */}
                <p style={{
                  margin: 0,
                  fontSize: 13, color: 'var(--text-secondary)',
                  lineHeight: 1.65,
                }}>
                  {issue.reason}
                </p>

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
                    <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>
                      {issue.source}
                    </span>
                  )}
                </div>
              </div>

              {!isLast && (
                <div style={{ height: 1, background: 'var(--border-subtle)', marginTop: 24 }} />
              )}
            </div>
          )
        })}
      </div>
    </section>
  )
}
