"""
认证 API
登录、获取当前用户、修改密码
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, UserCompanyAccess
from ..auth import (
    verify_password, create_access_token, hash_password,
    get_current_user, get_user_company_codes, validate_password,
    login_limiter,
)
from datetime import datetime
from ..schemas import LoginRequest, LoginResponse, ChangePasswordRequest, UserResponse

router = APIRouter()


def _build_user_response(user: User, company_codes: list) -> dict:
    """构建用户响应字典"""
    return {
        "id": user.id,
        "username": user.username,
        "real_name": user.real_name or "",
        "email": user.email or "",
        "role": user.role,
        "company_id": user.company_id,
        "is_active": user.is_active,
        "must_change_password": user.must_change_password,
        "company_codes": company_codes,
        "last_login": user.last_login,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }


@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """用户登录，返回 JWT token（含登录失败限流）"""
    # 1. 登录失败限流：同一用户名连续失败达阈值后临时锁定
    login_limiter.check_locked(req.username)

    user = db.query(User).filter(User.username == req.username).first()
    # 用户不存在或密码错误统一返回同一文案，避免用户名枚举
    if not user or not verify_password(req.password, user.password_hash):
        fails = login_limiter.record_fail(req.username)
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账户已被禁用")

    # 2. 登录成功：清空失败计数，记录最后登录时间（naive 本地时间，系统时区 Asia/Shanghai）
    login_limiter.reset(req.username)
    user.last_login = datetime.now()
    db.commit()
    db.refresh(user)

    # 3. 生成 token 与权限上下文
    # token 携带 user_id/role/username，审计中间件可从 token 直接解析操作者
    token = create_access_token({
        "sub": str(user.id),
        "role": user.role,
        "username": user.username,
    })
    company_codes = get_user_company_codes(user, db)

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": _build_user_response(user, company_codes),
    }


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取当前用户信息"""
    company_codes = get_user_company_codes(current_user, db)
    return _build_user_response(current_user, company_codes)


@router.post("/change-password")
def change_password(
    req: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """修改密码（统一走密码强度校验）"""
    if not verify_password(req.old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="旧密码错误")
    try:
        validate_password(req.new_password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if req.new_password == req.old_password:
        raise HTTPException(status_code=400, detail="新密码不能与旧密码相同")

    current_user.password_hash = hash_password(req.new_password)
    current_user.must_change_password = False
    db.commit()
    return {"code": 200, "message": "密码修改成功"}
