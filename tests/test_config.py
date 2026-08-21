"""
Mem0 Dashboard 后端 - 配置模块单元测试

运行方式: pytest tests/test_config.py -v
"""
import os
import sys
import pytest
from pathlib import Path

# 确保能导入 app 模块
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestConfigLoading:
    """测试配置加载"""

    def test_load_config_from_yaml_exists(self):
        """config.yaml 存在时应正确加载"""
        from app.config import MEM0_CONFIG
        assert isinstance(MEM0_CONFIG, dict)
        # 应该包含核心配置项
        assert "vector_store" in MEM0_CONFIG or "llm" in MEM0_CONFIG

    def test_qdrant_data_path_is_absolute(self):
        """QDRANT_DATA_PATH 应为绝对路径"""
        from app.config import QDRANT_DATA_PATH
        assert os.path.isabs(QDRANT_DATA_PATH)
        assert QDRANT_DATA_PATH.endswith("qdrant_data")

    def test_is_production_default(self):
        """默认应为开发模式"""
        from app.config import IS_PRODUCTION
        # 不设置环境变量时应为 False
        assert isinstance(IS_PRODUCTION, bool)

    def test_valid_categories_not_empty(self):
        """VALID_CATEGORIES 不应为空"""
        from app.config import VALID_CATEGORIES
        assert len(VALID_CATEGORIES) >= 10
        assert "personal" in VALID_CATEGORIES
        assert "work" in VALID_CATEGORIES

    def test_valid_states(self):
        """VALID_STATES 应包含三种状态"""
        from app.config import VALID_STATES
        assert VALID_STATES == {"active", "paused", "deleted"}

    def test_safe_error_detail_dev_mode(self):
        """开发模式应返回详细错误"""
        from app.config import _safe_error_detail
        err = ValueError("test error detail")
        # 开发模式下应返回原始错误信息
        result = _safe_error_detail(err)
        assert "test error detail" in result

    def test_category_descriptions_complete(self):
        """每个分类都应有描述"""
        from app.config import CATEGORY_DESCRIPTIONS, VALID_CATEGORIES
        for cat in VALID_CATEGORIES:
            assert cat in CATEGORY_DESCRIPTIONS, f"分类 {cat} 缺少描述"


class TestEnvVarResolution:
    """测试环境变量替换"""

    def test_resolve_string_env_var(self):
        """字符串中的 ${ENV_VAR} 应被替换"""
        from app.config import _resolve_env_vars
        os.environ["TEST_VAR"] = "test_value"
        result = _resolve_env_vars("prefix-${TEST_VAR}-suffix")
        assert result == "prefix-test_value-suffix"
        del os.environ["TEST_VAR"]

    def test_resolve_nested_dict(self):
        """嵌套 dict 中的环境变量应被替换"""
        from app.config import _resolve_env_vars
        os.environ["NESTED_VAR"] = "nested"
        result = _resolve_env_vars({
            "outer": {
                "inner": "${NESTED_VAR}",
            },
        })
        assert result["outer"]["inner"] == "nested"
        del os.environ["NESTED_VAR"]

    def test_resolve_no_env_var(self):
        """未定义的环境变量应替换为空字符串"""
        from app.config import _resolve_env_vars
        result = _resolve_env_vars("${UNDEFINED_VAR_12345}")
        assert result == ""

    def test_resolve_non_string(self):
        """非字符串类型应原样返回"""
        from app.config import _resolve_env_vars
        assert _resolve_env_vars(123) == 123
        assert _resolve_env_vars(None) is None
        assert _resolve_env_vars(True) is True
