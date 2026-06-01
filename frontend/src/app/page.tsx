'use client'

import { Suspense, useEffect, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import {
  fetchBriefing,
  fetchLatestBriefing,
} from '@/lib/fetchBriefing'
import { setGlossary } from '@/lib/glossaryStore'
import { getStoredLang, t, type Lang } from '@/lib/i18n'
import { parseDateFromSearch, parseScopeFromSearch } from '@/lib/tabs'
import type { Briefing, NewsItem } from '@/lib/types'
import { AiCard } from '@/components/AiCard'
import { CurrentSection } from '@/components/CurrentSection'
import { HeroCard } from '@/components/HeroCard'
import { SignalCard } from '@/components/SignalCard'
import { ThemeBanner } from '@/components/ThemeBanner'

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        fontSize: 11,
        fontWeight: 700,
        letterSpacing: '0.08em',
        textTransform: 'uppercase',
        color: 'var(--text-tertiary)',
        padding: '28px 20px 10px',
      }}
    >
      {children}
    </div>
  )
}

function Divider() {
  return (
    <div
      style={{
        height: 1,
        background: 'var(--border-subtle)',
        margin: '8px 20px 0',
      }}
    />
  )
}

function HomeInner() {
  const sp = useSearchParams()
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

  const economy = briefing.tabs.economy
  const signals = economy.signals.filter((s) => s.scope === scope && s.direction === 'positive')
  const showHero = briefing.hero !== null && briefing.hero.scope === scope

  const aiTab = briefing.tabs.ai ?? { domestic: [], foreign: [] }
  const aiItems = scope === 'foreign' ? aiTab.foreign : aiTab.domestic

  const current = briefing.tabs.current
  const filterScope = (arr: NewsItem[]) => arr.filter((n) => n.scope === scope)
  const categories = ['politics', 'society', 'international', 'tech'] as const
  const hasCurrentNews = categories.some((c) => filterScope(current[c]).length > 0)

  return (
    <div>
      {/* ── 경제 섹션 ── */}
      <SectionLabel>경제</SectionLabel>

      {showHero && briefing.hero && (
        <HeroCard signal={briefing.hero} dict={dict} />
      )}

      {economy.themeBanner && (
        <ThemeBanner banner={economy.themeBanner} />
      )}

      {signals.length > 0 && (
        <div style={{ marginTop: 4 }}>
          {signals.map((s) => (
            <SignalCard key={s.id} signal={s} dict={dict} />
          ))}
        </div>
      )}

      {/* ── 뉴스 섹션 ── */}
      {(aiItems.length > 0 || hasCurrentNews) && (
        <>
          <Divider />
          <SectionLabel>뉴스</SectionLabel>

          {/* AI 소식 */}
          {aiItems.length > 0 && (
            <div style={{ paddingBottom: hasCurrentNews ? 8 : 0 }}>
              {aiItems.map((n) => (
                <AiCard key={n.id} news={n} dict={dict} />
              ))}
            </div>
          )}

          {/* 시사 카테고리 */}
          {hasCurrentNews &&
            categories.map((cat) => (
              <CurrentSection
                key={cat}
                category={cat}
                news={filterScope(current[cat])}
                dict={dict}
                hideLabel={scope === 'foreign' && cat === 'international'}
              />
            ))}
        </>
      )}
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
