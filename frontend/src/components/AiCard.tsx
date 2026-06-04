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
  if (src.startsWith('yt-')) return `▶ ${src.replace('yt-', '').replace(/-/g, ' ')}`
  if (src === 'anthropic') return 'Anthropic'
  if (src === 'openai') return 'OpenAI'
  if (src === 'geeknews') return 'GeekNews'
  if (src.startsWith('hn-')) return 'Hacker News'
  return src
}

const EMOJI_RE = /[\p{Emoji_Presentation}\p{Extended_Pictographic}]/gu

function stripEmoji(text: string): string {
  return text.replace(EMOJI_RE, '').replace(/\s{2,}/g, ' ').trim()
}

export function AiCard({
  news,
  dict,
}: {
  news: NewsItem
  dict: import('@/lib/i18n/ko').Dict
}) {
  void dict
  const isVideo = news.source.startsWith('rss:yt-') || news.url.includes('youtube.com')
  const rawSummary = news.summary.replace(/<[^>]*>/g, '').trim()
  // YouTube 설명은 링크 나열이라 표시 안 함
  const summary = isVideo ? '' : rawSummary

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
        {/* 소스 타입 뱃지 */}
        <span
          style={{
            fontSize: 11,
            fontWeight: 700,
            color: isVideo ? '#C0392B' : 'var(--text-secondary)',
            background: isVideo ? '#FFF0EE' : 'var(--bg-inset)',
            borderRadius: 4,
            padding: '2px 6px',
            letterSpacing: '-0.01em',
            flexShrink: 0,
          }}
        >
          {isVideo ? '▶ YouTube' : '기사'}
        </span>
        <span
          style={{
            fontSize: 12,
            fontWeight: 600,
            color: 'var(--text-tertiary)',
            letterSpacing: '-0.01em',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {sourceLabel(news)}
        </span>
        <span
          className="ml-auto"
          style={{ fontSize: 11, fontWeight: 500, color: 'var(--text-tertiary)', flexShrink: 0 }}
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
        {stripEmoji(news.title)}
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
