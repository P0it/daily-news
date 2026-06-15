export type Scope = 'domestic' | 'foreign' | 'picks'

const SCOPES_SET: ReadonlySet<string> = new Set(['domestic', 'foreign', 'picks'])
const DEFAULT_SCOPE: Scope = 'foreign'

export function parseScopeFromSearch(search: URLSearchParams | string): Scope {
  const p = typeof search === 'string' ? new URLSearchParams(search) : search
  const v = p.get('scope')
  return SCOPES_SET.has(v ?? '') ? (v as Scope) : DEFAULT_SCOPE
}

export function parseDateFromSearch(search: URLSearchParams | string): string | null {
  const p = typeof search === 'string' ? new URLSearchParams(search) : search
  const v = p.get('date')
  return v && /^\d{4}-\d{2}-\d{2}$/.test(v) ? v : null
}

export function scopeHref(scope: Scope, date?: string | null): string {
  const p = new URLSearchParams()
  if (date) p.set('date', date)
  // scope는 항상 명시적으로 포함 — 생략하면 static export 에서 useSearchParams 가 갱신되지 않는 이슈 발생
  p.set('scope', scope)
  return `/?${p.toString()}`
}
