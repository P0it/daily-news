'use client'

import type { NewsItem } from '@/lib/types'
import { CurrentNewsCard } from './CurrentNewsCard'

const SECTION_LABEL: Record<string, string> = {
  politics: '🏛️ 정치',
  society: '🏙️ 사회',
  international: '🌏 국제',
  tech: '💡 IT · 과학',
}

type SectionKey = keyof typeof SECTION_LABEL

export function CurrentSection({
  category,
  news,
  dict,
  hideLabel,
}: {
  category: SectionKey
  news: NewsItem[]
  dict: import('@/lib/i18n/ko').Dict
  hideLabel?: boolean
}) {
  if (news.length === 0) return null
  return (
    <section style={{ paddingTop: 32 }}>
      {!hideLabel && (
        <div style={{ padding: '0 20px 14px' }}>
          <h2
            style={{
              fontSize: 18,
              fontWeight: 700,
              color: 'var(--text-primary)',
              letterSpacing: '-0.02em',
              lineHeight: 1,
              marginBottom: 4,
            }}
          >
            {SECTION_LABEL[category]}
          </h2>
          <span
            style={{
              fontSize: 12,
              fontWeight: 500,
              color: 'var(--text-tertiary)',
            }}
          >
            {news.length}건
          </span>
        </div>
      )}

      {news.map((n) => (
        <CurrentNewsCard key={n.id} news={n} dict={dict} />
      ))}
    </section>
  )
}
