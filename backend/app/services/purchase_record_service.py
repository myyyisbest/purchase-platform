"""
采购记录明细查询服务
支持多维过滤 + 分页，供明细页与 Excel 导出复用
"""
from datetime import date
from decimal import Decimal
from typing import List, Optional, Dict, Any

from sqlalchemy import or_, func
from sqlalchemy.orm import Session

from ..models import PurchaseRecord


class PurchaseRecordService:
    """采购记录查询服务"""

    EXPORT_MAX_ROWS = 50000

    def __init__(self, db: Session):
        self.db = db

    def _base_query(
        self,
        company_codes: Optional[List[str]] = None,
        material_code: Optional[str] = None,
        material_keyword: Optional[str] = None,
        supplier_keyword: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        fiscal_year: Optional[int] = None,
        po_number: Optional[str] = None,
        material_doc: Optional[str] = None,
    ):
        q = self.db.query(PurchaseRecord).filter(PurchaseRecord.deleted_at.is_(None))

        if company_codes:
            q = q.filter(PurchaseRecord.company_code.in_(company_codes))
        if material_code:
            q = q.filter(PurchaseRecord.material_code == material_code.strip())
        if material_keyword:
            pattern = f"%{material_keyword.strip()}%"
            q = q.filter(
                or_(
                    PurchaseRecord.material_code.ilike(pattern),
                    PurchaseRecord.material_name.ilike(pattern),
                )
            )
        if supplier_keyword:
            pattern = f"%{supplier_keyword.strip()}%"
            q = q.filter(
                or_(
                    PurchaseRecord.supplier_code.ilike(pattern),
                    PurchaseRecord.supplier_name.ilike(pattern),
                )
            )
        if date_from:
            q = q.filter(PurchaseRecord.transaction_date >= date_from)
        if date_to:
            q = q.filter(PurchaseRecord.transaction_date <= date_to)
        if fiscal_year:
            q = q.filter(PurchaseRecord.fiscal_year == fiscal_year)
        if po_number:
            q = q.filter(PurchaseRecord.po_number.ilike(f"%{po_number.strip()}%"))
        if material_doc:
            q = q.filter(PurchaseRecord.material_doc.ilike(f"%{material_doc.strip()}%"))

        return q

    @staticmethod
    def _serialize(record: PurchaseRecord) -> Dict[str, Any]:
        def _num(v):
            if v is None:
                return None
            if isinstance(v, Decimal):
                return float(v)
            return v

        return {
            "id": record.id,
            "company_code": record.company_code or "",
            "company_name": record.company_name or "",
            "fiscal_year": record.fiscal_year,
            "transaction_date": record.transaction_date.isoformat() if record.transaction_date else None,
            "supplier_code": record.supplier_code or "",
            "supplier_name": record.supplier_name or "",
            "supplier_category": record.supplier_category or "",
            "material_code": record.material_code or "",
            "material_name": record.material_name or "",
            "specification": record.specification or "",
            "material_category": record.material_category or "",
            "base_currency": record.base_currency or "",
            "unit": record.unit or "",
            "quantity": _num(record.quantity),
            "unit_price": _num(record.unit_price),
            "amount": _num(record.amount),
            "order_currency": record.order_currency or "",
            "order_unit_price": _num(record.order_unit_price),
            "order_amount": _num(record.order_amount),
            "exchange_rate": _num(record.exchange_rate),
            "cny_amount": _num(record.cny_amount),
            "po_number": record.po_number or "",
            "material_doc": record.material_doc or "",
            "line_item": record.line_item or "",
            "purchase_purpose": record.purchase_purpose or "",
            "data_source": record.data_source or "",
            "import_batch_id": record.import_batch_id or "",
        }

    def list_records(
        self,
        company_codes: Optional[List[str]] = None,
        material_code: Optional[str] = None,
        material_keyword: Optional[str] = None,
        supplier_keyword: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        fiscal_year: Optional[int] = None,
        po_number: Optional[str] = None,
        material_doc: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        q = self._base_query(
            company_codes=company_codes,
            material_code=material_code,
            material_keyword=material_keyword,
            supplier_keyword=supplier_keyword,
            date_from=date_from,
            date_to=date_to,
            fiscal_year=fiscal_year,
            po_number=po_number,
            material_doc=material_doc,
        )

        summary_row = q.with_entities(
            func.count(PurchaseRecord.id).label("cnt"),
            func.coalesce(func.sum(PurchaseRecord.cny_amount), 0).label("total_cny"),
            func.coalesce(func.sum(PurchaseRecord.quantity), 0).label("total_qty"),
        ).one()

        total = int(summary_row.cnt or 0)
        total_pages = max(1, (total + page_size - 1) // page_size) if total else 0
        page = max(1, min(page, total_pages or 1))

        rows = (
            q.order_by(
                PurchaseRecord.transaction_date.desc().nullslast(),
                PurchaseRecord.id.desc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        return {
            "items": [self._serialize(r) for r in rows],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": total_pages,
            },
            "summary": {
                "count": total,
                "total_cny": float(summary_row.total_cny or 0),
                "total_qty": float(summary_row.total_qty or 0),
            },
        }

    def export_records(
        self,
        company_codes: Optional[List[str]] = None,
        material_code: Optional[str] = None,
        material_keyword: Optional[str] = None,
        supplier_keyword: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        fiscal_year: Optional[int] = None,
        po_number: Optional[str] = None,
        material_doc: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        q = self._base_query(
            company_codes=company_codes,
            material_code=material_code,
            material_keyword=material_keyword,
            supplier_keyword=supplier_keyword,
            date_from=date_from,
            date_to=date_to,
            fiscal_year=fiscal_year,
            po_number=po_number,
            material_doc=material_doc,
        )
        rows = (
            q.order_by(
                PurchaseRecord.transaction_date.desc().nullslast(),
                PurchaseRecord.id.desc(),
            )
            .limit(self.EXPORT_MAX_ROWS)
            .all()
        )
        return [self._serialize(r) for r in rows]
