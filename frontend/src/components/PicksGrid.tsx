'use client'

import type { PicksTab } from '@/lib/types'
import { PicksCard } from './PicksCard'

export function PicksGrid({
  picks,
  dict,
}: {
  picks: PicksTab
  dict: import('@/lib/i18n/ko').Dict
}) {
  const renderColumn = (
    label: string,
    signals: typeof picks.domestic,
    emptyText: string,
  ) => (
    <div>
      <h3
        style={{
          fontSize: 20,
          fontWeight: 700,
          color: 'var(--text-primary)',
          padding: '0 4px',
          marginBottom: 4,
          letterSpacing: '-0.02em',
        }}
      >
        {label}
      </h3>
      <div
        style={{
          fontSize: 13,
          color: 'var(--text-tertiary)',
          padding: '0 4px',
          marginBottom: 12,
        }}
      >
        Today&apos;s Pick · {signals.length}건
      </div>
      {signals.length === 0 ? (
        <p
          className="text-center"
          style={{
            fontSize: 13,
            color: 'var(--text-tertiary)',
            padding: '40px 10px',
          }}
        >
          {emptyText}
        </p>
      ) : (
        <div className="flex flex-col" style={{ gap: 8 }}>
          {signals.map((s) => (
            <PicksCard key={s.id} signal={s} dict={dict} />
          ))}
        </div>
      )}
    </div>
  )

  return (
    <>
      <div className="px-4 picks-grid">
        {renderColumn('국내', picks.domestic, '오늘은 국내 종목이 조용해요')}
        {renderColumn('해외', picks.foreign, '오늘은 해외 종목이 조용해요')}
      </div>
      <style jsx>{`
        .picks-grid {
          display: grid;
          grid-template-columns: 1fr;
          gap: 28px;
          padding-bottom: 24px;
        }
        @media (min-width: 720px) {
          .picks-grid {
            grid-template-columns: 1fr 1fr;
            gap: 14px;
          }
        }
      `}</style>
    </>
  )
}
