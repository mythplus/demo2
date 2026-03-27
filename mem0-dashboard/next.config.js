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

  // 修复 Windows 上 webpack 文件缓存反复损坏导致页面崩溃的问题
  // 将持久化文件缓存改为内存缓存，避免 .next 缓存文件不一致
  webpack: (config, { dev }) => {
    if (dev) {
      config.cache = {
        type: 'memory',
      };
    }
    return config;
  },
};

module.exports = nextConfig;
