"""
供应商服务：列表/CRUD + 从采购记录同步去重供应商
"""
from __future__ import annotations

from typing import Optional, Tuple, List

from sqlalchemy.orm import Session
from sqlalchemy import or_, func

from ..models import Supplier, PurchaseRecord
from ..schemas import SupplierCreate, SupplierUpdate


def list_suppliers(
    db: Session,
    *,
    keyword: Optional[str] = None,
    category: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[List[Supplier], int]:
    q = db.query(Supplier)
    if keyword:
        pattern = f"%{keyword}%"
        q = q.filter(
            or_(
                Supplier.supplier_code.ilike(pattern),
                Supplier.supplier_name.ilike(pattern),
            )
        )
    if category:
        q = q.filter(Supplier.category == category)
    total = q.count()
    items = (
        q.order_by(Supplier.supplier_code)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def get_supplier(db: Session, supplier_id: int) -> Optional[Supplier]:
    return db.query(Supplier).filter(Supplier.id == supplier_id).first()


def create_supplier(db: Session, data: SupplierCreate) -> Supplier:
    existing = db.query(Supplier).filter(Supplier.supplier_code == data.supplier_code).first()
    if existing:
        raise ValueError(f"供应商编码已存在: {data.supplier_code}")
    obj = Supplier(**data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_supplier(db: Session, supplier_id: int, data: SupplierUpdate) -> Optional[Supplier]:
    obj = get_supplier(db, supplier_id)
    if not obj:
        return None
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


def delete_supplier(db: Session, supplier_id: int) -> bool:
    obj = get_supplier(db, supplier_id)
    if not obj:
        return False
    db.delete(obj)
    db.commit()
    return True


def sync_from_records(db: Session) -> dict:
    """
    从采购记录 upsert 去重供应商（按 supplier_code）。
    仅同步未软删除记录；已存在则更新名称/类别（若记录侧有值）。
    """
    rows = (
        db.query(
            PurchaseRecord.supplier_code,
            func.max(PurchaseRecord.supplier_name).label("supplier_name"),
            func.max(PurchaseRecord.supplier_category).label("category"),
        )
        .filter(
            PurchaseRecord.deleted_at.is_(None),
            PurchaseRecord.supplier_code.isnot(None),
            PurchaseRecord.supplier_code != "",
        )
        .group_by(PurchaseRecord.supplier_code)
        .all()
    )
    created = updated = 0
    existing_map = {
        s.supplier_code: s
        for s in db.query(Supplier).all()
    }
    for code, name, category in rows:
        if code in existing_map:
            s = existing_map[code]
            changed = False
            if name and s.supplier_name != name:
                s.supplier_name = name
                changed = True
            if category and s.category != category:
                s.category = category
                changed = True
            if changed:
                updated += 1
        else:
            db.add(
                Supplier(
                    supplier_code=code,
                    supplier_name=name or code,
                    category=category,
                )
            )
            created += 1
    db.commit()
    return {"created": created, "updated": updated, "scanned": len(rows)}
