'use client'

import type { HotIssue } from '@/lib/types'

const DIRECTION_CONFIG = {
  positive: { label: '긍정', dot: '#00C073', textColor: '#00C073' },
  negative: { label: '부정', dot: '#FF4B4B', textColor: '#FF4B4B' },
  mixed:    { label: '혼재', dot: '#F5A623', textColor: '#F5A623' },
}

const ASSET_TYPE_LABEL = {
  stock: '종목',
  theme: '테마',
  macro: '매크로',
}

export function HotIssuesCard({ issues }: { issues: HotIssue[] }) {
  if (!issues || issues.length === 0) return null

  return (
    <section className="mx-4 mb-2.5" style={{ background: 'var(--bg-card)', borderRadius: 'var(--radius-card)', padding: '20px 22px' }}>
      {/* 헤더 */}
      <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-tertiary)', marginBottom: 18 }}>
        오늘 주목할 종목·테마
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
        {issues.map((issue, idx) => {
          // 구버전 JSON은 title 필드 사용, 신버전은 asset
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const assetName = issue.asset || (issue as any).title || ''
          const dir = DIRECTION_CONFIG[issue.direction] ?? DIRECTION_CONFIG.mixed
          const typeLabel = issue.assetType ? (ASSET_TYPE_LABEL[issue.assetType] ?? issue.assetType) : null
          const isLast = idx === issues.length - 1

          return (
            <div key={issue.rank}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {/* 상단 행: 순위 + 종목명 + 방향 칩 */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                  <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-tertiary)', minWidth: 20 }}>
                    {issue.rank}위
                  </span>

                  {/* 자산명 */}
                  {assetName && (
                    <span style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.02em', lineHeight: 1.2 }}>
                      {assetName}
                    </span>
                  )}

                  {/* 방향 칩 — direction 있을 때만 */}
                  {issue.direction && (
                    <span style={{
                      display: 'inline-flex', alignItems: 'center', gap: 4,
                      padding: '3px 8px', borderRadius: 999,
                      background: 'var(--bg-inset)',
                      fontSize: 11, fontWeight: 700, color: dir.textColor,
                    }}>
                      <span style={{ width: 5, height: 5, borderRadius: '50%', background: dir.dot, flexShrink: 0 }} />
                      {dir.label}
                    </span>
                  )}
                </div>

                {/* 태그 행: 자산 유형 + 핵심 시그널 — 둘 다 있을 때만 렌더 */}
                {(typeLabel || issue.signal) && (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, paddingLeft: 28 }}>
                    {typeLabel && (
                      <span style={{
                        padding: '4px 10px', borderRadius: 999,
                        background: 'var(--bg-inset)',
                        fontSize: 12, fontWeight: 700, color: 'var(--text-secondary)',
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

                {/* 근거 설명 */}
                <p style={{
                  margin: 0, paddingLeft: 28,
                  fontSize: 13, color: 'var(--text-secondary)',
                  lineHeight: 1.65,
                }}>
                  {issue.reason}
                </p>

                {/* 출처 링크 */}
                <div style={{ paddingLeft: 28 }}>
                  {issue.url ? (
                    <a
                      href={issue.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{
                        display: 'inline-flex', alignItems: 'center', gap: 4,
                        fontSize: 12, fontWeight: 700, color: 'var(--text-tertiary)',
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

              {/* 구분선 (마지막 아이템 제외) */}
              {!isLast && (
                <div style={{ height: 1, background: 'var(--border-subtle)', marginTop: 20 }} />
              )}
            </div>
          )
        })}
      </div>
    </section>
  )
}
