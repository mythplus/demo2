#!/bin/bash
# ============================================
# Mem0 Dashboard - 前端 TypeScript 类型生成脚本
#
# 从后端 OpenAPI schema 自动生成前端 TypeScript 类型，
# 确保 Pydantic 模型与 TypeScript 类型保持同步。
#
# 使用方式:
#   ./scripts/generate-types.sh
#
# 依赖:
#   - npx (随 Node.js 安装)
#   - openapi-typescript (通过 npx 自动安装)
# ============================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
FRONTEND_DIR="$PROJECT_ROOT/mem0-dashboard"
OPENAPI_JSON="$FRONTEND_DIR/src/lib/api/openapi.json"
TYPES_OUTPUT="$FRONTEND_DIR/src/lib/api/generated-types.ts"

echo "🔍 正在生成 OpenAPI schema..."
cd "$PROJECT_ROOT"
python scripts/export_openapi.py

echo "📦 正在从 OpenAPI 生成 TypeScript 类型..."
cd "$FRONTEND_DIR"
npx openapi-typescript "$OPENAPI_JSON" -o "$TYPES_OUTPUT"

echo "✅ TypeScript 类型已生成到: $TYPES_OUTPUT"
echo ""
echo "使用方式:"
echo "  import type { paths, components } from '@/lib/api/generated-types';"
