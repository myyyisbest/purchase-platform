"""
汇率管理API
支持区间有效期模型的汇率 CRUD，含区间重叠校验

鉴权策略：
- GET（读）：所有登录用户可访问（用于下拉/查询）
- POST/PUT/DELETE（写）：仅 admin
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import date as date_type
from typing import Optional

from ..database import get_db
from ..auth import get_current_user, require_admin
from ..models import User
from ..services import exchange_rate_service
from ..schemas import ExchangeRateCreate, ExchangeRateUpdate, ExchangeRateResponse

router = APIRouter()


def _ok(data=None, message="成功"):
    return {"code": 200, "message": message, "data": data}


# ============================================
# 币种列表 / 汇率列表（读，所有登录用户）
# ============================================
@router.get("/currencies", summary="获取所有币种列表")
def list_currencies(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items = exchange_rate_service.get_currencies(db)
    return _ok(items)


@router.get("/order-currencies", summary="获取采购订单中实际使用的币种列表")
def list_order_currencies(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """从 purchase_records 表提取去重的 order_currency，作为汇率维护的币种来源"""
    from ..models import PurchaseRecord
    from sqlalchemy import func
    rows = (
        db.query(PurchaseRecord.order_currency)
        .filter(PurchaseRecord.order_currency.isnot(None), PurchaseRecord.order_currency != '')
        .distinct()
        .order_by(PurchaseRecord.order_currency)
        .all()
    )
    currencies = [r[0] for r in rows]
    return _ok(currencies)


@router.get("", summary="获取汇率列表（分页）")
def list_rates(
    from_currency: Optional[str] = Query(None, description="按币种筛选"),
    effective_date: Optional[str] = Query(None, description="筛选指定日期生效的汇率（YYYY-MM-DD）"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    target_date = None
    if effective_date:
        try:
            target_date = date_type.fromisoformat(effective_date)
        except ValueError:
            raise HTTPException(400, "日期格式错误，请使用 YYYY-MM-DD")

    items, total = exchange_rate_service.list_rates(db, from_currency, target_date, page, page_size)
    return {
        "code": 200,
        "message": "查询成功",
        "data": {
            "items": [ExchangeRateResponse.model_validate(i).model_dump() for i in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    }


# ============================================
# 详情（读）
# ============================================
@router.get("/{rate_id}", summary="获取汇率详情")
def get_rate(
    rate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = exchange_rate_service.get_rate(db, rate_id)
    if not item:
        raise HTTPException(404, "汇率记录不存在")
    return _ok(ExchangeRateResponse.model_validate(item).model_dump())


# ============================================
# 创建（写，admin only）
# ============================================
@router.post("", summary="创建汇率")
def create_rate(
    data: ExchangeRateCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    try:
        item = exchange_rate_service.create_rate(db, data)
        return _ok(ExchangeRateResponse.model_validate(item).model_dump(), message="创建成功")
    except ValueError as e:
        raise HTTPException(400, str(e))


# ============================================
# 更新（写，admin only）
# ============================================
@router.put("/{rate_id}", summary="更新汇率")
def update_rate(
    rate_id: int,
    data: ExchangeRateUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    try:
        item = exchange_rate_service.update_rate(db, rate_id, data)
        if not item:
            raise HTTPException(404, "汇率记录不存在")
        return _ok(ExchangeRateResponse.model_validate(item).model_dump(), message="更新成功")
    except ValueError as e:
        raise HTTPException(400, str(e))


# ============================================
# 删除（写，admin only）
# ============================================
@router.delete("/{rate_id}", summary="删除汇率")
def delete_rate(
    rate_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    ok = exchange_rate_service.delete_rate(db, rate_id)
    if not ok:
        raise HTTPException(400, "删除失败：记录不存在")
    return _ok(message="删除成功")
