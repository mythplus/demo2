"""
Mem0 Dashboard 后端 - 日志路由（访问日志 & 请求日志）
"""
import logging
import sqlite3
from typing import Optional, Dict
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Query

from app.config import _safe_error_detail
from app.database import (
    get_access_logs, get_request_logs, _get_db_conn,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["logs"])


# ============ 访问日志 ============

@router.get("/v1/access-logs/")
async def get_access_logs_api(
    memory_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """获取访问日志"""
    try:
        logs, total = get_access_logs(memory_id=memory_id, limit=limit, offset=offset)
        return {"logs": logs, "total": total}
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
        logs, total = get_access_logs(memory_id=memory_id, limit=limit)
        return {"logs": logs}
    except Exception as e:
        logger.error(f"获取记忆访问日志失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


# ============ 请求日志 ============

@router.get("/v1/request-logs/")
async def get_request_logs_api(
    request_type: Optional[str] = Query(None),
    since: Optional[str] = Query(None),
    until: Optional[str] = Query(None),
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
    since: Optional[str] = Query(None),
    until: Optional[str] = Query(None),
):
    """获取请求日志统计"""
    try:
        conn = _get_db_conn()
        conn.row_factory = sqlite3.Row

        where = "WHERE 1=1"
        params: list = []
        if since:
            where += " AND timestamp >= ?"
            params.append(since)
        if until:
            where += " AND timestamp <= ?"
            params.append(until)

        type_rows = conn.execute(
            f"SELECT request_type, COUNT(*) as count FROM request_logs {where} GROUP BY request_type ORDER BY count DESC",
            params,
        ).fetchall()
        type_distribution = {row["request_type"]: row["count"] for row in type_rows}

        now = datetime.now()
        if since:
            try:
                since_dt = datetime.fromisoformat(since.replace("Z", "+00:00")).replace(tzinfo=None)
            except (ValueError, TypeError):
                since_dt = now - timedelta(days=14)
            hours_diff = (now - since_dt).total_seconds() / 3600
        else:
            hours_diff = 999

        if hours_diff <= 24:
            granularity = "hour"
            hourly_rows = conn.execute(
                f"""SELECT
                      STRFTIME('%Y-%m-%d %H:00', timestamp) as slot,
                      request_type, COUNT(*) as count
                    FROM request_logs {where}
                    GROUP BY slot, request_type
                    ORDER BY slot""",
                params,
            ).fetchall()

            slot_map: Dict[str, Dict[str, int]] = {}
            all_types = set()
            for row in hourly_rows:
                s = row["slot"]
                t = row["request_type"]
                all_types.add(t)
                if s not in slot_map:
                    slot_map[s] = {}
                slot_map[s][t] = row["count"]

            daily_trend = []
            slot_start = since_dt.replace(hour=0, minute=0, second=0, microsecond=0)
            slot_end = slot_start.replace(hour=23, minute=0)
            while slot_start <= slot_end:
                slot_key = slot_start.strftime("%Y-%m-%d %H:%M")
                entry: dict = {"date": slot_key}
                type_counts = slot_map.get(slot_key.replace(":00", ":00"), {})
                for t in all_types:
                    entry[t] = type_counts.get(t, 0)
                daily_trend.append(entry)
                slot_start += timedelta(hours=1)
        else:
            granularity = "day"
            daily_type_rows = conn.execute(
                f"""SELECT DATE(timestamp) as date, request_type, COUNT(*) as count
                   FROM request_logs {where}
                   GROUP BY DATE(timestamp), request_type
                   ORDER BY date""",
                params,
            ).fetchall()

            daily_type_map: Dict[str, Dict[str, int]] = {}
            all_types = set()
            for row in daily_type_rows:
                d = row["date"]
                t = row["request_type"]
                all_types.add(t)
                if d not in daily_type_map:
                    daily_type_map[d] = {}
                daily_type_map[d][t] = row["count"]

            num_days = min(int(hours_diff / 24) + 1, 30)
            daily_trend = []
            for i in range(num_days - 1, -1, -1):
                d = (now - timedelta(days=i)).strftime("%Y-%m-%d")
                entry: dict = {"date": d}
                type_counts = daily_type_map.get(d, {})
                for t in all_types:
                    entry[t] = type_counts.get(t, 0)
                daily_trend.append(entry)

        total = conn.execute(f"SELECT COUNT(*) FROM request_logs {where}", params).fetchone()[0]

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
