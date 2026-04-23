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
import { AiSection } from '@/components/AiSection'
import { CurrentSection } from '@/components/CurrentSection'
import { HeroCard } from '@/components/HeroCard'
import { MarketIndices } from '@/components/MarketIndices'
import { PicksSection } from '@/components/PicksSection'
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

  // ───── AI 탭 (Week 5b: default — DECISIONS #13) ─────
  if (tab === 'ai') {
    const aiTab = briefing.tabs.ai ?? { domestic: [], foreign: [] }
    return <AiSection tab={aiTab} scope={scope} dict={dict} />
  }

  // ───── 경제 탭 (Week 5a: picks 내부 통합 + 국내/해외 단일 scope) ─────
  if (tab === 'economy') {
    const economy = briefing.tabs.economy
    const signals = economy.signals.filter((s) => s.scope === scope)
    const picks = economy.picks ?? { domestic: [], foreign: [] }
    const showHero =
      briefing.hero !== null && briefing.hero.scope === scope

    return (
      <div>
        {economy.themeBanner && <ThemeBanner banner={economy.themeBanner} />}
        <PicksSection picks={picks} scope={scope} dict={dict} />
        {showHero && briefing.hero && (
          <HeroCard signal={briefing.hero} dict={dict} />
        )}
        <MarketIndices indices={economy.indices} dict={dict} />
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

  // ───── 시사 탭 (카테고리별 섹션 + 국내/해외 단일 scope) ─────
  const current = briefing.tabs.current
  const filterScope = (arr: NewsItem[]) => arr.filter((n) => n.scope === scope)
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
