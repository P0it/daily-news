'use client'

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

function sourceLabel(news: NewsItem): string {
  if (news.publisher) return news.publisher
  const src = news.source.replace(/^rss:/, '')
  if (src.startsWith('yt-')) return `▶ ${src.replace('yt-', '').replace(/-/g, ' ')}`
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
  void dict
  const isVideo = news.source.startsWith('rss:yt-')
  const summary = news.summary.replace(/<[^>]*>/g, '').trim()
  const categoryMeta = news.category ? CATEGORY_META[news.category] : null

  return (
    <a
      href={news.url}
      target="_blank"
      rel="noopener"
      className="mx-4 mb-2.5 block"
      style={{
        background: 'var(--bg-card)',
        borderRadius: 'var(--radius-card-sm)',
        padding: '16px 18px',
        textDecoration: 'none',
        transition: 'opacity 120ms ease-out',
      }}
      onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.opacity = '0.75' }}
      onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.opacity = '1' }}
    >
      {/* 상단 메타 */}
      <div className="flex items-center" style={{ marginBottom: 9, gap: 6 }}>
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

      {/* 제목 */}
      <h3
        style={{
          fontSize: 15,
          fontWeight: 700,
          letterSpacing: '-0.02em',
          lineHeight: 1.45,
          color: 'var(--text-primary)',
          marginBottom: news.titleOriginal ? 4 : summary ? 8 : 0,
          wordBreak: 'keep-all',
          overflowWrap: 'break-word',
        }}
      >
        {news.title}
      </h3>

      {/* 원문 제목 (번역된 경우) */}
      {news.titleOriginal && (
        <p
          style={{
            fontSize: 12,
            lineHeight: 1.45,
            color: 'var(--text-tertiary)',
            marginBottom: summary ? 8 : 0,
          }}
        >
          {news.titleOriginal}
        </p>
      )}

      {/* 요약 — 2줄 clamp */}
      {summary && (
        <p
          style={{
            fontSize: 13,
            lineHeight: 1.65,
            color: 'var(--text-secondary)',
            display: '-webkit-box',
            WebkitLineClamp: 2,
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
