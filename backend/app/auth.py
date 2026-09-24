"""
认证与授权核心模块
JWT Token + bcrypt 密码哈希 + FastAPI Depends

设计要点：
- 密码强度统一由 validate_password 校验（至少8位且含字母与数字）
- 登录防爆破由 LoginRateLimiter 提供进程内限流（线程安全）
- 所有时间统一使用东八区（UTC+8）时区感知对象，避免 utcnow 与本地时间混用
"""
import os
import hmac
import time
import threading
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List

import jwt
from passlib.hash import bcrypt
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from .database import get_db
from .models import User, UserCompanyAccess

logger = logging.getLogger(__name__)

# JWT 配置（必须通过环境变量注入；缺失则启动失败，杜绝可预测密钥）
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET or len(JWT_SECRET) < 16:
    raise RuntimeError(
        "JWT_SECRET 未配置或长度不足 16 位，请在 .env 中设置随机长字符串后重启"
    )
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))  # 默认 24 小时

# 系统时区固定为东八区（Asia/Shanghai），JWT 过期时间与业务时间统一使用此时区
CST = timezone(timedelta(hours=8))

# 默认初始密码（仅用于首次创建 admin/user，可通过环境变量覆盖；建议首次登录后立即修改）
DEFAULT_ADMIN_PASSWORD = os.getenv("DEFAULT_ADMIN_PASSWORD", "")
DEFAULT_USER_PASSWORD = os.getenv("DEFAULT_USER_PASSWORD", "")
if not DEFAULT_ADMIN_PASSWORD or not DEFAULT_USER_PASSWORD:
    logger.warning(
        "DEFAULT_ADMIN_PASSWORD/DEFAULT_USER_PASSWORD 未在 .env 配置，"
        "首次创建账户将失败，请补齐后重启"
    )

security = HTTPBearer(auto_error=False)


# ============ 密码工具 ============

def hash_password(password: str) -> str:
    return bcrypt.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.verify(plain, hashed)


def validate_password(password: str) -> None:
    """
    密码强度统一校验：至少8位，且必须同时包含字母和数字。
    校验不通过抛出 ValueError，由调用方转为 HTTPException。
    """
    if not password or len(password) < 8:
        raise ValueError("密码至少8位")
    if not any(c.isalpha() for c in password):
        raise ValueError("密码必须包含字母")
    if not any(c.isdigit() for c in password):
        raise ValueError("密码必须包含数字")


# ============ JWT 工具 ============

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """生成 JWT（过期时间使用东八区时区感知对象，PyJWT 会自动转为 UTC 时间戳）"""
    to_encode = data.copy()
    expire = datetime.now(CST) + (expires_delta or timedelta(minutes=JWT_EXPIRE_MINUTES))
    to_encode["exp"] = expire
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="无效的认证令牌")


# ============ 登录防爆破限流 ============

class LoginRateLimiter:
    """
    进程内登录失败限流器（线程安全）。
    策略：同一用户名连续失败达到阈值后锁定 N 秒，成功登录即清零。
    注：单实例方案；多实例部署需替换为 Redis 等共享存储。
    """

    def __init__(self, max_fails: int = 5, lock_seconds: int = 300):
        self._max_fails = max_fails
        self._lock_seconds = lock_seconds
        # username -> (连续失败次数, 锁定到期时间戳；0 表示未锁定)
        self._store: dict[str, tuple[int, float]] = {}
        self._guard = threading.Lock()

    def remaining_lock(self, username: str) -> int:
        """返回剩余锁定秒数，0 表示未锁定"""
        with self._guard:
            record = self._store.get(username)
            if not record:
                return 0
            _, lock_until = record
            return max(0, int(lock_until - time.time()))

    def check_locked(self, username: str) -> None:
        """未锁定直接返回；已锁定抛 429"""
        remaining = self.remaining_lock(username)
        if remaining > 0:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"登录失败次数过多，请 {remaining} 秒后重试",
            )

    def record_fail(self, username: str) -> int:
        """记录一次失败，返回当前累计失败次数"""
        with self._guard:
            fails, _ = self._store.get(username, (0, 0.0))
            fails += 1
            lock_until = time.time() + self._lock_seconds if fails >= self._max_fails else 0.0
            self._store[username] = (fails, lock_until)
            return fails

    def reset(self, username: str) -> None:
        """登录成功后清空失败计数"""
        with self._guard:
            self._store.pop(username, None)


# 全局单例：最多 5 次失败，锁定 5 分钟
login_limiter = LoginRateLimiter(max_fails=5, lock_seconds=300)


# ============ FastAPI Depends ============

def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """从 Authorization header 解析当前用户"""
    if credentials is None:
        raise HTTPException(status_code=401, detail="未提供认证凭证")
    payload = decode_access_token(credentials.credentials)
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=401, detail="无效的令牌")
    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账户已被禁用")
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """校验管理员角色"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return current_user


# ============ 公司权限工具 ============

def get_user_company_codes(user: User, db: Session) -> List[str]:
    """获取用户可访问的公司代码列表"""
    if user.role == "admin":
        return []  # 空列表代表不限制
    rows = (
        db.query(UserCompanyAccess.company_code)
        .filter(UserCompanyAccess.user_id == user.id)
        .all()
    )
    return [r[0] for r in rows]


def get_effective_company_codes(
    user: User,
    requested_codes: Optional[List[str]],
    db: Session,
) -> Optional[List[str]]:
    """
    计算有效公司过滤范围:
    - admin: 返回 requested_codes（或 None 代表不限制）
    - 普通用户: 返回 requested_codes 与用户授权的交集
    """
    if user.role == "admin":
        return requested_codes

    user_codes = get_user_company_codes(user, db)
    if not user_codes:
        raise HTTPException(status_code=403, detail="未授权任何公司数据，请联系管理员")

    if requested_codes:
        # 取交集
        effective = [c for c in requested_codes if c in user_codes]
        if not effective:
            raise HTTPException(status_code=403, detail="所选公司不在授权范围内")
        return effective

    return user_codes


# ============ Cron / 管理员双通道鉴权 ============

# 定时任务专用 Token（空则 cron 头鉴权失败关闭）
CRON_API_TOKEN = os.getenv("CRON_API_TOKEN") or os.getenv("HANA_SYNC_CRON_TOKEN") or ""


def _extract_cron_token(request: Request) -> Optional[str]:
    """从 X-Cron-Token 或 Authorization: Bearer 提取 cron token"""
    header = request.headers.get("X-Cron-Token")
    if header:
        return header.strip()
    auth_header = request.headers.get("Authorization") or ""
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return None


def require_admin_or_cron(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    允许 JWT 管理员 或 合法 Cron Token 访问。
    - Cron：仅当 CRON_API_TOKEN / HANA_SYNC_CRON_TOKEN 非空，且与头匹配（常量时间比较）
    - 否则回退 require_admin JWT
    返回 User（JWT 路径）或 None（cron 路径）
    """
    token = _extract_cron_token(request)
    configured = CRON_API_TOKEN
    # 若请求显式带了 X-Cron-Token，优先走 cron 通道（未配置则失败关闭）
    if request.headers.get("X-Cron-Token") is not None:
        if not configured:
            raise HTTPException(status_code=401, detail="Cron Token 未配置，拒绝访问")
        if not token or not hmac.compare_digest(token, configured):
            raise HTTPException(status_code=401, detail="无效的 Cron Token")
        return None  # cron 身份，无 User

    # 否则走 JWT admin
    if credentials is None:
        # 也允许 Authorization: Bearer <cron_token>（无 JWT 时）
        if configured and token and hmac.compare_digest(token, configured):
            return None
        raise HTTPException(status_code=401, detail="未提供认证凭证")

    # 先尝试 JWT
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = payload.get("sub")
        if user_id is not None:
            user = db.query(User).filter(User.id == int(user_id)).first()
            if user and user.is_active:
                if user.role != "admin":
                    raise HTTPException(status_code=403, detail="需要管理员权限")
                return user
    except HTTPException:
        # JWT 无效时，若 Bearer 恰好是 cron token 也可放行
        if configured and hmac.compare_digest(credentials.credentials, configured):
            return None
        raise

    # JWT 解析失败但 Bearer 是 cron token
    if configured and hmac.compare_digest(credentials.credentials, configured):
        return None
    raise HTTPException(status_code=401, detail="无效的认证令牌")

