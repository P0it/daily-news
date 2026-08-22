'use client'

import { useState, type CSSProperties } from 'react'
import type { SurgeItem } from '@/lib/types'
import { resolveTickerToSymbol } from '@/lib/tradingview'
import { StockChartPanel } from '@/components/StockChartPanel'
import { StockLogo } from '@/components/StockLogo'

// 코드 칩 — HotIssuesCard 와 동일 스타일 유지
const CODE_CHIP_STYLE: CSSProperties = {
  fontSize: 10,
  fontWeight: 700,
  color: 'var(--badge-text)',
  background: 'var(--badge-bg)',
  padding: '1px 6px',
  borderRadius: 5,
  letterSpacing: '0.02em',
  flexShrink: 0,
}

// 한국 시장 관례: 상승 빨강, 하락 파랑
function changeColor(pct: number): string {
  if (pct > 0) return '#F04452'
  if (pct < 0) return '#3182F6'
  return 'var(--text-secondary)'
}

// 원 단위 → 억/조 축약 (거래대금·시총 표시용)
function formatKRW(won: number): string {
  if (won >= 1e12) return `${(won / 1e12).toFixed(1)}조`
  return `${Math.round(won / 1e8).toLocaleString()}억`
}

function SurgeRow({ item }: { item: SurgeItem }) {
  const [open, setOpen] = useState(false)
  const symbol = resolveTickerToSymbol(item.code) // .KQ 접미사 대신 6자리 코드로 KRX 해석

  return (
    <div
      style={{
        background: 'var(--bg-inset)',
        borderRadius: 10,
        padding: '14px 14px',
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
      }}
    >
      {/* 종목명 + 코드 칩 + 시장 + 차트 버튼 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <StockLogo ticker={item.code} name={item.name} size={24} />
        <span style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)', lineHeight: 1.2 }}>
          {item.name}
        </span>
        <span style={CODE_CHIP_STYLE}>{item.code}</span>
        <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{item.market}</span>
        {symbol && (
          <button
            onClick={() => setOpen((v) => !v)}
            title={open ? '차트 닫기' : '네이버 증권 차트'}
            style={{
              marginLeft: 'auto',
              background: open ? 'var(--bg-card)' : 'transparent',
              border: 'none',
              borderRadius: 6,
              padding: '2px 6px',
              cursor: 'pointer',
              fontSize: 15,
              lineHeight: 1,
              flexShrink: 0,
              display: 'inline-flex',
              alignItems: 'center',
            }}
          >
            📊
          </button>
        )}
      </div>

      {/* 핵심 숫자 — 거래대금 배수가 주인공 */}
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 24, fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>
          {item.valueMultiple.toLocaleString()}배
        </span>
        <span style={{ fontSize: 13, color: 'var(--text-tertiary)' }}>평소 거래대금 대비</span>
        <span style={{ fontSize: 15, fontWeight: 700, color: changeColor(item.changePct), marginLeft: 'auto' }}>
          {item.changePct > 0 ? '+' : ''}{item.changePct.toFixed(2)}%
        </span>
      </div>

      {/* 보조 숫자 — 거래대금·종가·시총 */}
      <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
        거래대금 {formatKRW(item.value)} · 종가 {item.close.toLocaleString()}원 · 시총 {formatKRW(item.marketCap)}
      </div>

      {/* 왜 올랐나 — 같은 기간 공시. 없으면 그 자체가 정보(이유 미확인) */}
      {item.disclosures.length > 0 ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          {item.disclosures.map((title, i) => (
            <p key={i} style={{ margin: 0, fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
              📄 {title}
            </p>
          ))}
        </div>
      ) : (
        <p style={{ margin: 0, fontSize: 12, color: 'var(--text-tertiary)', lineHeight: 1.5 }}>
          공시가 없어요. 왜 올랐는지는 아직 확인되지 않았어요
        </p>
      )}

      {/* 차트 펼침 */}
      {open && symbol && (
        <StockChartPanel code={item.code} symbol={symbol} isKrx name={item.name} />
      )}
    </div>
  )
}

export function SurgeCard({ items }: { items: SurgeItem[] }) {
  if (!items || items.length === 0) return null

  return (
    <section
      className="mx-4 mb-2.5"
      style={{ background: 'var(--bg-card)', borderRadius: 'var(--radius-card)', padding: '20px 22px' }}
    >
      <div
        style={{
          fontSize: 11,
          fontWeight: 700,
          letterSpacing: '0.08em',
          textTransform: 'uppercase',
          color: 'var(--text-tertiary)',
          marginBottom: 10,
        }}
      >
        📊 어제 거래대금이 몰린 종목
      </div>
      <p style={{ margin: '0 0 18px', fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
        골라드린 게 아니라 이미 시장이 크게 움직인 종목이에요. 왜 올랐는지 공시로 되짚어 보세요
      </p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {items.map((item) => (
          <SurgeRow key={item.code} item={item} />
        ))}
      </div>
    </section>
  )
}
