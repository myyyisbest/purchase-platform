"""
审计日志只读 API（admin）
"""
from datetime import datetime, date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from ..database import get_db
from ..auth import require_admin
from ..models import User, AuditLog

router = APIRouter()


def _ok(data=None, message="成功"):
    return {"code": 200, "message": message, "data": data}


@router.get("", summary="分页查询审计日志")
def list_audit_logs(
    username: Optional[str] = Query(None),
    method: Optional[str] = Query(None),
    path_keyword: Optional[str] = Query(None, description="路径模糊"),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    q = db.query(AuditLog)
    if username:
        q = q.filter(AuditLog.username.ilike(f"%{username}%"))
    if method:
        q = q.filter(AuditLog.method == method.upper())
    if path_keyword:
        q = q.filter(AuditLog.path.ilike(f"%{path_keyword}%"))
    if date_from:
        q = q.filter(AuditLog.created_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        q = q.filter(AuditLog.created_at <= datetime.combine(date_to, datetime.max.time()))

    total = q.count()
    items = (
        q.order_by(AuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return _ok({
        "items": [
            {
                "id": i.id,
                "user_id": i.user_id,
                "username": i.username,
                "method": i.method,
                "path": i.path,
                "status_code": i.status_code,
                "client_ip": i.client_ip,
                "body_summary": i.body_summary,
                "cost_ms": i.cost_ms,
                "created_at": i.created_at.isoformat() if i.created_at else None,
            }
            for i in items
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    })
