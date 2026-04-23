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

  // Week 5a: 모든 탭 560px 단일 (종목 탭 격하, DECISIONS #13)
  // `tab` 은 향후 AI 탭 추가 시 분기에 사용 (현재는 너비 동일)
  void tab
  const maxWidth = 'var(--container-briefing)'

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
