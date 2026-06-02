'use client'

import { Suspense } from 'react'
import { useSearchParams } from 'next/navigation'
import { CalendarButton } from './CalendarButton'
import { ScopeFilter } from './ScopeFilter'
import { ThemeToggle } from './ThemeToggle'
import { parseDateFromSearch } from '@/lib/tabs'

function formatHeaderDate(dateStr: string): string {
  const [, m, d] = dateStr.split('-').map(Number)
  const date = new Date(dateStr + 'T00:00:00')
  const dayNames = ['일', '월', '화', '수', '목', '금', '토']
  return `${m}월 ${d}일 ${dayNames[date.getDay()]}요일`
}

function ShellInner({ children }: { children: React.ReactNode }) {
  const maxWidth = 'var(--container-briefing)'
  const sp = useSearchParams()
  const today = new Date().toISOString().slice(0, 10)
  const dateStr = parseDateFromSearch(sp) ?? today

  return (
    <>
      <nav style={{ background: 'transparent' }}>
        <header
          className="flex items-center justify-between px-5 pt-5 pb-3"
          style={{ maxWidth, margin: '0 auto' }}
        >
          <div className="flex flex-col gap-0.5">
            <h1
              className="tracking-tight"
              style={{
                fontSize: '26px',
                fontWeight: 700,
                color: 'var(--color-text-secondary)',
                letterSpacing: '-0.03em',
              }}
            >
              데일리 브리핑
            </h1>
            <span style={{ fontSize: 13, fontWeight: 400, color: 'var(--text-secondary, #8B95A1)' }}>
              {formatHeaderDate(dateStr)}
            </span>
          </div>
          <div className="flex items-center gap-1">
            <CalendarButton />
            <ThemeToggle />
          </div>
        </header>
        <div style={{ maxWidth, margin: '0 auto' }}>
          <ScopeFilter lang="ko" />
        </div>
      </nav>
      <main style={{ maxWidth, margin: '0 auto', minHeight: '100vh' }} className="pb-20">
        {children}
      </main>
    </>
  )
}

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <Suspense fallback={<div style={{ height: 200 }} />}>
      <ShellInner>{children}</ShellInner>
    </Suspense>
  )
}
