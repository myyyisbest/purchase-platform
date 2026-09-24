"""
采购记录明细查询 API
鉴权：登录用户；公司范围走 user_company_access（与看板/趋势一致）
"""
from datetime import date
from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..auth import get_current_user, get_effective_company_codes
from ..services.purchase_record_service import PurchaseRecordService
from ..services.export_service import ExportService

router = APIRouter()


def _resolve_codes(
    current_user: User,
    company_codes: Optional[List[str]],
    db: Session,
) -> Optional[List[str]]:
    return get_effective_company_codes(current_user, company_codes, db)


@router.get("/list")
def list_purchase_records(
    company_codes: Optional[List[str]] = Query(None, description="公司代码列表"),
    material_code: Optional[str] = Query(None, description="物料编码（精确）"),
    material_keyword: Optional[str] = Query(None, description="物料编码/名称模糊"),
    supplier_keyword: Optional[str] = Query(None, description="供应商编码/名称模糊"),
    date_from: Optional[date] = Query(None, description="交易日起（含）"),
    date_to: Optional[date] = Query(None, description="交易日止（含）"),
    fiscal_year: Optional[int] = Query(None, description="财年"),
    po_number: Optional[str] = Query(None, description="采购订单号（模糊）"),
    material_doc: Optional[str] = Query(None, description="物料凭证（模糊）"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=10, le=200, description="每页条数"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """分页查询采购记录明细"""
    effective = _resolve_codes(current_user, company_codes, db)
    result = PurchaseRecordService(db).list_records(
        company_codes=effective,
        material_code=material_code,
        material_keyword=material_keyword,
        supplier_keyword=supplier_keyword,
        date_from=date_from,
        date_to=date_to,
        fiscal_year=fiscal_year,
        po_number=po_number,
        material_doc=material_doc,
        page=page,
        page_size=page_size,
    )
    return {"code": 200, "data": result}


@router.get("/export")
def export_purchase_records(
    company_codes: Optional[List[str]] = Query(None, description="公司代码列表"),
    material_code: Optional[str] = Query(None, description="物料编码（精确）"),
    material_keyword: Optional[str] = Query(None, description="物料编码/名称模糊"),
    supplier_keyword: Optional[str] = Query(None, description="供应商编码/名称模糊"),
    date_from: Optional[date] = Query(None, description="交易日起（含）"),
    date_to: Optional[date] = Query(None, description="交易日止（含）"),
    fiscal_year: Optional[int] = Query(None, description="财年"),
    po_number: Optional[str] = Query(None, description="采购订单号（模糊）"),
    material_doc: Optional[str] = Query(None, description="物料凭证（模糊）"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """导出当前过滤条件下的采购记录为 Excel（最多 5 万行）"""
    effective = _resolve_codes(current_user, company_codes, db)
    items = PurchaseRecordService(db).export_records(
        company_codes=effective,
        material_code=material_code,
        material_keyword=material_keyword,
        supplier_keyword=supplier_keyword,
        date_from=date_from,
        date_to=date_to,
        fiscal_year=fiscal_year,
        po_number=po_number,
        material_doc=material_doc,
    )
    return ExportService().generate_purchase_records_excel(items)
