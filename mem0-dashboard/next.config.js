/** @type {import('next').NextConfig} */
const nextConfig = {
  // 允许跨域请求 Mem0 API
  async rewrites() {
    return [
      {
        source: '/api/mem0/:path*',
        destination: `${process.env.NEXT_PUBLIC_MEM0_API_URL || 'http://localhost:8080'}/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
