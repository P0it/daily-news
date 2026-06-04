'use client'

import { useState } from 'react'

interface StockLogoProps {
  ticker: string | null
  name: string
  size?: number
}

function getLogoUrl(ticker: string): string {
  return `https://static.toss.im/png-icons/securities/icn-sec-fill-${ticker}.png`
}

// 종목 이름에서 의미있는 첫 글자 추출
function getInitial(name: string): string {
  const match = name.trim().match(/[가-힣A-Za-z0-9]/)
  return match ? match[0].toUpperCase() : name.trim().charAt(0)
}

// ticker 해시 기반 결정적 색상
function getColors(ticker: string): { bg: string; text: string } {
  const palette = [
    { bg: '#EBF4FF', text: '#1A6EB5' },
    { bg: '#EDFAF3', text: '#1A7A40' },
    { bg: '#FFF8EC', text: '#8A6000' },
    { bg: '#F5F0FF', text: '#5B2DA0' },
    { bg: '#FFF0F0', text: '#A02020' },
  ]
  const idx = [...ticker].reduce((acc, c) => acc + c.charCodeAt(0), 0) % palette.length
  return palette[idx]
}

function InitialAvatar({ ticker, name, size }: { ticker: string; name: string; size: number }) {
  const { bg, text } = getColors(ticker)
  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: 6,
        background: bg,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
        overflow: 'hidden',
      }}
    >
      <span style={{ fontSize: Math.round(size * 0.46), fontWeight: 700, color: text, lineHeight: 1 }}>
        {getInitial(name)}
      </span>
    </div>
  )
}

export function StockLogo({ ticker, name, size = 28 }: StockLogoProps) {
  const effectiveTicker = ticker ?? ''
  const [failed, setFailed] = useState(!effectiveTicker)

  if (failed) {
    return <InitialAvatar ticker={effectiveTicker || name} name={name} size={size} />
  }

  const logoUrl = getLogoUrl(effectiveTicker)

  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: 6,
        flexShrink: 0,
        overflow: 'hidden',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'var(--bg-card)',
      }}
    >
      <img
        src={logoUrl}
        alt={name}
        width={size}
        height={size}
        style={{ objectFit: 'contain', width: size, height: size, display: 'block' }}
        onError={() => setFailed(true)}
      />
    </div>
  )
}
