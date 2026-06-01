import { CATEGORY_META } from '@/lib/categoryMeta'
import type { NewsItem } from '@/lib/types'

function formatTime(iso: string): string {
  const d = new Date(iso)
  const now = new Date()
  const diffHours = (now.getTime() - d.getTime()) / 3600_000
  if (diffHours < 1) return '방금 전'
  if (diffHours < 24) return `${Math.floor(diffHours)}시간 전`
  const days = Math.floor(diffHours / 24)
  if (days < 7) return `${days}일 전`
  return d.toLocaleDateString('ko-KR')
}

export function CurrentNewsCard({
  news,
  dict,
}: {
  news: NewsItem
  dict: import('@/lib/i18n/ko').Dict
}) {
  void dict
  const publisher = news.publisher || news.source.replace(/^rss:/, '')
  const summary = news.summary.replace(/<[^>]*>/g, '').trim()
  const categoryMeta = news.category ? CATEGORY_META[news.category] : null

  return (
    <a
      href={news.url}
      target="_blank"
      rel="noopener"
      className="mx-4 mb-3 block"
      style={{
        background: 'var(--bg-card)',
        borderRadius: 'var(--radius-card)',
        padding: '20px 20px 18px',
        textDecoration: 'none',
        transition: 'opacity 120ms ease-out',
      }}
      onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.opacity = '0.75' }}
      onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.opacity = '1' }}
    >
      {/* 상단 메타 */}
      <div className="flex items-center" style={{ marginBottom: 10, gap: 6 }}>
        {categoryMeta && (
          <span
            style={{
              fontSize: 11,
              fontWeight: 600,
              color: categoryMeta.color,
              background: categoryMeta.bg,
              borderRadius: 4,
              padding: '2px 6px',
              letterSpacing: '-0.01em',
            }}
          >
            {categoryMeta.label}
          </span>
        )}
        <span
          style={{
            fontSize: 12,
            fontWeight: 600,
            color: 'var(--text-tertiary)',
            letterSpacing: '-0.01em',
          }}
        >
          {publisher}
        </span>
        <span
          style={{
            fontSize: 11,
            color: 'var(--border-subtle)',
            lineHeight: 1,
          }}
        >
          ·
        </span>
        <span
          style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-tertiary)' }}
        >
          {formatTime(news.time)}
        </span>
      </div>

      {/* 제목 */}
      <h3
        style={{
          fontSize: 16,
          fontWeight: 700,
          letterSpacing: '-0.02em',
          lineHeight: 1.45,
          color: 'var(--text-primary)',
          marginBottom: summary ? 10 : 0,
          wordBreak: 'keep-all',
          overflowWrap: 'break-word',
        }}
      >
        {news.title}
      </h3>

      {/* 요약 — 3줄 clamp */}
      {summary && (
        <p
          style={{
            fontSize: 14,
            lineHeight: 1.7,
            color: 'var(--text-secondary)',
            display: '-webkit-box',
            WebkitLineClamp: 3,
            WebkitBoxOrient: 'vertical' as const,
            overflow: 'hidden',
          }}
        >
          {summary}
        </p>
      )}
    </a>
  )
}
