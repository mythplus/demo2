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
  webpack: (config, { dev, isServer }) => {
    if (dev) {
      config.cache = {
        type: 'memory',
      };
    }

    // 生产构建优化：将大型库拆分为独立 chunk
    if (!dev && !isServer) {
      config.optimization = {
        ...config.optimization,
        splitChunks: {
          chunks: 'all',
          cacheGroups: {
            recharts: {
              test: /[\\/]node_modules[\\/](recharts|d3-|victory-vendor|decimal\.js-light)/,
              name: 'vendor-recharts',
              chunks: 'all',
              priority: 20,
            },
            radix: {
              test: /[\\/]node_modules[\\/]@radix-ui/,
              name: 'vendor-radix',
              chunks: 'all',
              priority: 15,
            },
            forceGraph: {
              test: /[\\/]node_modules[\\/](react-force-graph-2d|d3-force|d3-selection|d3-zoom|d3-drag)/,
              name: 'vendor-force-graph',
              chunks: 'all',
              priority: 20,
            },
          },
        },
      };
    }

    return config;
  },

  // 启用 SWC 压缩（比 Terser 更快）
  swcMinify: true,

  // 生产环境关闭 powered-by 头
  poweredByHeader: false,
};

module.exports = nextConfig;
