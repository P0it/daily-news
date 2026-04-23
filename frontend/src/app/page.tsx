'use client'

import { Suspense, useEffect, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import {
  fetchBriefing,
  fetchLatestBriefing,
} from '@/lib/fetchBriefing'
import { setGlossary } from '@/lib/glossaryStore'
import { getStoredLang, t, type Lang } from '@/lib/i18n'
import {
  parseDateFromSearch,
  parseScopeFromSearch,
  parseTabFromSearch,
} from '@/lib/tabs'
import type { Briefing, NewsItem } from '@/lib/types'
import { CurrentSection } from '@/components/CurrentSection'
import { HeroCard } from '@/components/HeroCard'
import { MarketIndices } from '@/components/MarketIndices'
import { PicksGrid } from '@/components/PicksGrid'
import { SignalCard } from '@/components/SignalCard'
import { ThemeBanner } from '@/components/ThemeBanner'

function HomeInner() {
  const sp = useSearchParams()
  const tab = parseTabFromSearch(sp)
  const scope = parseScopeFromSearch(sp)
  const date = parseDateFromSearch(sp)
  const [briefing, setBriefing] = useState<Briefing | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [lang, setLang] = useState<Lang>('ko')

  useEffect(() => {
    setLang(getStoredLang())
  }, [])

  useEffect(() => {
    let cancelled = false
    async function run() {
      try {
        const b = date
          ? await fetchBriefing(date)
          : await fetchLatestBriefing()
        if (cancelled) return
        if (!b) {
          setError('empty')
          return
        }
        setBriefing(b)
        setGlossary(b.glossary)
      } catch (e) {
        if (!cancelled) setError(String(e))
      }
    }
    run()
    return () => {
      cancelled = true
    }
  }, [date])

  const dict = t(lang)

  if (error) {
    return (
      <p className="px-5 py-20 text-center" style={{ color: 'var(--text-secondary)' }}>
        {dict['error.fetch']}
      </p>
    )
  }

  if (!briefing) {
    return (
      <p className="px-5 py-20 text-center" style={{ color: 'var(--text-secondary)' }}>
        {dict.loading}
      </p>
    )
  }

  if (tab === 'picks') {
    const picks = briefing.tabs.picks ?? { domestic: [], foreign: [] }
    return <PicksGrid picks={picks} dict={dict} />
  }

  if (tab === 'economy') {
    const signals = briefing.tabs.economy.signals.filter(
      (s) => scope === 'all' || s.scope === scope,
    )

    return (
      <div>
        {briefing.tabs.economy.themeBanner && (
          <ThemeBanner banner={briefing.tabs.economy.themeBanner} />
        )}
        {briefing.hero && <HeroCard signal={briefing.hero} dict={dict} />}
        <MarketIndices indices={briefing.tabs.economy.indices} dict={dict} />
        {signals.length === 0 ? (
          <p
            className="px-5 py-16 text-center"
            style={{ color: 'var(--text-secondary)' }}
          >
            {dict['empty.economy']}
          </p>
        ) : (
          signals.map((s) => <SignalCard key={s.id} signal={s} dict={dict} />)
        )}
      </div>
    )
  }

  // current tab — 카테고리별 섹션 렌더 + scope 필터
  const current = briefing.tabs.current
  const filterScope = (arr: NewsItem[]) =>
    arr.filter((n) => {
      if (scope === 'all') return true
      if (scope === 'domestic') return n.scope === 'domestic'
      return n.scope === 'foreign'
    })
  const sections: Array<'politics' | 'society' | 'international' | 'tech'> = [
    'politics',
    'society',
    'international',
    'tech',
  ]
  const hasAny = sections.some((s) => filterScope(current[s]).length > 0)
  if (!hasAny) {
    return (
      <p
        className="px-5 py-16 text-center"
        style={{ color: 'var(--text-secondary)' }}
      >
        {dict['empty.current']}
      </p>
    )
  }
  return (
    <div>
      {sections.map((s) => (
        <CurrentSection
          key={s}
          category={s}
          news={filterScope(current[s])}
          dict={dict}
        />
      ))}
    </div>
  )
}

export default function HomePage() {
  return (
    <Suspense fallback={null}>
      <HomeInner />
    </Suspense>
  )
}
