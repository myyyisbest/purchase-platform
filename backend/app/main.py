"""
FastAPI主应用
采购分析平台后端服务
"""
import os
import time
import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()  # 加载 .env 环境变量

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from .database import engine, Base
from .rate_limiter import RateLimitMiddleware
from .middleware.audit_log import AuditLogMiddleware

# 配置根日志：控制台输出，INFO 级别（生产可由 uvicorn/gunicorn 接管）
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("purchase_platform")


def _startup_init() -> None:
    """启动初始化：建表 + 确保 admin 账户存在"""
    from . import models  # noqa: F401 触发 ORM 注册
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        logger.warning("建表失败（可能已存在）: %s", e)

    from .database import SessionLocal
    from .services.user_service import UserService
    db = SessionLocal()
    try:
        UserService(db).ensure_admin_exists()
    except Exception as e:
        logger.warning("初始化 admin 账户失败: %s", e)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化，停止时无需额外清理"""
    logger.info("采购分析平台启动中...")
    _startup_init()
    logger.info("采购分析平台启动完成")
    yield
    logger.info("采购分析平台停止")


# 创建FastAPI应用
app = FastAPI(
    title="采购分析平台API",
    description="采购分析平台后端服务",
    version="1.0.0",
    lifespan=lifespan,
)

# 配置CORS：来源由环境变量 CORS_ALLOW_ORIGINS 控制（逗号分隔），默认仅放行本地开发地址
_cors_raw = os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:5173,http://localhost:3000")
_cors_origins = [o.strip() for o in _cors_raw.split(",") if o.strip()]
logger.info("CORS 允许来源: %s", _cors_origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 请求日志中间件：记录方法/路径/状态码/耗时，便于审计与排障
class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        cost_ms = int((time.time() - start) * 1000)
        logger.info(
            "%s %s -> %d (%dms)",
            request.method, request.url.path, response.status_code, cost_ms,
        )
        return response


app.add_middleware(RequestLoggingMiddleware)

# 审计日志中间件：写操作（POST/PUT/DELETE）异步落库
# Starlette 中间件为 LIFO 栈：后注册=外层=先执行
# 执行顺序：限流 → 审计 → 日志 → 路由（限流拦截的请求不进入审计）
app.add_middleware(AuditLogMiddleware)
app.add_middleware(RateLimitMiddleware)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局兜底异常处理：防止堆栈信息泄漏到响应体，仅记录服务端日志"""
    logger.exception("未处理异常: %s %s -> %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误，请联系管理员"},
    )


# 健康检查接口（不依赖数据库）
@app.get("/health")
def health_check():
    return {"status": "ok", "message": "采购分析平台API运行正常"}

# 根路径
@app.get("/")
def root():
    return {
        "message": "采购分析平台API",
        "version": "1.0.0",
        "docs": "/docs",
        "openapi": "/openapi.json"
    }


# 导入API路由
from .api import import_api      # noqa: E402
from .api import yoy_api         # noqa: E402
from .api import dashboard_api   # noqa: E402
from .api import org_api         # noqa: E402
from .api import exchange_rate_api  # noqa: E402
from .api import ai_api          # noqa: E402
from .api import price_trend_api # noqa: E402
from .api import material_major_category_api  # noqa: E402
from .api import auth_api        # noqa: E402
from .api import user_api        # noqa: E402
from .api import hana_sync_api   # noqa: E402
from .api import purchase_record_api  # noqa: E402
from .api import anomaly_alert_api  # noqa: E402
from .api import supplier_api  # noqa: E402

app.include_router(auth_api.router, prefix="/api/auth", tags=["认证"])
app.include_router(user_api.router, prefix="/api/users", tags=["用户管理"])
app.include_router(import_api.router, prefix="/api/import", tags=["数据导入"])
app.include_router(yoy_api.router, prefix="/api/yoy", tags=["采购同期对比分析"])
app.include_router(dashboard_api.router, prefix="/api/dashboard", tags=["采购分析面板"])
app.include_router(org_api.router, prefix="/api/org", tags=["组织架构管理"])
app.include_router(exchange_rate_api.router, prefix="/api/exchange-rates", tags=["汇率管理"])
app.include_router(ai_api.router, prefix="/api/ai", tags=["AI助手"])
app.include_router(price_trend_api.router, prefix="/api/price-trend", tags=["物料单价趋势"])
app.include_router(material_major_category_api.router, prefix="/api/material-major-categories", tags=["物料大类维护"])
app.include_router(hana_sync_api.router, prefix="/api/hana-sync", tags=["HANA数据同步"])
app.include_router(purchase_record_api.router, prefix="/api/purchase-records", tags=["采购记录明细"])
app.include_router(anomaly_alert_api.router, prefix="/api/anomaly-alerts", tags=["异常预警"])
app.include_router(supplier_api.router, prefix="/api/suppliers", tags=["供应商管理"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
