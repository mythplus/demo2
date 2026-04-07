# ============================================
# Mem0 Dashboard 前端 Dockerfile
# 多阶段构建：依赖安装 → 构建 → 运行时
# ============================================

# ---- 阶段 1：安装依赖 ----
FROM node:18-alpine AS deps

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --only=production && \
    cp -R node_modules /prod_node_modules && \
    npm ci

# ---- 阶段 2：构建 ----
FROM node:18-alpine AS builder

WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# 构建时注入 API 地址（指向 Nginx 反向代理，运行时通过 /api/mem0 转发）
ENV NEXT_TELEMETRY_DISABLED=1
ENV NEXT_PUBLIC_MEM0_API_URL=http://localhost:8080

RUN npm run build

# ---- 阶段 3：运行时镜像 ----
FROM node:18-alpine AS runner

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
