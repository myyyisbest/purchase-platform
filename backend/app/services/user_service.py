"""
用户管理服务
用户 CRUD + CSV批量导入 + 公司授权
"""
import csv
import io
import logging
from typing import Optional, List
from datetime import datetime

from sqlalchemy.orm import Session
from ..models import User, UserCompanyAccess
from ..auth import (
    hash_password, validate_password,
    DEFAULT_ADMIN_PASSWORD, DEFAULT_USER_PASSWORD,
)

logger = logging.getLogger(__name__)


class UserService:
    def __init__(self, db: Session):
        self.db = db

    def list_users(self) -> list:
        """查询所有用户 + 各自公司授权"""
        users = self.db.query(User).order_by(User.id).all()
        result = []
        for u in users:
            codes = (
                self.db.query(UserCompanyAccess.company_code)
                .filter(UserCompanyAccess.user_id == u.id)
                .all()
            )
            result.append({
                "id": u.id,
                "username": u.username,
                "real_name": u.real_name or "",
                "email": u.email or "",
                "role": u.role,
                "is_active": u.is_active,
                "must_change_password": u.must_change_password,
                "company_codes": [c[0] for c in codes],
                "last_login": str(u.last_login) if u.last_login else "",
                "created_at": str(u.created_at) if u.created_at else "",
            })
        return result

    def create_user(
        self,
        username: str,
        real_name: str = "",
        email: str = "",
        role: str = "user",
        password: Optional[str] = None,
        company_codes: Optional[List[str]] = None,
    ) -> dict:
        """创建用户"""
        existing = self.db.query(User).filter(User.username == username).first()
        if existing:
            raise ValueError(f"用户名 {username} 已存在")

        # 密码处理：优先用调用方传入的密码（需通过强度校验）；否则用默认密码（须非空）
        if password:
            validate_password(password)
            pwd_hash = hash_password(password)
            must_change = False
        elif DEFAULT_USER_PASSWORD:
            pwd_hash = hash_password(DEFAULT_USER_PASSWORD)
            must_change = True  # 默认密码强制改密
        else:
            raise ValueError("未指定密码且 DEFAULT_USER_PASSWORD 未配置，无法创建用户")

        user = User(
            username=username,
            password_hash=pwd_hash,
            real_name=real_name,
            email=email,
            role=role,
            must_change_password=must_change,
        )
        self.db.add(user)
        self.db.flush()  # 获取 user.id

        # 设置公司授权
        if company_codes and role == "user":
            self._set_user_access(user.id, company_codes)

        self.db.commit()
        self.db.refresh(user)
        return {"id": user.id, "username": user.username}

    def import_users_csv(self, csv_content: str) -> dict:
        """
        CSV批量导入用户
        格式: username,real_name,role,company_codes
        company_codes 用分号分隔，如: 1000;2000;D230
        """
        stats = {"total": 0, "success": 0, "failed": 0, "errors": []}
        reader = csv.DictReader(io.StringIO(csv_content))

        for i, row in enumerate(reader):
            stats["total"] += 1
            try:
                username = row.get("username", "").strip()
                if not username:
                    raise ValueError("用户名为空")

                real_name = row.get("real_name", "").strip()
                role = row.get("role", "user").strip()
                if role not in ("admin", "user"):
                    role = "user"

                codes_str = row.get("company_codes", "").strip()
                codes = [c.strip() for c in codes_str.split(";") if c.strip()] if codes_str else []

                self.create_user(
                    username=username,
                    real_name=real_name,
                    role=role,
                    company_codes=codes,
                )
                stats["success"] += 1
            except Exception as e:
                stats["failed"] += 1
                stats["errors"].append({"row": i + 2, "username": row.get("username", ""), "error": str(e)})

        return stats

    def update_user(self, user_id: int, **kwargs) -> dict:
        """编辑用户"""
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("用户不存在")

        if kwargs.get("real_name") is not None:
            user.real_name = kwargs["real_name"]
        if kwargs.get("email") is not None:
            user.email = kwargs["email"]
        if kwargs.get("role") is not None:
            user.role = kwargs["role"]
        if kwargs.get("is_active") is not None:
            user.is_active = kwargs["is_active"]

        # 更新公司授权
        if kwargs.get("company_codes") is not None:
            self._set_user_access(user.id, kwargs["company_codes"])

        self.db.commit()
        return {"id": user.id, "username": user.username}

    def delete_user(self, user_id: int):
        """删除用户"""
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("用户不存在")
        if user.role == "admin" and user.username == "admin":
            raise ValueError("不能删除系统管理员账户")

        # 删除公司授权
        self.db.query(UserCompanyAccess).filter(UserCompanyAccess.user_id == user_id).delete()
        self.db.delete(user)
        self.db.commit()

    def reset_password(self, user_id: int) -> dict:
        """管理员重置密码"""
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("用户不存在")

        if user.role == "admin":
            default_pwd = DEFAULT_ADMIN_PASSWORD
        else:
            default_pwd = DEFAULT_USER_PASSWORD
        if not default_pwd:
            raise ValueError("默认密码未配置（DEFAULT_*_PASSWORD），无法重置，请先在 .env 中设置")

        user.password_hash = hash_password(default_pwd)
        user.must_change_password = True
        self.db.commit()
        return {"id": user.id, "username": user.username, "message": "密码已重置为默认密码"}

    def update_user_access(self, user_id: int, company_codes: List[str]):
        """设置用户公司授权"""
        self._set_user_access(user_id, company_codes)
        self.db.commit()

    def _set_user_access(self, user_id: int, company_codes: List[str]):
        """内部方法：替换用户的公司授权"""
        # 删除旧授权
        self.db.query(UserCompanyAccess).filter(UserCompanyAccess.user_id == user_id).delete()
        # 添加新授权
        for code in company_codes:
            access = UserCompanyAccess(user_id=user_id, company_code=code)
            self.db.add(access)

    def ensure_admin_exists(self):
        """确保 admin 账户存在（启动时调用）"""
        admin = self.db.query(User).filter(User.username == "admin").first()
        if admin:
            return
        # 默认密码未配置时不创建空密码管理员，仅记录警告等待人工配置
        if not DEFAULT_ADMIN_PASSWORD:
            logger.warning(
                "admin 账户不存在且 DEFAULT_ADMIN_PASSWORD 未配置，已跳过自动创建，"
                "请在 .env 设置后重启"
            )
            return
        admin = User(
            username="admin",
            password_hash=hash_password(DEFAULT_ADMIN_PASSWORD),
            real_name="系统管理员",
            role="admin",
            must_change_password=False,
            is_active=True,
        )
        self.db.add(admin)
        self.db.commit()
