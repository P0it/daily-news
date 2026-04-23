'use client'

import type { PicksSection as PicksSectionData, Scope } from '@/lib/types'
import { PicksCard } from './PicksCard'

/** 경제 탭 내부 Today's Pick 섹션 (Week 5a — 종목 탭 격하 후 이동).
 *
 * scope 에 따라 해당 쪽만 표시:
 *   - domestic → 국내만 (1컬럼)
 *   - foreign  → 해외만 (1컬럼)
 */
export function PicksSection({
  picks,
  scope,
  dict,
}: {
  picks: PicksSectionData
  scope: Scope
  dict: import('@/lib/i18n/ko').Dict
}) {
  const items = scope === 'foreign' ? picks.foreign : picks.domestic
  const title =
    scope === 'foreign'
      ? "Today's Pick · 해외"
      : "Today's Pick · 국내"
  const emptyText =
    scope === 'foreign'
      ? '오늘은 해외 종목이 조용해요'
      : '오늘은 국내 종목이 조용해요'

  return (
    <section className="px-4" style={{ marginBottom: 18 }}>
      <h3
        style={{
          fontSize: 18,
          fontWeight: 700,
          color: 'var(--text-primary)',
          letterSpacing: '-0.02em',
          padding: '8px 4px 2px',
        }}
      >
        {title}
      </h3>
      <div
        style={{
          fontSize: 12,
          color: 'var(--text-tertiary)',
          padding: '0 4px 10px',
        }}
      >
        시그널 점수 상위 {items.length}건
      </div>

      {items.length === 0 ? (
        <p
          className="text-center"
          style={{
            fontSize: 13,
            color: 'var(--text-tertiary)',
            padding: '24px 10px',
          }}
        >
          {emptyText}
        </p>
      ) : (
        <div className="flex flex-col" style={{ gap: 8 }}>
          {items.map((s) => (
            <PicksCard key={s.id} signal={s} dict={dict} />
          ))}
        </div>
      )}
    </section>
  )
}
