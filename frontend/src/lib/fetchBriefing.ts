import type { Briefing, Discovery, PickRecord } from '@/lib/types'

function todayKey(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export async function fetchBriefing(date?: string): Promise<Briefing> {
  const key = date ?? todayKey()
  const res = await fetch(`/briefings/${key}.json`, { cache: 'no-store' })
  if (!res.ok) throw new Error(`briefing fetch failed: ${res.status}`)
  return res.json() as Promise<Briefing>
}

export async function fetchBriefingIndex(): Promise<{ dates: string[] }> {
  try {
    const res = await fetch('/briefings/index.json', { cache: 'no-store' })
    if (!res.ok) return { dates: [] }
    return res.json()
  } catch {
    return { dates: [] }
  }
}

export async function fetchPicksHistory(): Promise<PickRecord[]> {
  try {
    const res = await fetch('/picks_history.json', { cache: 'no-store' })
    if (!res.ok) return []
    const json = await res.json()
    return (json.records ?? []) as PickRecord[]
  } catch {
    return []
  }
}

export async function fetchDiscovery(): Promise<Discovery | null> {
  try {
    const res = await fetch('/discovery.json', { cache: 'no-store' })
    if (!res.ok) return null
    return (await res.json()) as Discovery
  } catch {
    return null
  }
}

export async function fetchLatestBriefing(): Promise<Briefing | null> {
  try {
    return await fetchBriefing()
  } catch {
    const index = await fetchBriefingIndex()
    if (index.dates.length === 0) return null
    try {
      return await fetchBriefing(index.dates[0])
    } catch {
      return null
    }
  }
}
