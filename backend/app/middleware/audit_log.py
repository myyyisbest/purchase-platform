"""
操作审计日志中间件

设计：
- 仅记录写操作（POST/PUT/PATCH/DELETE），读操作不记录（避免日志膨胀）
- best-effort 解析 JWT 获取操作者身份（解析失败记为匿名）
- 请求完成后异步落库（BackgroundTasks），不阻塞主请求响应
- body_summary 暂不采集（ASGI body stream 处理复杂，收益有限）
"""
import logging
from typing import Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.background import BackgroundTask

from ..auth import decode_access_token
from ..database import SessionLocal
from ..models import AuditLog

logger = logging.getLogger(__name__)

_WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_BODY_SUMMARY_MAX = 500


def _resolve_user(request: Request) -> tuple[Optional[int], Optional[str]]:
    """best-effort 解析 JWT 获取 user_id 和 username；失败返回 (None, None)"""
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return None, None
    token = auth_header[7:]
    try:
        payload = decode_access_token(token)
        user_id = int(payload.get("sub", 0)) or None
        return user_id, payload.get("username")
    except Exception:
        # token 无效或过期，仍记录操作（标记为匿名）
        return None, None


def _extract_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _write_audit_log(
    user_id: Optional[int],
    username: Optional[str],
    method: str,
    path: str,
    status_code: int,
    client_ip: str,
    cost_ms: int,
) -> None:
    """后台任务：写入审计日志（独立 Session，失败仅记日志不影响主流程）"""
    db = SessionLocal()
    try:
        log = AuditLog(
            user_id=user_id,
            username=username,
            method=method,
            path=path,
            status_code=status_code,
            client_ip=client_ip,
            cost_ms=cost_ms,
        )
        db.add(log)
        db.commit()
    except Exception as e:
        logger.warning("审计日志写入失败: %s", e)
    finally:
        db.close()


class AuditLogMiddleware(BaseHTTPMiddleware):
    """写操作审计日志中间件：POST/PUT/PATCH/DELETE 请求完成后异步落库"""

    async def dispatch(self, request: Request, call_next):
        # 放行读操作和非业务路径
        if request.method not in _WRITE_METHODS:
            return await call_next(request)

        import time as _time
        start = _time.time()
        response = await call_next(request)
        cost_ms = int((_time.time() - start) * 1000)

        # 注册后台任务：响应返回后异步写审计日志
        user_id, username = _resolve_user(request)
        client_ip = _extract_client_ip(request)
        response.background = BackgroundTask(
            _write_audit_log,
            user_id=user_id,
            username=username,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            client_ip=client_ip,
            cost_ms=cost_ms,
        )
        return response
