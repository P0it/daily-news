'use client'

import { useState, useRef, useEffect } from 'react'

const PHASE_INFO: Record<string, { label: string; color: string; bg: string; desc: string }> = {
  low: {
    label: '초기 선점',
    color: '#2AC769',
    bg: 'rgba(42,199,105,0.12)',
    desc: '시장 대다수가 아직 이 이슈-종목 연결고리를 인식하지 못한 상태예요. 개미 투자자 대비 선행 진입이 가능한 구간이에요.',
  },
  medium: {
    label: '초기 주목',
    color: '#F5A623',
    bg: 'rgba(245,166,35,0.12)',
    desc: '일부 투자자가 주목하기 시작했지만 아직 주류는 아니에요. 진입은 가능하나 초기 선점보다 선점 우위는 낮아요.',
  },
}

interface Props {
  risk: 'low' | 'medium'
}

export function PhaseTag({ risk }: Props) {
  const info = PHASE_INFO[risk]
  if (!info) return null

  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLSpanElement>(null)

  useEffect(() => {
    if (!open) return
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [open])

  return (
    <span
      ref={ref}
      style={{ position: 'relative', display: 'inline-flex', alignItems: 'center', flexShrink: 0 }}
    >
      <button
        onClick={() => setOpen((v) => !v)}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 5,
          padding: '4px 10px',
          borderRadius: 999,
          border: 'none',
          cursor: 'pointer',
          background: info.bg,
          color: info.color,
          fontSize: 11,
          fontWeight: 700,
          flexShrink: 0,
        }}
      >
        {info.label}
      </button>

      {open && (
        <span
          style={{
            position: 'absolute',
            bottom: 'calc(100% + 6px)',
            left: 0,
            zIndex: 100,
            width: 220,
            background: 'var(--bg-card)',
            border: '1px solid var(--border-subtle)',
            color: 'var(--text-secondary)',
            fontSize: 12,
            lineHeight: 1.6,
            padding: '10px 12px',
            borderRadius: 10,
            boxShadow: '0 2px 12px rgba(0,0,0,0.12)',
            pointerEvents: 'none',
          }}
        >
          <span style={{ display: 'block', fontWeight: 700, color: info.color, marginBottom: 4 }}>
            {info.label}
          </span>
          {info.desc}
        </span>
      )}
    </span>
  )
}
