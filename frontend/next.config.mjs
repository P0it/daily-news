/** @type {import('next').NextConfig} */
const nextConfig = {
  images: { unoptimized: true },
  trailingSlash: true,
  async rewrites() {
    return [
      {
        source: '/api/naver-stock/:ticker/',
        destination: 'https://m.stock.naver.com/api/stock/:ticker/basic',
      },
      {
        source: '/api/yahoo-stock/:ticker/',
        destination: 'https://query1.finance.yahoo.com/v8/finance/chart/:ticker?interval=1d&range=1d',
      },
    ]
  },
};

export default nextConfig;
