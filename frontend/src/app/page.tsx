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
import { CurrentNewsCard } from '@/components/CurrentNewsCard'
import { HeroCard } from '@/components/HeroCard'
import { MarketIndices } from '@/components/MarketIndices'
import { SignalCard } from '@/components/SignalCard'

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

  if (tab === 'economy') {
    const signals = briefing.tabs.economy.signals.filter(
      (s) => scope === 'all' || s.scope === scope,
    )

    return (
      <div>
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

  // current tab — 모든 카테고리를 시간 역순으로 섞고, scope 필터 적용
  const current = briefing.tabs.current
  const allNews: NewsItem[] = [
    ...current.politics,
    ...current.society,
    ...current.international,
    ...current.tech,
  ]
    .filter((n) => {
      if (scope === 'all') return true
      if (scope === 'domestic') return n.scope === 'domestic'
      return n.scope === 'foreign'
    })
    .sort((a, b) => {
      // "전체" 모드는 최신순으로 섞음. 같은 시간이면 source 기준 tie-break.
      const ta = new Date(a.time).getTime()
      const tb = new Date(b.time).getTime()
      if (tb !== ta) return tb - ta
      return a.source.localeCompare(b.source)
    })

  if (allNews.length === 0) {
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
      {allNews.map((n) => (
        <CurrentNewsCard key={n.id} news={n} dict={dict} />
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
