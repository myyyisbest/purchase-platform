"""
pytest 公共 fixtures

运行测试前需安装依赖：
    cd backend && pip install -r requirements-dev.txt

运行测试：
    cd backend && python -m pytest tests/ -v
"""
import os
import sys

# 注入测试用环境变量（必须在导入 app 模块之前设置）
os.environ.setdefault("JWT_SECRET", "test_secret_for_unit_tests_at_least_32_chars_long")
os.environ.setdefault("DEFAULT_ADMIN_PASSWORD", "test_admin_pwd_123")
os.environ.setdefault("DEFAULT_USER_PASSWORD", "test_user_pwd_123")

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def app():
    """创建 FastAPI 应用实例（不启动 lifespan，避免连接数据库）"""
    from app.main import app as _app
    return _app


@pytest.fixture(scope="session")
def client(app):
    """FastAPI 测试客户端"""
    return TestClient(app)
