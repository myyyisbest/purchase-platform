"""
认证模块单元测试
覆盖：密码哈希、密码强度校验、JWT 生成/解析、登录防爆破限流器

纯单元测试，不依赖数据库。
"""
import time
import pytest

from app.auth import (
    hash_password, verify_password, validate_password,
    create_access_token, decode_access_token,
    LoginRateLimiter,
)


# ============ 密码哈希 ============

class TestPasswordHashing:
    def test_hash_and_verify(self):
        """正确密码应校验通过"""
        hashed = hash_password("testPass123")
        assert verify_password("testPass123", hashed) is True

    def test_wrong_password_fails(self):
        """错误密码应校验失败"""
        hashed = hash_password("correctPwd1")
        assert verify_password("wrongPwd1", hashed) is False

    def test_hash_is_unique(self):
        """同一密码两次哈希结果应不同（bcrypt 含随机盐）"""
        h1 = hash_password("samePwd123")
        h2 = hash_password("samePwd123")
        assert h1 != h2


# ============ 密码强度校验 ============

class TestPasswordValidation:
    @pytest.mark.parametrize("valid_pwd", [
        "abc12345", "Passw0rd", "A1b2c3d4", "test2024Pwd",
    ])
    def test_valid_passwords(self, valid_pwd):
        """合法密码不应抛异常"""
        validate_password(valid_pwd)  # 无异常即通过

    @pytest.mark.parametrize("invalid_pwd,reason", [
        ("", "空密码"),
        ("123", "不足8位"),
        ("12345678", "纯数字无字母"),
        ("abcdefgh", "纯字母无数字"),
        ("abc1234", "刚好7位不满足8位"),
    ])
    def test_invalid_passwords(self, invalid_pwd, reason):
        """非法密码应抛 ValueError"""
        with pytest.raises(ValueError, reason=reason):
            validate_password(invalid_pwd)


# ============ JWT ============

class TestJWT:
    def test_create_and_decode(self):
        """生成的 token 应能正确解码出 payload"""
        token = create_access_token({"sub": "1", "role": "admin", "username": "admin"})
        payload = decode_access_token(token)
        assert payload["sub"] == "1"
        assert payload["role"] == "admin"
        assert payload["username"] == "admin"

    def test_decode_invalid_token_raises_401(self):
        """无效 token 应抛 401"""
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            decode_access_token("invalid.token.here")
        assert exc_info.value.status_code == 401


# ============ 登录防爆破限流器 ============

class TestLoginRateLimiter:
    def test_allows_up_to_max_fails(self):
        """未达阈值不应锁定"""
        limiter = LoginRateLimiter(max_fails=3, lock_seconds=60)
        for _ in range(2):
            limiter.record_fail("user1")
        limiter.check_locked("user1")  # 未达3次，不抛异常即通过

    def test_locks_after_max_fails(self):
        """达到阈值后应锁定，check_locked 抛 429"""
        from fastapi import HTTPException
        limiter = LoginRateLimiter(max_fails=3, lock_seconds=60)
        for _ in range(3):
            limiter.record_fail("user2")
        with pytest.raises(HTTPException) as exc_info:
            limiter.check_locked("user2")
        assert exc_info.value.status_code == 429

    def test_reset_after_success(self):
        """成功登录后应清空计数，不再锁定"""
        limiter = LoginRateLimiter(max_fails=3, lock_seconds=60)
        for _ in range(3):
            limiter.record_fail("user3")
        # 此时已锁定
        assert limiter.remaining_lock("user3") > 0
        # 成功登录后重置
        limiter.reset("user3")
        assert limiter.remaining_lock("user3") == 0

    def test_different_users_independent(self):
        """不同用户的限流应相互独立"""
        limiter = LoginRateLimiter(max_fails=2, lock_seconds=60)
        limiter.record_fail("userA")
        limiter.record_fail("userA")
        # userA 已锁定
        assert limiter.remaining_lock("userA") > 0
        # userB 未受影响
        assert limiter.remaining_lock("userB") == 0

    def test_lock_expires(self):
        """锁定到期后应自动解锁"""
        limiter = LoginRateLimiter(max_fails=1, lock_seconds=1)
        limiter.record_fail("userExpire")
        assert limiter.remaining_lock("userExpire") > 0
        time.sleep(1.1)
        assert limiter.remaining_lock("userExpire") == 0
