"""
物料大类维护 API

鉴权策略：
- GET（读）：所有登录用户可访问（用于筛选器）
- POST/PUT/DELETE（写）：仅 admin
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from ..database import get_db
from ..auth import get_current_user, require_admin
from ..models import User
from ..services import material_major_category_service
from ..schemas import (
    MaterialMajorCategoryCreate,
    MaterialMajorCategoryUpdate,
    MaterialMajorCategoryResponse,
)

router = APIRouter()


def _ok(data=None, message="成功"):
    return {"code": 200, "message": message, "data": data}


@router.get("", summary="分页查询物料大类维护记录")
def list_records(
    company_code: Optional[str] = Query(None, description="按公司代码过滤"),
    material_code: Optional[str] = Query(None, description="按物料编码精确过滤"),
    major_category: Optional[str] = Query(None, description="按物料大类过滤"),
    keyword: Optional[str] = Query(None, description="模糊搜索（物料编码/名称/大类）"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页条数"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items, total = material_major_category_service.list_categories(
        db,
        company_code=company_code,
        material_code=material_code,
        major_category=major_category,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    return {
        "code": 200,
        "message": "查询成功",
        "data": {
            "items": [MaterialMajorCategoryResponse.model_validate(i).model_dump() for i in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    }


@router.get("/options", summary="获取所有物料大类下拉（用于全局筛选器）")
def get_major_options(
    company_code: Optional[str] = Query(None, description="按公司代码过滤"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items = material_major_category_service.list_major_categories(db, company_code=company_code)
    return _ok(items)


@router.get("/{record_id}", summary="获取物料大类维护详情")
def get_record(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    obj = material_major_category_service.get_category(db, record_id)
    if not obj:
        raise HTTPException(404, "记录不存在")
    return _ok(MaterialMajorCategoryResponse.model_validate(obj).model_dump())


@router.post("", summary="新增物料大类维护记录")
def create_record(
    data: MaterialMajorCategoryCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    try:
        obj = material_major_category_service.create_category(db, data)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _ok(MaterialMajorCategoryResponse.model_validate(obj).model_dump(), message="创建成功")


@router.put("/{record_id}", summary="更新物料大类维护记录")
def update_record(
    record_id: int,
    data: MaterialMajorCategoryUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    obj = material_major_category_service.update_category(db, record_id, data)
    if not obj:
        raise HTTPException(404, "记录不存在")
    return _ok(MaterialMajorCategoryResponse.model_validate(obj).model_dump(), message="更新成功")


@router.delete("/{record_id}", summary="删除物料大类维护记录")
def delete_record(
    record_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    ok = material_major_category_service.delete_category(db, record_id)
    if not ok:
        raise HTTPException(404, "记录不存在")
    return _ok(message="删除成功")
