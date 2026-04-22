import type { NewsItem } from '@/lib/types'

function formatTime(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleTimeString('ko-KR', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  })
}

export function CurrentNewsCard({
  news,
  dict,
}: {
  news: NewsItem
  dict: import('@/lib/i18n/ko').Dict
}) {
  return (
    <article
      className="mx-4 mb-2.5"
      style={{
        background: 'var(--bg-card)',
        borderRadius: 'var(--radius-card)',
        padding: '22px 22px 18px',
      }}
    >
      <div className="flex items-center gap-2" style={{ marginBottom: 12 }}>
        <span
          style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-tertiary)' }}
        >
          {news.source}
        </span>
        <span
          className="ml-auto"
          style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-tertiary)' }}
        >
          {formatTime(news.time)}
        </span>
      </div>

      <h3
        style={{
          fontSize: 17,
          fontWeight: 700,
          letterSpacing: '-0.02em',
          lineHeight: 1.35,
          color: 'var(--text-primary)',
          marginBottom: 8,
        }}
      >
        {news.title}
      </h3>
      {news.summary && (
        <p
          style={{
            fontSize: 14,
            lineHeight: 1.65,
            color: 'var(--text-secondary)',
          }}
        >
          {news.summary}
        </p>
      )}

      <div
        className="flex items-center"
        style={{
          marginTop: 20,
          paddingTop: 14,
          borderTop: '1px solid var(--border-subtle)',
        }}
      >
        <a
          href={news.url}
          target="_blank"
          rel="noopener"
          className="ml-auto"
          style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}
        >
          {dict['cta.more']}
        </a>
      </div>
    </article>
  )
}
