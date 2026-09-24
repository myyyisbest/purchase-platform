"""
异常预警 API
GET  /list /summary
POST /scan (admin)
POST /{id}/acknowledge
POST /{id}/resolve
"""
from typing import Optional, List

from fastapi import APIRouter, Query, HTTPException

from ..dependencies import FiscalYear, CompanyCodes, CurrentUser, DbSession
from ..auth import get_effective_company_codes, require_admin
from ..models import User
from fastapi import Depends
from ..services.anomaly_alert_service import AnomalyAlertService

router = APIRouter()


def _ok(data=None, message="成功"):
    return {"code": 200, "message": message, "data": data}


@router.get("/list", summary="预警列表")
def list_alerts(
    status: Optional[str] = Query(None, description="open|acknowledged|resolved"),
    alert_type: Optional[str] = Query(None, description="single_source|price_volatility"),
    fiscal_year: FiscalYear = None,
    keyword: Optional[str] = Query(None),
    company_codes: CompanyCodes = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    current_user: CurrentUser = None,
    db: DbSession = None,
):
    effective = get_effective_company_codes(current_user, company_codes, db)
    items, total = AnomalyAlertService(db).list_alerts(
        status=status,
        alert_type=alert_type,
        fiscal_year=fiscal_year,
        keyword=keyword,
        company_codes=effective,
        page=page,
        page_size=page_size,
    )
    return _ok({
        "items": [AnomalyAlertService.to_dict(i) for i in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    })


@router.get("/summary", summary="预警状态汇总（角标）")
def alert_summary(
    fiscal_year: FiscalYear = None,
    company_codes: CompanyCodes = None,
    current_user: CurrentUser = None,
    db: DbSession = None,
):
    effective = get_effective_company_codes(current_user, company_codes, db)
    return _ok(AnomalyAlertService(db).get_summary(fiscal_year=fiscal_year, company_codes=effective))


@router.post("/scan", summary="重新扫描预警（管理员）")
def scan_alerts(
    fiscal_year: int = Query(..., description="财年"),
    company_codes: CompanyCodes = None,
    volatility_threshold: float = Query(20.0, ge=1, le=200),
    force_rescan: bool = Query(False, description="强制重开已确认/已关闭预警"),
    _: User = Depends(require_admin),
    db: DbSession = None,
):
    stats = AnomalyAlertService(db).scan_and_upsert(
        fiscal_year=fiscal_year,
        company_codes=company_codes,
        volatility_threshold=volatility_threshold,
        force_rescan=force_rescan,
    )
    return _ok(stats, message="扫描完成")


@router.post("/{alert_id}/acknowledge", summary="确认预警")
def acknowledge_alert(
    alert_id: int,
    current_user: CurrentUser = None,
    db: DbSession = None,
):
    alert = AnomalyAlertService(db).acknowledge(alert_id, current_user.username)
    if not alert:
        raise HTTPException(404, "预警不存在")
    return _ok(AnomalyAlertService.to_dict(alert), message="已确认")


@router.post("/{alert_id}/resolve", summary="关闭预警")
def resolve_alert(
    alert_id: int,
    current_user: CurrentUser = None,
    db: DbSession = None,
):
    alert = AnomalyAlertService(db).resolve(alert_id, current_user.username)
    if not alert:
        raise HTTPException(404, "预警不存在")
    return _ok(AnomalyAlertService.to_dict(alert), message="已关闭")
