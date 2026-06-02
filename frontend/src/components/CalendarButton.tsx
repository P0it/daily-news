'use client'

import { useEffect, useRef, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { fetchBriefingIndex } from '@/lib/fetchBriefing'
import { parseDateFromSearch } from '@/lib/tabs'

function formatDate(dateStr: string, today: string): string {
  const [, m, d] = dateStr.split('-').map(Number)
  const date = new Date(dateStr + 'T00:00:00')
  const dayNames = ['일', '월', '화', '수', '목', '금', '토']
  const day = dayNames[date.getDay()]

  if (dateStr === today) return `오늘 · ${m}월 ${d}일 (${day})`
  return `${m}월 ${d}일 (${day})`
}

export function CalendarButton() {
  const [open, setOpen] = useState(false)
  const [dates, setDates] = useState<string[]>([])
  const router = useRouter()
  const sp = useSearchParams()
  const currentDate = parseDateFromSearch(sp) ?? new Date().toISOString().slice(0, 10)
  const modalRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    fetchBriefingIndex().then(({ dates }) => setDates(dates))
  }, [open])

  useEffect(() => {
    if (!open) return
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open])

  function handleSelect(date: string) {
    router.push(`/?date=${date}`)
    setOpen(false)
  }

  const today = new Date().toISOString().slice(0, 10)

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        aria-label="브리핑 날짜 선택"
        title="브리핑 날짜 선택"
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
            background: 'rgba(0,0,0,0.45)',
            zIndex: 50,
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'flex-end',
            paddingTop: 56,
            paddingRight: 16,
          }}
          onClick={() => setOpen(false)}
        >
          <div
            ref={modalRef}
            style={{
              width: 240,
              maxHeight: 420,
              overflowY: 'auto',
              background: 'var(--surface-1, #fff)',
              borderRadius: 16,
              padding: '8px 0',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ padding: '14px 22px 10px', fontSize: 13, fontWeight: 700, color: 'var(--text-secondary, #8B95A1)', letterSpacing: '0.02em' }}>
              브리핑 날짜
            </div>

            {dates.length === 0 && (
              <div style={{ padding: '12px 22px', fontSize: 15, color: 'var(--text-secondary, #8B95A1)' }}>
                불러오는 중...
              </div>
            )}

            {dates.map((d) => {
              const isSelected = d === currentDate
              return (
                <button
                  key={d}
                  onClick={() => handleSelect(d)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    width: '100%',
                    padding: '11px 22px',
                    background: 'transparent',
                    border: 'none',
                    cursor: 'pointer',
                    textAlign: 'left',
                    fontSize: 15,
                    fontWeight: isSelected ? 700 : 400,
                    color: isSelected ? 'var(--text-primary, #191F28)' : 'var(--text-secondary, #8B95A1)',
                  }}
                  onMouseEnter={(e) => {
                    (e.currentTarget as HTMLButtonElement).style.background = 'var(--surface-2, #F9FAFB)'
                  }}
                  onMouseLeave={(e) => {
                    (e.currentTarget as HTMLButtonElement).style.background = 'transparent'
                  }}
                >
                  <span
                    style={{
                      width: 6,
                      height: 6,
                      borderRadius: '50%',
                      background: isSelected ? 'var(--text-primary, #191F28)' : 'transparent',
                      flexShrink: 0,
                    }}
                  />
                  {formatDate(d, today)}
                </button>
              )
            })}
          </div>
        </div>
      )}
    </>
  )
}
