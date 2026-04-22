import type { Briefing } from '@/lib/types'

function todayKey(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export async function fetchBriefing(date?: string): Promise<Briefing> {
  const key = date ?? todayKey()
  const resp = await fetch(`/briefings/${key}.json`, { cache: 'no-cache' })
  if (!resp.ok) {
    throw new Error(`briefing fetch failed: ${resp.status}`)
  }
  return resp.json()
}

export async function fetchBriefingIndex(): Promise<{ dates: string[] }> {
  const resp = await fetch('/briefings/index.json', { cache: 'no-cache' })
  if (!resp.ok) return { dates: [] }
  return resp.json()
}

export async function fetchLatestBriefing(): Promise<Briefing | null> {
  try {
    return await fetchBriefing()
  } catch {
    // 오늘 파일이 없으면 index.json 최신 날짜로 재시도
    const index = await fetchBriefingIndex()
    if (index.dates.length === 0) return null
    try {
      return await fetchBriefing(index.dates[0])
    } catch {
      return null
    }
  }
}
