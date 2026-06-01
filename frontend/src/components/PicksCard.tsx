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

function resolveSourceLabel(source: string): string {
  if (source === 'dart') return 'DART 공시'
  if (source === 'edgar') return 'SEC EDGAR'
  if (source === 'research') return '증권사 리포트'
  if (source.includes('ft')) return 'Financial Times'
  if (source.includes('bbc')) return 'BBC Business'
  if (source.includes('gnews')) return 'Google News'
  return source
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
  const sourceLabel = resolveSourceLabel(signal.source)

  return (
    <article
      onClick={() => setOpen((v) => !v)}
      className="cursor-pointer"
      style={{
        background: 'var(--bg-card)',
        borderRadius: 'var(--radius-card-sm)',
        padding: '18px 18px 16px',
        transition: 'transform 150ms ease-out',
      }}
    >
      {/* 상단: 방향 dot + 소스 레이블 + 시간 */}
      <div className="flex items-center" style={{ gap: 6, marginBottom: 10 }}>
        <span
          style={{
            width: 6,
            height: 6,
            borderRadius: '50%',
            background: color,
            flexShrink: 0,
          }}
        />
        <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
          {sourceLabel}
        </span>
        <span
          className="ml-auto"
          style={{ fontSize: 11, color: 'var(--text-tertiary)' }}
        >
          {time}
        </span>
      </div>

      {/* 회사명 + 종목코드 */}
      <div className="flex items-baseline" style={{ gap: 8, marginBottom: 4 }}>
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
        {signal.companyCode && (
          <span
            style={{
              fontSize: 11,
              fontWeight: 500,
              color: 'var(--text-tertiary)',
              background: 'var(--bg-inset)',
              borderRadius: 4,
              padding: '1px 5px',
              flexShrink: 0,
            }}
          >
            {signal.companyCode}
          </span>
        )}
      </div>

      {/* 공시 제목 (헤드라인) */}
      <p
        style={{
          fontSize: 13,
          fontWeight: 500,
          color: 'var(--text-secondary)',
          lineHeight: 1.45,
          marginBottom: signal.summary ? 10 : 0,
        }}
      >
        {signal.headline}
      </p>

      {/* 투자 포인트 — LLM 생성 rationale (항상 표시) */}
      {signal.summary && (
        <p
          style={{
            fontSize: 13,
            color: 'var(--text-secondary)',
            lineHeight: 1.6,
            paddingTop: 10,
            borderTop: '1px solid var(--border-subtle)',
          }}
        >
          {signal.summary}
        </p>
      )}

      {/* 펼침 영역: TradingView 차트 + 딥링크 */}
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
