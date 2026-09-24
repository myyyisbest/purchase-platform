"""
供应商 API
- GET 列表/详情：登录用户
- 写操作 + sync：admin
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..auth import get_current_user, require_admin
from ..models import User
from ..schemas import SupplierCreate, SupplierUpdate, SupplierResponse
from ..services import supplier_service

router = APIRouter()


def _ok(data=None, message="成功"):
    return {"code": 200, "message": message, "data": data}


@router.get("", summary="分页查询供应商")
def list_suppliers(
    keyword: Optional[str] = Query(None, description="编码/名称模糊"),
    category: Optional[str] = Query(None, description="类别：关联方/非关联方"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    items, total = supplier_service.list_suppliers(
        db, keyword=keyword, category=category, page=page, page_size=page_size
    )
    return _ok({
        "items": [SupplierResponse.model_validate(i).model_dump() for i in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    })


@router.post("/sync-from-records", summary="从采购记录同步供应商（admin）")
def sync_suppliers(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    stats = supplier_service.sync_from_records(db)
    return _ok(stats, message="同步完成")


@router.get("/{supplier_id}", summary="供应商详情")
def get_supplier(
    supplier_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    obj = supplier_service.get_supplier(db, supplier_id)
    if not obj:
        raise HTTPException(404, "供应商不存在")
    return _ok(SupplierResponse.model_validate(obj).model_dump())


@router.post("", summary="新增供应商（admin）")
def create_supplier(
    data: SupplierCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    try:
        obj = supplier_service.create_supplier(db, data)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _ok(SupplierResponse.model_validate(obj).model_dump(), message="创建成功")


@router.put("/{supplier_id}", summary="更新供应商（admin）")
def update_supplier(
    supplier_id: int,
    data: SupplierUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    obj = supplier_service.update_supplier(db, supplier_id, data)
    if not obj:
        raise HTTPException(404, "供应商不存在")
    return _ok(SupplierResponse.model_validate(obj).model_dump(), message="更新成功")


@router.delete("/{supplier_id}", summary="删除供应商（admin）")
def delete_supplier(
    supplier_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    ok = supplier_service.delete_supplier(db, supplier_id)
    if not ok:
        raise HTTPException(404, "供应商不存在")
    return _ok(message="删除成功")
