'use client'

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

function sourceLabel(news: NewsItem): string {
  if (news.publisher) return news.publisher
  const src = news.source.replace(/^rss:/, '')
  // YouTube 채널 표식
  if (src.startsWith('yt-')) {
    return `▶ ${src.replace('yt-', '').replace(/-/g, ' ')}`
  }
  if (src === 'anthropic') return 'Anthropic'
  if (src === 'openai') return 'OpenAI'
  if (src === 'geeknews') return 'GeekNews'
  if (src.startsWith('hn-')) return 'Hacker News'
  return src
}

export function AiCard({
  news,
  dict,
}: {
  news: NewsItem
  dict: import('@/lib/i18n/ko').Dict
}) {
  const isVideo = news.source.startsWith('rss:yt-')
  return (
    <a
      href={news.url}
      target="_blank"
      rel="noopener"
      className="mx-4 mb-2 block"
      style={{
        background: 'var(--bg-card)',
        borderRadius: 'var(--radius-card-sm)',
        padding: '16px 18px',
        textDecoration: 'none',
        transition: 'transform 150ms ease-out',
      }}
    >
      <div className="flex items-center gap-2" style={{ marginBottom: 8 }}>
        <span
          style={{
            fontSize: 12,
            fontWeight: 700,
            color: isVideo ? '#F04452' : 'var(--text-tertiary)',
            letterSpacing: '-0.01em',
          }}
        >
          {sourceLabel(news)}
        </span>
        <span
          className="ml-auto"
          style={{ fontSize: 11, fontWeight: 500, color: 'var(--text-tertiary)' }}
        >
          {formatTime(news.time)}
        </span>
      </div>
      <h3
        style={{
          fontSize: 16,
          fontWeight: 700,
          letterSpacing: '-0.02em',
          lineHeight: 1.35,
          color: 'var(--text-primary)',
          marginBottom: news.titleOriginal ? 4 : news.summary ? 6 : 0,
        }}
      >
        {news.title}
      </h3>
      {news.titleOriginal && (
        <p
          style={{
            fontSize: 12,
            lineHeight: 1.4,
            color: 'var(--text-tertiary)',
            marginBottom: news.summary ? 6 : 0,
          }}
        >
          {news.titleOriginal}
        </p>
      )}
      {news.summary && (
        <p
          style={{
            fontSize: 13,
            lineHeight: 1.55,
            color: 'var(--text-secondary)',
          }}
        >
          {news.summary.slice(0, 140)}
        </p>
      )}
      {void dict}
    </a>
  )
}
