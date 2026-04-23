'use client'

import type { AiTab, Scope } from '@/lib/types'
import { AiCard } from './AiCard'

export function AiSection({
  tab,
  scope,
  dict,
}: {
  tab: AiTab
  scope: Scope
  dict: import('@/lib/i18n/ko').Dict
}) {
  const items = scope === 'foreign' ? tab.foreign : tab.domestic
  const emptyText =
    scope === 'foreign'
      ? '오늘은 해외 AI 소식이 조용해요'
      : '오늘은 국내 AI 소식이 조용해요'

  if (items.length === 0) {
    return (
      <p
        className="px-5 py-16 text-center"
        style={{ color: 'var(--text-secondary)', fontSize: 14 }}
      >
        {emptyText}
      </p>
    )
  }

  return (
    <div style={{ paddingBottom: 24 }}>
      {items.map((n) => (
        <AiCard key={n.id} news={n} dict={dict} />
      ))}
    </div>
  )
}
