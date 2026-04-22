# news-briefing frontend

Next.js 16 static export PWA. Vercel 에 배포.

## Dev

```bash
cd frontend
npm install
npm run dev  # http://localhost:3000
```

## Build

```bash
npm run build   # → frontend/out/
```

## Data source

`frontend/public/briefings/YYYY-MM-DD.json` 은 백엔드 `python -m news_briefing morning`
실행 시 자동 생성. `frontend/public/briefings/index.json` 에 날짜 목록.

빌드 시 `out/briefings/` 로 복사되어 정적 파일로 서빙.

## Stack

- Next.js 16 (App Router + static export)
- React 19
- Tailwind CSS 4
- TypeScript 5
- Pretendard Variable (CDN)
- Custom service worker (no workbox)

## Deployment

Vercel 에 GitHub 저장소 연결. 루트 `vercel.json` 이 빌드 설정을 가짐.
