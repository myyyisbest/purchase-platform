"""
汇率服务 - 区间有效期模型
每条汇率覆盖 [effective_date, expiry_date] 区间，expiry_date 为 NULL 表示永久生效。
同一币种同一时间点只能有一条生效汇率（区间不重叠，由本服务校验）。
"""
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from ..models import ExchangeRate
from ..schemas import ExchangeRateCreate, ExchangeRateUpdate
from typing import Optional, List, Tuple
from datetime import date, datetime


# ============================================
# 列表 / 详情
# ============================================
def list_rates(
    db: Session,
    from_currency: Optional[str] = None,
    target_date: Optional[date] = None,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[List[ExchangeRate], int]:
    """分页查询汇率列表，可按币种 / 某天是否生效筛选"""
    q = db.query(ExchangeRate)
    if from_currency:
        q = q.filter(ExchangeRate.from_currency == from_currency)
    if target_date:
        # target_date 落在 [effective_date, expiry_date] 区间内（expiry 为空视为永久）
        q = q.filter(
            ExchangeRate.effective_date <= target_date,
            or_(ExchangeRate.expiry_date.is_(None), ExchangeRate.expiry_date >= target_date),
        )
    total = q.count()
    items = (
        q.order_by(ExchangeRate.from_currency, ExchangeRate.effective_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def get_rate(db: Session, rate_id: int) -> Optional[ExchangeRate]:
    return db.query(ExchangeRate).filter(ExchangeRate.id == rate_id).first()


def get_currencies(db: Session) -> List[str]:
    """去重查询所有源币种，供前端筛选用"""
    rows = db.query(ExchangeRate.from_currency).distinct().all()
    return sorted([r[0] for r in rows])


# ============================================
# 区间重叠校验
# ============================================
def _find_overlap(
    db: Session,
    currency: str,
    effective: date,
    expiry: Optional[date],
    exclude_id: Optional[int] = None,
) -> Optional[ExchangeRate]:
    """
    查找同币种下与新区间 [effective, expiry] 重叠的已有记录。
    重叠条件：existing.effective <= new.expiry AND (existing.expiry IS NULL OR existing.expiry >= new.effective)
    返回第一条冲突记录，供调用方报错。
    """
    q = db.query(ExchangeRate).filter(ExchangeRate.from_currency == currency)
    if exclude_id:
        q = q.filter(ExchangeRate.id != exclude_id)
    # new.expiry 为空表示新区间永久生效，会与该币种所有"生效到新 effective 之后"的记录重叠
    new_exp_bound = expiry if expiry is not None else date.max
    q = q.filter(
        and_(
            ExchangeRate.effective_date <= new_exp_bound,
            or_(
                ExchangeRate.expiry_date.is_(None),
                ExchangeRate.expiry_date >= effective,
            ),
        )
    )
    return q.first()


# ============================================
# CRUD
# ============================================
def create_rate(db: Session, data: ExchangeRateCreate) -> ExchangeRate:
    # 区间重叠校验
    conflict = _find_overlap(db, data.from_currency, data.effective_date, data.expiry_date)
    if conflict:
        raise ValueError(
            f"与现有汇率区间重叠（{conflict.from_currency}: "
            f"{conflict.effective_date} ~ {conflict.expiry_date or '永久'}）"
        )
    obj = ExchangeRate(**data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_rate(db: Session, rate_id: int, data: ExchangeRateUpdate) -> Optional[ExchangeRate]:
    obj = get_rate(db, rate_id)
    if not obj:
        return None

    # 计算更新后的生效/失效日期（用于重叠校验）
    new_effective = data.effective_date if data.effective_date is not None else obj.effective_date
    new_expiry = data.expiry_date  # 显式传 None 表示永久生效
    if "expiry_date" not in data.model_dump(exclude_unset=True):
        new_expiry = obj.expiry_date

    # 区间重叠校验（排除自身）
    conflict = _find_overlap(db, obj.from_currency, new_effective, new_expiry, exclude_id=rate_id)
    if conflict:
        raise ValueError(
            f"与现有汇率区间重叠（{conflict.from_currency}: "
            f"{conflict.effective_date} ~ {conflict.expiry_date or '永久'}）"
        )

    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


def delete_rate(db: Session, rate_id: int) -> bool:
    obj = get_rate(db, rate_id)
    if not obj:
        return False
    db.delete(obj)
    db.commit()
    return True


# ============================================
# 生效汇率查询（供 import_service 使用）
# ============================================
def get_effective_rate(db: Session, currency: str, target_date: date) -> Optional[ExchangeRate]:
    """取指定币种在 target_date 生效的汇率记录"""
    return (
        db.query(ExchangeRate)
        .filter(
            ExchangeRate.from_currency == currency,
            ExchangeRate.effective_date <= target_date,
            or_(ExchangeRate.expiry_date.is_(None), ExchangeRate.expiry_date >= target_date),
        )
        .order_by(ExchangeRate.effective_date.desc())
        .first()
    )


def get_active_rates(db: Session, target_date: Optional[date] = None) -> dict:
    """
    返回所有币种在 target_date 生效的汇率字典 {currency: rate}。
    target_date 默认今天。CNY 恒为 1.0。
    供 import_service._load_exchange_rates() 使用。
    """
    if target_date is None:
        target_date = date.today()
    # 一次性查出所有"覆盖 target_date"的记录，按币种分组取最新生效的
    rows = (
        db.query(ExchangeRate)
        .filter(
            ExchangeRate.effective_date <= target_date,
            or_(ExchangeRate.expiry_date.is_(None), ExchangeRate.expiry_date >= target_date),
        )
        .order_by(ExchangeRate.from_currency, ExchangeRate.effective_date.desc())
        .all()
    )
    rates = {}
    for r in rows:
        # 因为按 effective_date desc 排序，每个币种第一条就是最新的
        if r.from_currency not in rates:
            rates[r.from_currency] = float(r.exchange_rate)
    rates["CNY"] = 1.0
    return rates
