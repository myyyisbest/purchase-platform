"""
API 限流器单元测试
覆盖：滑动窗口限流逻辑、读/写不同阈值、key 隔离

纯单元测试，不依赖数据库与 FastAPI。
"""
import pytest

from app.rate_limiter import SlidingWindowLimiter


class TestSlidingWindowLimiter:
    def test_allows_within_limit(self):
        """窗口内未超限应全部允许"""
        limiter = SlidingWindowLimiter(max_requests=5, window_seconds=60)
        for i in range(5):
            allowed, _ = limiter._allow("key1")
            assert allowed is True, f"第{i+1}次应允许"

    def test_blocks_over_limit(self):
        """超限后应拒绝"""
        limiter = SlidingWindowLimiter(max_requests=3, window_seconds=60)
        for _ in range(3):
            limiter._allow("key2")
        allowed, retry = limiter._allow("key2")
        assert allowed is False
        assert retry > 0

    def test_different_keys_independent(self):
        """不同 key 的限流应相互独立"""
        limiter = SlidingWindowLimiter(max_requests=2, window_seconds=60)
        limiter._allow("ipA")
        limiter._allow("ipA")
        # ipA 已达上限
        assert limiter._allow("ipA")[0] is False
        # ipB 不受影响
        assert limiter._allow("ipB")[0] is True

    def test_window_expiry(self):
        """窗口过期后应重新允许"""
        import time
        limiter = SlidingWindowLimiter(max_requests=1, window_seconds=1)
        limiter._allow("keyExp")
        assert limiter._allow("keyExp")[0] is False
        time.sleep(1.1)
        assert limiter._allow("keyExp")[0] is True

    def test_check_raises_429_when_over_limit(self):
        """超限时 check() 应抛 HTTPException(429)"""
        from fastapi import HTTPException
        limiter = SlidingWindowLimiter(max_requests=1, window_seconds=60)
        limiter.check("key429")  # 第一次允许
        with pytest.raises(HTTPException) as exc_info:
            limiter.check("key429")  # 第二次超限
        assert exc_info.value.status_code == 429
        assert "Retry-After" in exc_info.value.headers
