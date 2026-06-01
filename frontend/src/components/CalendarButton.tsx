'use client'

import { useEffect, useRef, useState } from 'react'

function EconomicCalendarWidget() {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    el.innerHTML = ''

    const isDark = document.documentElement.classList.contains('dark')
    const script = document.createElement('script')
    script.src =
      'https://s3.tradingview.com/external-embedding/embed-widget-events.js'
    script.async = true
    script.innerHTML = JSON.stringify({
      colorTheme: isDark ? 'dark' : 'light',
      isTransparent: true,
      width: '100%',
      height: 500,
      locale: 'ko',
      importanceFilter: '0,1',
      countryFilter: 'us,eu,gb,jp,cn,kr',
    })
    el.appendChild(script)
    return () => {
      if (el) el.innerHTML = ''
    }
  }, [])

  return (
    <div
      ref={containerRef}
      className="tradingview-widget-container"
      style={{ height: 500 }}
      aria-label="경제 캘린더"
    />
  )
}

export function CalendarButton() {
  const [open, setOpen] = useState(false)

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        aria-label="경제 일정 보기"
        title="경제 일정"
        className="flex items-center justify-center rounded-full"
        style={{ width: 36, height: 36, color: 'var(--text-secondary, #8B95A1)' }}
      >
        <svg
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden
        >
          <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
          <line x1="16" y1="2" x2="16" y2="6" />
          <line x1="8" y1="2" x2="8" y2="6" />
          <line x1="3" y1="10" x2="21" y2="10" />
        </svg>
      </button>

      {open && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.5)',
            zIndex: 50,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '20px',
          }}
          onClick={() => setOpen(false)}
        >
          <div
            style={{
              width: '100%',
              maxWidth: 680,
              background: 'var(--surface-1, #fff)',
              borderRadius: 16,
              overflow: 'hidden',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '20px 22px 12px',
              }}
            >
              <span style={{ fontSize: 17, fontWeight: 700 }}>경제 일정</span>
              <button
                onClick={() => setOpen(false)}
                aria-label="닫기"
                style={{
                  width: 32,
                  height: 32,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  borderRadius: '50%',
                  color: 'var(--text-secondary, #8B95A1)',
                  background: 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                }}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden>
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>
            <EconomicCalendarWidget />
          </div>
        </div>
      )}
    </>
  )
}
