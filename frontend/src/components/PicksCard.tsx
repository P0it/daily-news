'use client'

import { useState } from 'react'
import { resolveTradingViewSymbol } from '@/lib/tradingview'
import type { Direction, SignalItem } from '@/lib/types'
import { DeeplinkButtons } from './DeeplinkButtons'
import { TradingViewWidget } from './TradingViewWidget'

const TONE: Record<Direction, string> = {
  positive: '#3182F6',
  negative: '#F04452',
  mixed: '#F79A34',
  neutral: '#8B95A1',
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString('ko-KR', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  })
}

export function PicksCard({
  signal,
  dict,
}: {
  signal: SignalItem
  dict: import('@/lib/i18n/ko').Dict
}) {
  const [open, setOpen] = useState(false)
  const color = TONE[signal.direction]
  const symbol = resolveTradingViewSymbol(signal)
  const time = formatTime(signal.time)

  return (
    <article
      onClick={() => setOpen((v) => !v)}
      className="cursor-pointer"
      style={{
        background: 'var(--bg-card)',
        borderRadius: 'var(--radius-card-sm)',
        padding: '16px 18px',
        transition: 'transform 150ms ease-out',
      }}
    >
      <div className="flex items-center" style={{ gap: 7, marginBottom: 8 }}>
        <span
          style={{
            width: 6,
            height: 6,
            borderRadius: '50%',
            background: color,
          }}
        />
        <span
          className="ml-auto"
          style={{ fontSize: 11, color: 'var(--text-tertiary)' }}
        >
          {time}
        </span>
      </div>

      <h4
        style={{
          fontSize: 16,
          fontWeight: 700,
          color: 'var(--text-primary)',
          letterSpacing: '-0.02em',
          lineHeight: 1.3,
        }}
      >
        {signal.company || '—'}
      </h4>
      <p
        style={{
          fontSize: 13,
          fontWeight: 500,
          color: 'var(--text-secondary)',
          marginTop: 4,
          lineHeight: 1.45,
        }}
      >
        {signal.headline}
      </p>

      {open && (
        <div
          onClick={(e) => e.stopPropagation()}
          style={{
            marginTop: 14,
            paddingTop: 14,
            borderTop: '1px solid var(--border-subtle)',
          }}
        >
          {symbol ? (
            <TradingViewWidget symbol={symbol} height={220} />
          ) : (
            <p
              className="text-center"
              style={{
                fontSize: 12,
                color: 'var(--text-tertiary)',
                padding: 20,
              }}
            >
              차트 심볼을 찾을 수 없어요
            </p>
          )}
          <a
            href={signal.url}
            target="_blank"
            rel="noopener"
            onClick={(e) => e.stopPropagation()}
            className="block text-center"
            style={{
              background: 'var(--text-primary)',
              color: 'var(--bg-card)',
              padding: '12px',
              borderRadius: 'var(--radius-btn)',
              fontSize: 13,
              fontWeight: 700,
              marginTop: 8,
            }}
          >
            {dict['cta.openOriginal']}
          </a>
          <DeeplinkButtons signal={signal} />
        </div>
      )}
    </article>
  )
}
