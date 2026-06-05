import type { NewsItem } from '@/lib/types'

export type CategoryBadge = { label: string; color: string; bg: string }

export const CATEGORY_META: Record<string, CategoryBadge> = {
  politics:      { label: '정치',    color: '#C84B31', bg: '#FFF0ED' },
  society:       { label: '사회',    color: '#1A6B3C', bg: '#E9F7EF' },
  international: { label: '국제',    color: '#1A56A0', bg: '#EBF3FF' },
  tech:          { label: 'IT·과학', color: '#6B3EC8', bg: '#F3EEFF' },
  ai:            { label: 'AI',      color: '#0B6E6E', bg: '#E6F6F6' },
  stock:         { label: '증시',    color: '#805B00', bg: '#FFF8E1' },
}

/**
 * 뉴스 카드의 주제 분류 뱃지를 결정한다.
 *
 * 모든 카드(AI 소식·시사 뉴스)가 동일하게 '주제'를 1차 태그로 보여주도록
 * 분류 로직을 한곳에 모았다. 글/영상 구분은 소스 라벨(▶ prefix)이 담당하므로
 * 여기서는 다루지 않는다.
 *
 * 해외 scope 의 international 은 뱃지를 달지 않는다 — 해외 탭 자체가 '세계 뉴스'를
 * 의미하므로 모든 카드에 '세계'를 붙이는 건 중복이다. (국내 scope 의 '국제'는
 * 정치·사회·IT 사이에서 '해외 소식'을 구분해주므로 유지)
 */
export function resolveCategoryBadge(news: NewsItem): CategoryBadge | null {
  if (news.scope === 'foreign' && news.category === 'international') {
    return null
  }
  return news.category ? (CATEGORY_META[news.category] ?? null) : null
}
