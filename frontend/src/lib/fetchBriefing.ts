import type { Briefing, PickRecord } from '@/lib/types'
import { supabase } from '@/lib/supabase'

function todayKey(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export async function fetchBriefing(date?: string): Promise<Briefing> {
  const key = date ?? todayKey()
  const { data, error } = await supabase
    .from('briefings')
    .select('data')
    .eq('date', key)
    .single()

  if (error || !data) {
    throw new Error(`briefing fetch failed: ${error?.message ?? 'not found'}`)
  }
  return data.data as Briefing
}

export async function fetchBriefingIndex(): Promise<{ dates: string[] }> {
  const { data, error } = await supabase
    .from('briefings')
    .select('date')
    .order('date', { ascending: false })
    .limit(30)

  if (error || !data) return { dates: [] }
  return { dates: data.map((r) => r.date) }
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
