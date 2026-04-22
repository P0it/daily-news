import type { GlossaryEntry } from '@/lib/types'

let _cache: Record<string, GlossaryEntry> = {}

export function setGlossary(g: Record<string, GlossaryEntry> | undefined) {
  _cache = g ?? {}
}

export function getGlossary(termId: string | null | undefined): GlossaryEntry | null {
  if (!termId) return null
  return _cache[termId] ?? null
}
