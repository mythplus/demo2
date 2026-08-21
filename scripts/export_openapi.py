#!/usr/bin/env python3
"""
Mem0 Dashboard - OpenAPI Schema 导出脚本

从 FastAPI 应用中导出 OpenAPI schema，供前端 TypeScript 类型生成使用。

使用方式:
  python scripts/export_openapi.py

输出:
  mem0-dashboard/src/lib/api/openapi.json
"""
import sys
import json
from pathlib import Path

# 确保项目根目录在 sys.path 中
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from app.main import app

output_path = project_root / "mem0-dashboard" / "src" / "lib" / "api" / "openapi.json"

# 导出 OpenAPI schema
schema = app.openapi()

# 写入文件
output_path.parent.mkdir(parents=True, exist_ok=True)
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(schema, f, ensure_ascii=False, indent=2)

print(f"OpenAPI schema 已导出到: {output_path}")
print(f"共 {len(schema.get('paths', {}))} 个端点")
