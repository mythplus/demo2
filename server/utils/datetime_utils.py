"""日期/时间解析工具 — B2 P2-6：统一 memory_service 与 meta_service 中重复的解析函数。

设计要点：
- 所有输出均带 UTC 时区（tz-aware），避免与 PostgreSQL / Qdrant 的时区语义混淆。
- 接受 "YYYY-MM-DD" 纯日期：视为该日 00:00:00（start of day）或 23:59:59（end of day）。
- 接受 ISO 8601 形式（含可选的 "Z" 后缀，这里统一归一化为 "+00:00"）。
- 解析失败交给调用方感知（raise ValueError），调用方可按业务决定是否降级。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional


def parse_iso_datetime(value: Optional[str], *, end_of_day: bool = False) -> Optional[datetime]:
    """把日期/时间字符串解析为带 UTC 时区的 ``datetime``。

    Args:
        value: 输入字符串。``None`` 或空白字符串一律返回 ``None``。
        end_of_day: 当输入是 "YYYY-MM-DD" 纯日期时，是否按 23:59:59 截取（用于"截止日期"语义）。

    Returns:
        带 UTC 时区的 ``datetime``；``value`` 为空时返回 ``None``。

    Raises:
        ValueError: 无法解析的日期字符串，由 ``datetime.fromisoformat`` 抛出。
    """
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None

    # 形如 "2026-04-21"，兼容纯日期输入
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        suffix = "T23:59:59+00:00" if end_of_day else "T00:00:00+00:00"
        return datetime.fromisoformat(text + suffix)

    # ISO 8601；把 Python 3.10 之前 fromisoformat 不支持的 "Z" 后缀统一转成 "+00:00"
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed
