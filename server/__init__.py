"""
Mem0 Dashboard 后端 API 服务 — server 包

向后兼容层：确保 `import server` / `from server import app` 仍然有效。
实际代码分布在 server/ 包的各子模块中。
"""

# ============ 从子模块重新导出核心对象 ============
# 这些导出确保 uvicorn server:app 和测试中的 from server import app 仍然有效

from server.app import app  # noqa: F401 — FastAPI 应用实例

# ============ 向后兼容：重新导出测试文件引用的符号 ============
from server.config import (  # noqa: F401
    MEM0_CONFIG, IS_PRODUCTION, IS_TESTING, QDRANT_DATA_PATH, ACCESS_LOG_DB_PATH,
    CONFIG_FILE_PATH, VALID_CATEGORIES, VALID_STATES,
    CATEGORY_DESCRIPTIONS, MEMORY_CATEGORIZATION_PROMPT,
    _safe_error_detail, load_config_from_yaml, setup_logging,
)
from server.services.memory_service import (  # noqa: F401
    get_memory, extract_memory_fields, format_record, format_mem0_result,
    apply_filters, auto_categorize_memory as _auto_categorize_memory,
    get_all_memories_raw as _get_all_memories_raw,
    get_real_states as _get_real_states,
    invalidate_stats_cache as _invalidate_stats_cache,
)
from server.services.log_service import (  # noqa: F401
    init_access_log_db as _init_access_log_db,
    start_log_writer as _start_log_writer,
    stop_log_writer as _stop_log_writer,
    _get_db_conn,
    _enqueue_log,
    log_access as _log_access,
    get_access_logs as _get_access_logs,
    save_change_log as _save_change_log,
    get_change_logs as _get_change_logs,
    save_category_snapshot as _save_category_snapshot,
    classify_request as _classify_request,
    extract_user_from_request as _extract_user_from_request,
    summarize_payload as _summarize_payload,
    log_request as _log_request,
    get_request_logs as _get_request_logs,
)
from server.services.graph_service import (  # noqa: F401
    get_neo4j_driver as _get_neo4j_driver,
    close_neo4j_driver as _close_neo4j_driver,
    neo4j_query as _neo4j_query,
)
from server.middleware.auth import ApiKeyAuthMiddleware  # noqa: F401
from server.middleware.rate_limit import RateLimitMiddleware  # noqa: F401
from server.middleware.request_log import RequestLogMiddleware  # noqa: F401
from server.models.schemas import (  # noqa: F401
    MemoryMessage, AddMemoryRequest, SearchMemoryRequest, UpdateMemoryRequest,
    BatchImportItem, BatchImportRequest, BatchImportResponse, BatchImportResultItem,
    BatchDeleteRequest, BatchDeleteResponse, GraphSearchRequest,
)

# 向后兼容的配置变量
_configured_api_key = MEM0_CONFIG.get("security", {}).get("api_key", "")
_rate_limit_rpm = int(MEM0_CONFIG.get("security", {}).get("rate_limit", 60))
