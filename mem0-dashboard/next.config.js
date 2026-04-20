/** @type {import('next').NextConfig} */
const nextConfig = {
  // 生产环境使用 standalone 输出模式，优化 Docker 镜像体积
  output: 'standalone',

  // ESLint：warning 不阻断构建（真正的错误仍然会报；CI 中用 `npm run lint` 单独守门）
  eslint: {
    ignoreDuringBuilds: true,
  },

  // 优化大型图标库的 tree-shaking，避免将 1000+ 个图标全部打包
  modularizeImports: {
    'lucide-react': {
      transform: 'lucide-react/dist/esm/icons/{{kebabCase member}}',
    },
  },

  // 注：此前有一条 `/api/mem0/:path*` rewrites，但实际代码走 `resolveApiBase()` 直接 fetch，
  // 并未使用该 rewrite；且 rewrites 的 destination 会在构建时静态展开，
  // 容易把开发地址烘焙进生产 bundle，因此移除以减少歧义。

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
