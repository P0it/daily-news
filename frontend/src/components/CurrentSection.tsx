'use client'

import type { NewsItem } from '@/lib/types'
import { CurrentNewsCard } from './CurrentNewsCard'

const SECTION_LABEL: Record<string, string> = {
  politics: '정치',
  society: '사회',
  international: '국제',
  tech: 'IT · 과학',
}

type SectionKey = keyof typeof SECTION_LABEL

export function CurrentSection({
  category,
  news,
  dict,
}: {
  category: SectionKey
  news: NewsItem[]
  dict: import('@/lib/i18n/ko').Dict
}) {
  if (news.length === 0) return null
  return (
    <section style={{ paddingTop: 24 }}>
      <h2
        style={{
          fontSize: 20,
          fontWeight: 700,
          padding: '0 20px 4px',
          color: 'var(--text-primary)',
          letterSpacing: '-0.02em',
        }}
      >
        {SECTION_LABEL[category]}
      </h2>
      <div
        style={{
          fontSize: 13,
          color: 'var(--text-tertiary)',
          padding: '0 20px 12px',
        }}
      >
        주목할 {news.length}건
      </div>
      {news.map((n) => (
        <CurrentNewsCard key={n.id} news={n} dict={dict} />
      ))}
    </section>
  )
}
