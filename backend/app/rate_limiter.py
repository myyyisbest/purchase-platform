"""
API 限流器（进程内滑动窗口，线程安全）

设计：
- 按 client_ip + user_id 维度限流（未登录时只按 IP）
- 读接口（GET）和写接口（POST/PUT/PATCH/DELETE）使用不同阈值
- 超限返回 429 + Retry-After 头

注：单实例方案。多实例部署需替换为 Redis 共享存储。
"""
import time
import threading
import logging
from collections import deque
from typing import Optional

from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# 写操作方法集
_WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class SlidingWindowLimiter:
    """滑动窗口限流器：在 window_seconds 内最多允许 max_requests 次"""

    def __init__(self, max_requests: int, window_seconds: int):
        self._max = max_requests
        self._window = window_seconds
        # key -> deque[timestamps]
        self._buckets: dict[str, deque] = {}
        self._guard = threading.Lock()

    def _allow(self, key: str) -> tuple[bool, int]:
        """返回 (是否允许, 需等待秒数)"""
        now = time.time()
        cutoff = now - self._window
        with self._guard:
            dq = self._buckets.get(key)
            if dq is None:
                dq = deque()
                self._buckets[key] = dq
            # 清理过期时间戳
            while dq and dq[0] < cutoff:
                dq.popleft()
            if len(dq) >= self._max:
                # 计算最早请求还需等多久过期
                retry_after = int(dq[0] + self._window - now) + 1
                return False, max(1, retry_after)
            dq.append(now)
            return True, 0

    def check(self, key: str) -> None:
        """超限抛 HTTPException(429)；正常直接返回"""
        allowed, retry_after = self._allow(key)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"请求过于频繁，请 {retry_after} 秒后重试",
                headers={"Retry-After": str(retry_after)},
            )


def _extract_client_ip(request: Request) -> str:
    """提取真实客户端 IP（优先取反向代理转发的 X-Forwarded-For）"""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _extract_user_id(request: Request) -> Optional[str]:
    """从 request.state 提取用户ID（由 get_current_user 解析后注入；未登录返回 None）"""
    user = getattr(request.state, "user", None)
    if user is not None:
        return str(getattr(user, "id", ""))
    return None


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    API 限流中间件：
    - GET：60 次/分钟（高频读）
    - 写操作：20 次/分钟（低频写，保护数据库）
    - /api/auth/login 和 /health 不限流（登录已有专用 LoginRateLimiter）
    """

    _EXEMPT_PATHS = frozenset({"/api/auth/login", "/health", "/"})

    def __init__(self, app, read_limit: int = 60, write_limit: int = 20, window: int = 60):
        super().__init__(app)
        self._read_limiter = SlidingWindowLimiter(read_limit, window)
        self._write_limiter = SlidingWindowLimiter(write_limit, window)

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # 放行白名单：登录、健康检查、文档
        if path in self._EXEMPT_PATHS or path.startswith("/docs") or path.startswith("/openapi"):
            return await call_next(request)

        # 构造限流 key：IP + user_id（未登录只按 IP）
        ip = _extract_client_ip(request)
        user_id = _extract_user_id(request)
        key = f"{ip}:{user_id}" if user_id else ip

        try:
            if request.method in _WRITE_METHODS:
                self._write_limiter.check(key)
            else:
                self._read_limiter.check(key)
        except HTTPException as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
                headers=exc.headers or {},
            )

        return await call_next(request)
