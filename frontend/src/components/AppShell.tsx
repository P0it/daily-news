'use client'

import { Suspense, useEffect, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { LangToggle } from './LangToggle'
import { ScopeFilter } from './ScopeFilter'
import { TabBar } from './TabBar'
import { ThemeToggle } from './ThemeToggle'
import { getStoredLang, type Lang } from '@/lib/i18n'
import { parseTabFromSearch } from '@/lib/tabs'

function ShellInner({ children }: { children: React.ReactNode }) {
  const sp = useSearchParams()
  const tab = parseTabFromSearch(sp)
  const [lang, setLang] = useState<Lang>('ko')

  useEffect(() => {
    setLang(getStoredLang())
  }, [])

  // 종목 탭만 720px, 그 외는 560px (DESIGN.md 4.2 + 5.13)
  const maxWidth =
    tab === 'picks' ? 'var(--container-picks)' : 'var(--container-briefing)'

  return (
    <>
      <header
        className="flex items-center justify-between px-5 pt-9 pb-3"
        style={{ maxWidth, margin: '0 auto' }}
      >
        <h1
          className="tracking-tight"
          style={{
            fontSize: '26px',
            fontWeight: 700,
            color: 'var(--text-primary)',
            letterSpacing: '-0.03em',
          }}
        >
          데일리 브리핑
        </h1>
        <div className="flex items-center gap-1">
          <LangToggle />
          <ThemeToggle />
        </div>
      </header>
      <div style={{ maxWidth, margin: '0 auto' }}>
        <TabBar lang={lang} />
        <ScopeFilter lang={lang} />
      </div>
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
