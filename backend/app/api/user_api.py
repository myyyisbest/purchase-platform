"""
用户管理 API（管理员专属）
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..auth import require_admin
from ..services.user_service import UserService
from ..schemas import UserCreateRequest, UserEditRequest, UserCompanyAccessUpdate

router = APIRouter()


@router.get("/")
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """获取用户列表"""
    return UserService(db).list_users()


@router.post("/")
def create_user(
    req: UserCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """创建用户"""
    try:
        result = UserService(db).create_user(
            username=req.username,
            real_name=req.real_name or "",
            email=req.email or "",
            role=req.role,
            password=req.password,
            company_codes=req.company_codes or [],
        )
        return {"code": 200, "message": "创建成功", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/import")
async def import_users(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """CSV 批量导入用户"""
    content = await file.read()
    # 尝试 UTF-8 和 GBK
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("gbk")

    stats = UserService(db).import_users_csv(text)
    return {"code": 200, "data": stats}


@router.put("/{user_id}")
def update_user(
    user_id: int,
    req: UserEditRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """编辑用户"""
    try:
        result = UserService(db).update_user(
            user_id,
            real_name=req.real_name,
            email=req.email,
            role=req.role,
            is_active=req.is_active,
            company_codes=req.company_codes,
        )
        return {"code": 200, "message": "更新成功", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """删除用户"""
    try:
        UserService(db).delete_user(user_id)
        return {"code": 200, "message": "删除成功"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{user_id}/reset-password")
def reset_password(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """重置用户密码"""
    try:
        result = UserService(db).reset_password(user_id)
        return {"code": 200, "message": result["message"]}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{user_id}/access")
def update_user_access(
    user_id: int,
    req: UserCompanyAccessUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """设置用户公司授权"""
    UserService(db).update_user_access(user_id, req.company_codes)
    return {"code": 200, "message": "授权更新成功"}
