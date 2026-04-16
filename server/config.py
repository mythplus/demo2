"""
配置中心 — 加载 config.yaml、环境变量、常量定义、AI 分类 Prompt
"""

import os
import re
import json
import logging
import yaml
from datetime import datetime, timezone
from dotenv import load_dotenv

# 加载项目根目录的 .env 文件（本地开发时自动注入环境变量，生产环境由七彩石等平台注入）
_PROJECT_ROOT_FOR_ENV = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_dotenv_path = os.path.join(_PROJECT_ROOT_FOR_ENV, ".env")
if os.path.exists(_dotenv_path):
    load_dotenv(_dotenv_path, override=False)
else:
    # .env 文件不存在时输出警告（生产环境由平台注入环境变量，可忽略此警告）
    import sys
    print(
        f"[WARNING] .env 文件不存在: {_dotenv_path}，"
        "config.yaml 中的 ${{ENV_VAR}} 占位符可能被替换为空值。"
        "如果是本地开发，请复制 .env.example 为 .env 并填入实际值。",
        file=sys.stderr,
    )

# 配置日志
logger = logging.getLogger(__name__)

# ============ 环境模式 ============
_ENV_NAME = os.environ.get("MEM0_ENV", "development").lower()
IS_PRODUCTION = _ENV_NAME == "production"
IS_TESTING = _ENV_NAME == "test" or "PYTEST_CURRENT_TEST" in os.environ


# ============ 结构化日志 ============

class JsonLogFormatter(logging.Formatter):
    """JSON 格式日志 Formatter，适用于生产环境被 ELK / Loki 等日志系统采集"""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        # 附加异常信息
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
        # 附加 extra 字段（如果有）
        for key in ("request_id", "user_id", "method", "path", "status_code", "latency_ms"):
            if hasattr(record, key):
                log_entry[key] = getattr(record, key)
        return json.dumps(log_entry, ensure_ascii=False)


def setup_logging():
    """统一配置日志格式：
    - 生产环境：JSON 结构化日志，方便 ELK / Loki / CloudWatch 采集
    - 开发环境：人类可读的彩色文本格式
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # 清除已有 handler，避免重复
    root_logger.handlers.clear()

    handler = logging.StreamHandler()

    if IS_PRODUCTION:
        handler.setFormatter(JsonLogFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))

    root_logger.addHandler(handler)

    # 降低第三方库的日志级别，减少噪音
    for noisy_logger in ("httpx", "httpcore", "uvicorn.access", "neo4j", "qdrant_client"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

# ============ Qdrant 本地文件存储路径 ============
# 使用项目根目录下的 qdrant_data 文件夹，基于 server 包的父目录动态计算
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QDRANT_DATA_PATH = os.path.join(_PROJECT_ROOT, "qdrant_data")

# ============ 配置文件路径 ============
CONFIG_FILE_PATH = os.path.join(_PROJECT_ROOT, "config.yaml")

# ============ 访问日志数据库路径 ============
ACCESS_LOG_DB_PATH = os.path.join(_PROJECT_ROOT, "access_logs.db")

# ============ 速率限制数据库路径（独立于访问日志，避免高并发下互相阻塞） ============
RATE_LIMIT_DB_PATH = os.path.join(_PROJECT_ROOT, "rate_limit.db")

# ============ 记忆元数据库路径（SQLAlchemy 管理，对齐 OpenMemory 官方架构） ============
MEMORY_DB_PATH = os.path.join(_PROJECT_ROOT, "memory_meta.db")


def _safe_error_detail(e: Exception) -> str:
    """安全的异常信息：生产环境返回通用提示，开发环境返回详细错误"""
    if IS_PRODUCTION:
        return "服务器内部错误，请稍后重试"
    return str(e)


def _resolve_env_vars(value):
    """递归替换配置值中的 ${ENV_VAR} 为环境变量实际值"""
    if isinstance(value, str):
        def _replace(match):
            env_name = match.group(1)
            env_value = os.environ.get(env_name)
            if env_value is None:
                logger.warning(f"环境变量 {env_name} 未设置，将被替换为空字符串（请检查 .env 文件或环境变量配置）")
                return ""
            return env_value
        return re.sub(r'\$\{(\w+)\}', _replace, value)
    elif isinstance(value, dict):
        return {k: _resolve_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_resolve_env_vars(item) for item in value]
    return value


def load_config_from_yaml() -> dict:
    """从 config.yaml 文件实时读取配置，返回与 MEM0_CONFIG 兼容的字典格式。
    支持 ${ENV_VAR} 语法引用环境变量。"""
    try:
        with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
            yaml_config = yaml.safe_load(f)
        if not yaml_config:
            logger.warning("config.yaml 为空，使用默认配置")
            return {}

        # 递归替换环境变量
        yaml_config = _resolve_env_vars(yaml_config)

        # 构建与 MEM0_CONFIG 兼容的格式
        config = {}

        # LLM 配置
        if "llm" in yaml_config:
            config["llm"] = {
                "provider": yaml_config["llm"].get("provider", "ollama"),
                "config": yaml_config["llm"].get("config", {}),
            }

        # Embedder 配置
        if "embedder" in yaml_config:
            config["embedder"] = {
                "provider": yaml_config["embedder"].get("provider", "ollama"),
                "config": yaml_config["embedder"].get("config", {}),
            }

        # 向量数据库配置（补充 path 和 on_disk，这些不放在 yaml 中）
        if "vector_store" in yaml_config:
            vs_config = yaml_config["vector_store"].get("config", {})
            vs_config["path"] = QDRANT_DATA_PATH
            if "on_disk" not in vs_config:
                vs_config["on_disk"] = True
            config["vector_store"] = {
                "provider": yaml_config["vector_store"].get("provider", "qdrant"),
                "config": vs_config,
            }

        # 图数据库配置
        if "graph_store" in yaml_config:
            graph_store_entry = {
                "provider": yaml_config["graph_store"].get("provider", "neo4j"),
                "config": yaml_config["graph_store"].get("config", {}),
            }
            # 保留与 config 同级的额外字段（如 threshold）
            for key in yaml_config["graph_store"]:
                if key not in ("provider", "config"):
                    graph_store_entry[key] = yaml_config["graph_store"][key]
            config["graph_store"] = graph_store_entry

        # 版本号
        if "version" in yaml_config:
            config["version"] = yaml_config["version"]

        # 安全配置
        if "security" in yaml_config:
            config["security"] = yaml_config["security"]

        return config
    except FileNotFoundError:
        logger.warning(f"配置文件 {CONFIG_FILE_PATH} 不存在，使用内置默认配置")
        return {}
    except Exception as e:
        logger.error(f"读取配置文件失败: {e}，使用内置默认配置")
        return {}


# ============ Mem0 配置（从 config.yaml 加载，启动时初始化一次） ============
_yaml_config = load_config_from_yaml()
MEM0_CONFIG = _yaml_config if _yaml_config else {
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "collection_name": "mem0",
            "embedding_model_dims": 768,
            "path": QDRANT_DATA_PATH,
            "on_disk": True,
        },
    },
    "llm": {
        "provider": "ollama",
        "config": {
            "model": os.environ.get("OLLAMA_MODEL", "qwen2.5:7b"),
            "ollama_base_url": os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
            "temperature": 0.1,
        },
    },
    "embedder": {
        "provider": "ollama",
        "config": {
            "model": os.environ.get("EMBED_MODEL", "nomic-embed-text"),
            "ollama_base_url": os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
        },
    },
    "graph_store": {
        "provider": "neo4j",
        "config": {
            "url": os.environ.get("NEO4J_URL", "bolt://localhost:7687"),
            "username": os.environ.get("NEO4J_USER", "neo4j"),
            "password": os.environ.get("NEO4J_PASSWORD", ""),
        },
    },
    "version": "v1.1",
}
logger.info(f"配置加载完成，LLM: {MEM0_CONFIG.get('llm', {}).get('config', {}).get('model', 'unknown')}")

# ============ 分类和状态常量 ============
VALID_CATEGORIES = {
    "personal", "relationships", "preferences", "health", "travel",
    "work", "education", "projects", "ai_ml_technology", "technical_support",
    "finance", "shopping", "legal", "entertainment", "messages",
    "customer_support", "product_feedback", "news", "organization", "goals",
}
# ============ AI 自动分类 Prompt ============
CATEGORY_DESCRIPTIONS = {
    "personal": "个人 — 家庭、朋友、家居、爱好、生活方式",
    "relationships": "关系 — 社交网络、伴侣、同事、朋友关系",
    "preferences": "偏好 — 喜好、厌恶、习惯、喜欢的媒体",
    "health": "健康 — 体能、心理健康、饮食、睡眠",
    "travel": "旅行 — 旅行计划、通勤、喜欢的地方、行程",
    "work": "工作 — 职位、公司、项目、晋升",
    "education": "教育 — 课程、学位、证书、技能发展",
    "projects": "项目 — 待办事项、里程碑、截止日期、状态更新",
    "ai_ml_technology": "AI/ML与技术 — 基础设施、算法、工具、研究",
    "technical_support": "技术支持 — Bug报告、错误日志、修复",
    "finance": "财务 — 收入、支出、投资、账单",
    "shopping": "购物 — 购买、愿望清单、退货、配送",
    "legal": "法律 — 合同、政策、法规、隐私",
    "entertainment": "娱乐 — 电影、音乐、游戏、书籍、活动",
    "messages": "消息 — 邮件、短信、提醒、通知",
    "customer_support": "客户支持 — 工单、咨询、解决方案",
    "product_feedback": "产品反馈 — 评分、Bug报告、功能请求",
    "news": "新闻 — 文章、头条、热门话题",
    "organization": "组织 — 会议、预约、日历",
    "goals": "目标 — 目标、KPI、长期规划",
}

MEMORY_CATEGORIZATION_PROMPT = """你是一个记忆分类助手。请根据以下记忆内容，从给定的分类列表中选择最合适的分类标签。
一条记忆可以属于多个分类，但请只选择真正相关的分类，不要过度标注。

可用的分类列表：
{categories}

请严格按照以下 JSON 格式返回结果，不要输出任何其他内容：
{{"categories": ["分类1", "分类2"]}}

如果没有任何分类匹配，返回空数组：
{{"categories": []}}

记忆内容：
{memory_content}"""
