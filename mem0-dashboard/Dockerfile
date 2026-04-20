# ============================================
# Mem0 Dashboard 前端 Dockerfile
# 多阶段构建：依赖安装 → 构建 → 运行时
# ============================================

# ---- 阶段 1：安装依赖 ----
# 锁定到 minor 版本，避免不同 CI/机器拉到不一致的 npm 造成 lockfile 报错
FROM node:18.20.4-alpine AS deps

WORKDIR /app

COPY package.json package-lock.json ./
# 直接安装全量依赖（含 devDependencies），供 stage 2 构建使用
# Next.js 构建需要 typescript / eslint 等 dev 依赖，无法简单用 --omit=dev
RUN npm ci

# ---- 阶段 2：构建 ----
FROM node:18.20.4-alpine AS builder

WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
# 注意：配合 .dockerignore 可避免把 .env.local / .next / node_modules 等带进构建上下文
COPY . .

# 禁用 Next.js 遥测数据上报
ENV NEXT_TELEMETRY_DISABLED=1
# 生产镜像不预埋后端地址：留空后前端 resolveApiBase() 会走 window.location.origin 同源反向代理
# （由 Nginx 负责 /v1 转发和 API Key 注入，避免把 localhost 或密钥烘焙进前端 JS bundle）
ENV NEXT_PUBLIC_MEM0_API_URL=

RUN npm run build

# ---- 阶段 3：运行时镜像 ----
FROM node:18.20.4-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1

# 创建非 root 用户
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# 复制构建产物（Next.js standalone 模式需要以下文件）
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:3000/ || exit 1

CMD ["node", "server.js"]
