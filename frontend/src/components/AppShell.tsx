'use client'

import { Suspense, useEffect, useState } from 'react'
import { LangToggle } from './LangToggle'
import { ScopeFilter } from './ScopeFilter'
import { TabBar } from './TabBar'
import { ThemeToggle } from './ThemeToggle'
import { getStoredLang, type Lang } from '@/lib/i18n'

export function AppShell({ children }: { children: React.ReactNode }) {
  const [lang, setLang] = useState<Lang>('ko')

  useEffect(() => {
    setLang(getStoredLang())
  }, [])

  return (
    <>
      <header
        className="flex items-center justify-between px-5 pt-9 pb-3"
        style={{ maxWidth: 'var(--container-briefing)', margin: '0 auto' }}
      >
        <h1
          className="tracking-tight"
          style={{
            fontSize: '26px',
            fontWeight: 700,
            color: 'var(--text-primary)',
          }}
        >
          데일리 브리핑
        </h1>
        <div className="flex items-center gap-1">
          <LangToggle />
          <ThemeToggle />
        </div>
      </header>
      <div style={{ maxWidth: 'var(--container-briefing)', margin: '0 auto' }}>
        <Suspense fallback={<div style={{ height: 60 }} />}>
          <TabBar lang={lang} />
        </Suspense>
        <Suspense fallback={<div style={{ height: 48 }} />}>
          <ScopeFilter lang={lang} />
        </Suspense>
      </div>
      <main
        style={{ maxWidth: 'var(--container-briefing)', margin: '0 auto' }}
        className="pb-20"
      >
        {children}
      </main>
    </>
  )
}
