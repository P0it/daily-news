export interface Dict {
  'tab.ai': string
  'tab.current': string
  'tab.economy': string
  'tab.picks': string
  'scope.all': string
  'scope.domestic': string
  'scope.foreign': string
  'scope.international': string
  'hero.today': string
  'signal.positive': string
  'signal.negative': string
  'signal.mixed': string
  'signal.neutral': string
  'cta.more': string
  'cta.seeAll': (n: number) => string
  'cta.open': string
  'cta.openOriginal': string
  'empty.economy': string
  'empty.current': string
  loading: string
  'error.fetch': string
  'error.retry': string
  'install.title': string
  'install.subtitle': string
  'install.cta': string
  'install.dismiss': string
  'glossary.heading': (label: string) => string
  'glossary.acknowledge': string
  marketIndicesTitle: string
  updatedAt: (time: string) => string
  'count.signals': (n: number) => string
  'count.news': (n: number) => string
}

export const ko: Dict = {
  'tab.ai': 'AI',
  'tab.current': '시사',
  'tab.economy': '경제',
  'tab.picks': '종목',
  'scope.all': '전체',
  'scope.domestic': '국내',
  'scope.foreign': '해외',
  'scope.international': '국제',
  'hero.today': '지금 가장 중요해요',
  'signal.positive': '긍정 시그널',
  'signal.negative': '주의할 공시',
  'signal.mixed': '복합 시그널',
  'signal.neutral': '중립',
  'cta.more': '자세히 →',
  'cta.seeAll': (n: number) => `전체 ${n}건 모두 보기 →`,
  'cta.open': '열기',
  'cta.openOriginal': '공시 원문 보기',
  'empty.economy': '오늘은 조용한 장이에요. 주목할 공시가 없어요.',
  'empty.current': '아직 오늘 새 소식이 많지 않아요. 곧 업데이트될 거예요.',
  'loading': '불러오는 중이에요.',
  'error.fetch': '잠깐, 불러오지 못했어요.',
  'error.retry': '다시 시도해볼까요?',
  'install.title': '홈 화면에 추가해보세요',
  'install.subtitle': '앱처럼 바로 열려요',
  'install.cta': '설치',
  'install.dismiss': '닫기',
  'glossary.heading': (label: string) => `${label}가 뭐예요?`,
  'glossary.acknowledge': '알겠어요',
  'marketIndicesTitle': '오늘 시장',
  'updatedAt': (time: string) => `${time}에 업데이트했어요`,
  'count.signals': (n: number) => `공시 ${n}건`,
  'count.news': (n: number) => `뉴스 ${n}건`,
}
