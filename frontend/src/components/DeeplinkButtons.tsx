'use client'

import { buildDeeplinks } from '@/lib/deeplinks'
import type { SignalItem } from '@/lib/types'

export function DeeplinkButtons({ signal }: { signal: SignalItem }) {
  if (signal.source === 'edgar' || signal.scope === 'foreign') {
    return (
      <div
        className="text-center"
        style={{
          fontSize: 12,
          fontWeight: 500,
          color: 'var(--text-tertiary)',
          marginTop: 12,
        }}
      >
        해외 종목
      </div>
    )
  }

  if (!signal.companyCode) return null
  const links = buildDeeplinks(signal.companyCode)
  if (!links) return null

  const btnStyle = {
    flex: 1,
    background: 'var(--bg-inset)',
    color: 'var(--text-secondary)',
    padding: '10px 12px',
    borderRadius: 12,
    fontSize: 12,
    fontWeight: 600,
    textAlign: 'center' as const,
  }

  return (
    <div className="flex gap-2" style={{ marginTop: 12 }}>
      <a href={links.toss} style={btnStyle}>
        토스증권
      </a>
      <a href={links.koreainvestment} style={btnStyle}>
        증권플러스
      </a>
      <a href={links.naver} target="_blank" rel="noopener" style={btnStyle}>
        네이버증권
      </a>
    </div>
  )
}
