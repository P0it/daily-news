export type Tab = 'current' | 'economy' | 'picks'
export type Scope = 'all' | 'domestic' | 'foreign'

const TABS_SET: ReadonlySet<string> = new Set(['current', 'economy', 'picks'])
const SCOPES_SET: ReadonlySet<string> = new Set(['all', 'domestic', 'foreign'])

export function parseTabFromSearch(search: URLSearchParams | string): Tab {
  const p = typeof search === 'string' ? new URLSearchParams(search) : search
  const v = p.get('tab')
  return TABS_SET.has(v ?? '') ? (v as Tab) : 'current'
}

export function parseScopeFromSearch(search: URLSearchParams | string): Scope {
  const p = typeof search === 'string' ? new URLSearchParams(search) : search
  const v = p.get('scope')
  return SCOPES_SET.has(v ?? '') ? (v as Scope) : 'all'
}

export function parseDateFromSearch(search: URLSearchParams | string): string | null {
  const p = typeof search === 'string' ? new URLSearchParams(search) : search
  const v = p.get('date')
  return v && /^\d{4}-\d{2}-\d{2}$/.test(v) ? v : null
}

export function tabHref(
  tab: Tab,
  scope: Scope = 'all',
  date?: string | null,
): string {
  const p = new URLSearchParams()
  if (date) p.set('date', date)
  p.set('tab', tab)
  if (scope !== 'all') p.set('scope', scope)
  return `/?${p.toString()}`
}
