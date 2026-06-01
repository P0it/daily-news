'use client'

import { Suspense } from 'react'
import { CalendarButton } from './CalendarButton'
import { ScopeFilter } from './ScopeFilter'
import { ThemeToggle } from './ThemeToggle'

function ShellInner({ children }: { children: React.ReactNode }) {
  const maxWidth = 'var(--container-briefing)'

  return (
    <>
      <nav style={{ background: 'transparent' }}>
        <header
          className="flex items-center justify-between px-5 pt-5 pb-3"
          style={{ maxWidth, margin: '0 auto' }}
        >
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
          <div className="flex items-center gap-1">
            <CalendarButton />
            <ThemeToggle />
          </div>
        </header>
        <div style={{ maxWidth, margin: '0 auto' }}>
          <ScopeFilter lang="ko" />
        </div>
      </nav>
      <main style={{ maxWidth, margin: '0 auto' }} className="pb-20">
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
