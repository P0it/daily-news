/** @type {import('next').NextConfig} */

// 시세 프록시는 배포 환경에서 vercel.json rewrites가 처리한다. 하지만
// `next dev`(static export)에서는 vercel.json이 적용되지 않아 /api/* 호출이
// 깨지고, 성과 탭이 정적 시세(추천가=현재가 → 0%)에 묶인다. dev에서만 같은
// 프록시를 next.config로 재현해 로컬에서도 실시간 시세가 살아나게 한다.
const devProxyRewrites = async () => [
  {
    source: '/api/naver-stock/:ticker/',
    destination: 'https://m.stock.naver.com/api/stock/:ticker/basic',
  },
  {
    source: '/api/yahoo-stock/:ticker/',
    destination:
      'https://query1.finance.yahoo.com/v8/finance/chart/:ticker?interval=1d&range=1d',
  },
];

const nextConfig = {
  output: 'export',
  images: { unoptimized: true },
  trailingSlash: true,
  ...(process.env.NODE_ENV === 'development' ? { rewrites: devProxyRewrites } : {}),
};

export default nextConfig;
