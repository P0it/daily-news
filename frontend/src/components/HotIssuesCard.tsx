'use client'

import type { HotIssue } from '@/lib/types'

const RANK_LABEL: Record<number, string> = { 1: '1위', 2: '2위', 3: '3위' }

export function HotIssuesCard({ issues }: { issues: HotIssue[] }) {
  if (!issues || issues.length === 0) return null

  return (
    <section className="mx-4 mb-2.5" style={{ background: 'var(--bg-card)', borderRadius: 'var(--radius-card)', padding: '20px 22px' }}>
      <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-tertiary)', marginBottom: 16 }}>
        오늘의 핵심 이슈
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {issues.map((issue) => (
          <div key={issue.rank}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 4 }}>
              <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-tertiary)', minWidth: 24 }}>
                {RANK_LABEL[issue.rank] ?? `${issue.rank}위`}
              </span>
              {issue.url ? (
                <a
                  href={issue.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)', lineHeight: 1.4, textDecoration: 'none' }}
                >
                  {issue.title}
                </a>
              ) : (
                <span style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)', lineHeight: 1.4 }}>
                  {issue.title}
                </span>
              )}
            </div>
            <div style={{ paddingLeft: 32 }}>
              <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6, margin: 0 }}>
                {issue.reason}
              </p>
              <span style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 4, display: 'block' }}>
                {issue.source}
              </span>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
