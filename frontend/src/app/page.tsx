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
import { CurrentNewsCard } from '@/components/CurrentNewsCard'
import { HotIssuesCard } from '@/components/HotIssuesCard'
import { PicksHistoryView } from '@/components/PicksHistoryView'

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

  if (scope === 'picks') {
    return <PicksHistoryView />
  }

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
  // Phase 4 제외, 해당 scope의 positive 시그널 — Phase 1 우선 정렬
  const signals = economy.signals.filter(
    (s) => s.scope === scope && s.direction === 'positive' && (s.attentionPhase ?? 2) < 4
  )
  const aiTab = briefing.tabs.ai ?? { domestic: [], foreign: [] }
  const aiItems = scope === 'foreign' ? aiTab.foreign : aiTab.domestic

  const current = briefing.tabs.current
  const filterScope = (arr: NewsItem[]) => arr.filter((n) => n.scope === scope)
  // 같은 기사가 여러 카테고리에 분류될 수 있어 id 기준 중복 제거 (React key 충돌 방지)
  const dedupeById = (arr: NewsItem[]) => {
    const seen = new Set<string>()
    return arr.filter((n) => (seen.has(n.id) ? false : (seen.add(n.id), true)))
  }
  const allCurrentNews = dedupeById([
    ...filterScope(current.politics),
    ...filterScope(current.society),
    ...filterScope(current.international),
    ...filterScope(current.tech),
  ]).sort((a, b) => new Date(b.time).getTime() - new Date(a.time).getTime())
  const hasCurrentNews = allCurrentNews.length > 0

  return (
    <div>
      {/* ── 경제 섹션 ── */}
      <SectionLabel>경제</SectionLabel>

      {economy.hotIssues && (
        (scope === 'foreign' ? economy.hotIssues.foreign : economy.hotIssues.domestic).length > 0 && (
          <HotIssuesCard
            issues={scope === 'foreign' ? economy.hotIssues.foreign : economy.hotIssues.domestic}
            scope={scope}
          />
        )
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

          {/* 시사 뉴스 — 카테고리 태그와 함께 시간순 */}
          {hasCurrentNews && (
            <div style={{ paddingTop: 8 }}>
              {allCurrentNews.map((n) => (
                <CurrentNewsCard key={n.id} news={n} dict={dict} />
              ))}
            </div>
          )}
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
