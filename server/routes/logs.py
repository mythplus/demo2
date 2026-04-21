"""
访问日志 + 请求日志路由
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta, timezone

import psycopg2.extras
from fastapi import APIRouter, HTTPException, Query

from server.config import _safe_error_detail
from server.services.log_service import get_access_logs, get_request_logs, _get_db_conn, _release_conn
from server.utils.datetime_utils import parse_iso_datetime

logger = logging.getLogger(__name__)

# 旧版英文 request_type → 新版中文类型名映射（兼容历史数据）
_LEGACY_TYPE_MAP: Dict[str, str] = {
    "POST": "添加",
    "GET": "获取全部",
    "PUT": "更新",
    "DELETE": "删除",
}


def _normalize_request_type(raw_type: str) -> str:
    """将旧版英文类型名归并为中文类型名，已是中文的保持不变"""
    return _LEGACY_TYPE_MAP.get(raw_type, raw_type)

router = APIRouter(tags=["日志"])


@router.get("/v1/access-logs/")
async def get_access_logs_api(
    memory_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """获取访问日志（可按记忆 ID 筛选）"""
    try:
        logs = get_access_logs(memory_id=memory_id, limit=limit, offset=offset)
        return {"logs": logs, "total": len(logs)}
    except Exception as e:
        logger.error(f"获取访问日志失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


@router.get("/v1/memories/{memory_id}/access-logs/")
async def get_memory_access_logs(
    memory_id: str,
    limit: int = Query(10, ge=1, le=100),
):
    """获取单条记忆的访问日志"""
    try:
        logs = get_access_logs(memory_id=memory_id, limit=limit)
        return {"logs": logs}
    except Exception as e:
        logger.error(f"获取记忆访问日志失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


@router.get("/v1/request-logs/")
async def get_request_logs_api(
    request_type: Optional[str] = Query(None, description="请求类型筛选: 添加/搜索/删除/更新"),
    since: Optional[str] = Query(None, description="起始时间 ISO 格式，如 2026-03-27T10:00:00"),
    until: Optional[str] = Query(None, description="结束时间 ISO 格式，如 2026-04-02T23:59:59"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """获取请求日志"""
    try:
        logs, total = get_request_logs(request_type=request_type, since=since, until=until, limit=limit, offset=offset)
        return {"logs": logs, "total": total}
    except Exception as e:
        logger.error(f"获取请求日志失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


@router.get("/v1/request-logs/stats/")
async def get_request_logs_stats(
    since: Optional[str] = Query(None, description="起始时间 ISO 格式"),
    until: Optional[str] = Query(None, description="结束时间 ISO 格式"),
):
    """获取请求日志统计（按类型分组计数 + 按类型趋势数据，自动根据时间范围切换粒度）"""
    conn = None
    try:
        conn = _get_db_conn()

        where = "WHERE 1=1"
        params: list = []
        if since:
            where += " AND timestamp >= %s"
            params.append(since)
        if until:
            where += " AND timestamp <= %s"
            params.append(until)

        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # 按类型分组（归并旧版英文类型名）
            cur.execute(
                f"SELECT request_type, COUNT(*) as count FROM request_logs {where} GROUP BY request_type ORDER BY count DESC",
                params,
            )
            type_rows = cur.fetchall()

        type_distribution: Dict[str, int] = {}
        for row in type_rows:
            normalized = _normalize_request_type(row["request_type"])
            type_distribution[normalized] = type_distribution.get(normalized, 0) + row["count"]

        # 判断粒度
        now = datetime.now(timezone.utc)
        if since:
            # B3 P2-7: 用公共工具解析，避免 AttributeError
            try:
                since_dt = parse_iso_datetime(since)
                if since_dt:
                    since_dt = since_dt.replace(tzinfo=None)
                else:
                    since_dt = now - timedelta(days=14)
            except (ValueError, TypeError):
                since_dt = now - timedelta(days=14)
            hours_diff = (now - since_dt).total_seconds() / 3600
        else:
            hours_diff = 999

        if hours_diff <= 24:
            granularity = "hour"
            # PostgreSQL：按 1 小时分桶
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    f"""SELECT
                          TO_CHAR(DATE_TRUNC('hour', timestamp::timestamptz), 'YYYY-MM-DD HH24:00') AS slot,
                          request_type, COUNT(*) AS count
                        FROM request_logs {where}
                        GROUP BY slot, request_type
                        ORDER BY slot""",
                    params,
                )
                hourly_rows = cur.fetchall()

            slot_map: Dict[str, Dict[str, int]] = {}
            all_types = set()
            for row in hourly_rows:
                s = row["slot"]
                t = _normalize_request_type(row["request_type"])
                all_types.add(t)
                if s not in slot_map:
                    slot_map[s] = {}
                slot_map[s][t] = slot_map[s].get(t, 0) + row["count"]

            # 补全 24 小时时间槽
            daily_trend = []
            slot_start = since_dt.replace(hour=0, minute=0, second=0, microsecond=0)
            slot_end = slot_start.replace(hour=23, minute=0)
            while slot_start <= slot_end:
                slot_key = slot_start.strftime("%Y-%m-%d %H:00")
                entry: Dict[str, Any] = {"date": slot_key}
                type_counts = slot_map.get(slot_key, {})
                for t in all_types:
                    entry[t] = type_counts.get(t, 0)
                daily_trend.append(entry)
                slot_start += timedelta(hours=1)

        else:
            granularity = "day"
            # PostgreSQL：按天分组
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    f"""SELECT TO_CHAR(timestamp::timestamptz, 'YYYY-MM-DD') AS date,
                               request_type, COUNT(*) AS count
                           FROM request_logs {where}
                           GROUP BY date, request_type
                           ORDER BY date""",
                    params,
                )
                daily_type_rows = cur.fetchall()

            daily_type_map: Dict[str, Dict[str, int]] = {}
            all_types = set()
            for row in daily_type_rows:
                d = row["date"]
                t = _normalize_request_type(row["request_type"])
                all_types.add(t)
                if d not in daily_type_map:
                    daily_type_map[d] = {}
                daily_type_map[d][t] = daily_type_map[d].get(t, 0) + row["count"]

            num_days = min(int(hours_diff / 24) + 1, 30)
            daily_trend = []
            for i in range(num_days - 1, -1, -1):
                d = (now - timedelta(days=i)).strftime("%Y-%m-%d")
                entry: Dict[str, Any] = {"date": d}
                type_counts = daily_type_map.get(d, {})
                for t in all_types:
                    entry[t] = type_counts.get(t, 0)
                daily_trend.append(entry)

        # 总请求数
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM request_logs {where}", params)
            total = cur.fetchone()[0]

        return {
            "total": total,
            "type_distribution": type_distribution,
            "daily_trend": daily_trend,
            "types": sorted(all_types),
            "granularity": granularity,
        }
    except Exception as e:
        logger.error(f"获取请求日志统计失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))
    finally:
        if conn is not None:
            _release_conn(conn)
