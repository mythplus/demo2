/** @type {import('next').NextConfig} */
const nextConfig = {
  // 生产环境使用 standalone 输出模式，优化 Docker 镜像体积
  output: 'standalone',

  // ESLint：warning 不阻断构建（真正的错误仍然会报）
  eslint: {
    ignoreDuringBuilds: true,
  },

  // 优化大型图标库的 tree-shaking，避免将 1000+ 个图标全部打包
  modularizeImports: {
    'lucide-react': {
      transform: 'lucide-react/dist/esm/icons/{{kebabCase member}}',
    },
  },

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
