// Week 5a (DECISIONS #13):
// - 'picks' 탭 제거 (경제 탭 내부 섹션으로 이동)
// - scope: 'all' 옵션 제거, default='domestic'
// - Week 5b 에서 'ai' 탭 추가 예정
export type Tab = 'ai' | 'current' | 'economy'
export type Scope = 'domestic' | 'foreign'

const TABS_SET: ReadonlySet<string> = new Set(['ai', 'current', 'economy'])
const SCOPES_SET: ReadonlySet<string> = new Set(['domestic', 'foreign'])

const DEFAULT_TAB: Tab = 'current' // Week 5a 임시 default. Week 5b 에서 'ai' 로 전환.
const DEFAULT_SCOPE: Scope = 'domestic'

export function parseTabFromSearch(search: URLSearchParams | string): Tab {
  const p = typeof search === 'string' ? new URLSearchParams(search) : search
  const v = p.get('tab')
  return TABS_SET.has(v ?? '') ? (v as Tab) : DEFAULT_TAB
}

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

export function tabHref(
  tab: Tab,
  scope: Scope = DEFAULT_SCOPE,
  date?: string | null,
): string {
  const p = new URLSearchParams()
  if (date) p.set('date', date)
  p.set('tab', tab)
  if (scope !== DEFAULT_SCOPE) p.set('scope', scope)
  return `/?${p.toString()}`
}
