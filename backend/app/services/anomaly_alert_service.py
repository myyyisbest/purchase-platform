"""
异常预警服务
扫描单源供应风险 / 单价波动，写入 anomaly_alerts 并支持确认、关闭、汇总。
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Optional, List, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import or_, func

from ..models import AnomalyAlert, PurchaseRecord
from ..auth import CST
from .dashboard_service import DashboardService


def _fingerprint(alert_type: str, year: int, material: str, currency: Optional[str] = None) -> str:
    return f"{alert_type}:{year}:{material}:{currency or ''}"


def _severity(metric: float, threshold: float, alert_type: str) -> str:
    if alert_type == "single_source":
        # metric = amount_cny；金额越高风险越高
        if metric >= 1_000_000:
            return "high"
        if metric >= 100_000:
            return "medium"
        return "low"
    # price_volatility: metric = abs(change_rate)
    if metric >= threshold * 2:
        return "high"
    if metric >= threshold:
        return "medium"
    return "low"


class AnomalyAlertService:
    def __init__(self, db: Session):
        self.db = db

    def scan_and_upsert(
        self,
        fiscal_year: int,
        company_codes: Optional[List[str]] = None,
        volatility_threshold: float = 20.0,
        force_rescan: bool = False,
    ) -> dict:
        """
        扫描并 upsert 预警。
        - 已存在且 status=open：更新指标
        - 已存在且 acknowledged/resolved：默认跳过；force_rescan=True 时重新打开并更新
        """
        dash = DashboardService(self.db)
        created = updated = skipped = 0

        # ---- 单源供应 ----
        single_items = dash.get_single_source_risk(
            fiscal_year=fiscal_year,
            company_codes=company_codes,
            limit=200,
        )
        for item in single_items:
            fp = _fingerprint("single_source", fiscal_year, item["material_code"])
            metric = float(item.get("amount_cny") or 0)
            title = f"单源供应风险：{item.get('material_name') or item['material_code']}"
            detail = json.dumps(item, ensure_ascii=False)
            company_scope = json.dumps(company_codes or [], ensure_ascii=False)
            result = self._upsert_one(
                fingerprint=fp,
                alert_type="single_source",
                fiscal_year=fiscal_year,
                material_code=item["material_code"],
                material_name=item.get("material_name") or "",
                supplier_name=item.get("supplier_name"),
                currency=None,
                company_scope=company_scope,
                metric_value=metric,
                threshold=1.0,  # 供应商数=1 即触发
                severity=_severity(metric, 1.0, "single_source"),
                title=title,
                detail=detail,
                force_rescan=force_rescan,
            )
            if result == "created":
                created += 1
            elif result == "updated":
                updated += 1
            else:
                skipped += 1

        # ---- 单价波动 ----
        vol_items = dash.get_price_volatility(
            fiscal_year=fiscal_year,
            limit=200,
            company_codes=company_codes,
        )
        for item in vol_items:
            change = abs(float(item.get("change_rate") or 0))
            if change < volatility_threshold:
                continue
            fp = _fingerprint(
                "price_volatility",
                fiscal_year,
                item["material_code"],
                item.get("currency"),
            )
            title = (
                f"单价波动 {change:.1f}%：{item.get('material_name') or item['material_code']}"
                f"（{item.get('currency') or '-'}）"
            )
            detail = json.dumps(item, ensure_ascii=False)
            company_scope = json.dumps(company_codes or [], ensure_ascii=False)
            result = self._upsert_one(
                fingerprint=fp,
                alert_type="price_volatility",
                fiscal_year=fiscal_year,
                material_code=item["material_code"],
                material_name=item.get("material_name") or "",
                supplier_name=None,
                currency=item.get("currency"),
                company_scope=company_scope,
                metric_value=change,
                threshold=volatility_threshold,
                severity=_severity(change, volatility_threshold, "price_volatility"),
                title=title,
                detail=detail,
                force_rescan=force_rescan,
            )
            if result == "created":
                created += 1
            elif result == "updated":
                updated += 1
            else:
                skipped += 1

        self.db.commit()
        return {
            "fiscal_year": fiscal_year,
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "volatility_threshold": volatility_threshold,
        }

    def _upsert_one(
        self,
        *,
        fingerprint: str,
        alert_type: str,
        fiscal_year: int,
        material_code: str,
        material_name: str,
        supplier_name: Optional[str],
        currency: Optional[str],
        company_scope: Optional[str],
        metric_value: float,
        threshold: float,
        severity: str,
        title: str,
        detail: str,
        force_rescan: bool,
    ) -> str:
        existing: Optional[AnomalyAlert] = (
            self.db.query(AnomalyAlert)
            .filter(AnomalyAlert.fingerprint == fingerprint)
            .first()
        )
        now = datetime.now(CST).replace(tzinfo=None)

        if existing is None:
            alert = AnomalyAlert(
                alert_type=alert_type,
                fiscal_year=fiscal_year,
                material_code=material_code,
                material_name=material_name,
                supplier_name=supplier_name,
                currency=currency,
                company_scope=company_scope,
                metric_value=metric_value,
                threshold=threshold,
                severity=severity,
                status="open",
                title=title,
                detail=detail,
                fingerprint=fingerprint,
                created_at=now,
                updated_at=now,
            )
            self.db.add(alert)
            return "created"

        if existing.status != "open" and not force_rescan:
            return "skipped"

        existing.material_name = material_name
        existing.supplier_name = supplier_name
        existing.currency = currency
        existing.company_scope = company_scope
        existing.metric_value = metric_value
        existing.threshold = threshold
        existing.severity = severity
        existing.title = title
        existing.detail = detail
        existing.updated_at = now
        if force_rescan and existing.status != "open":
            existing.status = "open"
            existing.acknowledged_by = None
            existing.acknowledged_at = None
            existing.resolved_at = None
        return "updated"

    def list_alerts(
        self,
        *,
        status: Optional[str] = None,
        alert_type: Optional[str] = None,
        fiscal_year: Optional[int] = None,
        keyword: Optional[str] = None,
        company_codes: Optional[List[str]] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[list, int]:
        q = self.db.query(AnomalyAlert)
        if status:
            q = q.filter(AnomalyAlert.status == status)
        if alert_type:
            q = q.filter(AnomalyAlert.alert_type == alert_type)
        if fiscal_year:
            q = q.filter(AnomalyAlert.fiscal_year == fiscal_year)
        if keyword:
            pattern = f"%{keyword}%"
            q = q.filter(
                or_(
                    AnomalyAlert.material_code.ilike(pattern),
                    AnomalyAlert.material_name.ilike(pattern),
                    AnomalyAlert.supplier_name.ilike(pattern),
                    AnomalyAlert.title.ilike(pattern),
                )
            )
        # 公司范围过滤：若用户有公司限制，则要求 alert 关联物料在其公司采购记录中出现过
        if company_codes:
            material_subq = (
                self.db.query(PurchaseRecord.material_code)
                .filter(
                    PurchaseRecord.deleted_at.is_(None),
                    PurchaseRecord.company_code.in_(company_codes),
                )
                .distinct()
                .subquery()
            )
            q = q.filter(AnomalyAlert.material_code.in_(material_subq))

        total = q.count()
        items = (
            q.order_by(AnomalyAlert.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def get_summary(
        self,
        fiscal_year: Optional[int] = None,
        company_codes: Optional[List[str]] = None,
    ) -> dict:
        q = self.db.query(AnomalyAlert.status, func.count(AnomalyAlert.id))
        if fiscal_year:
            q = q.filter(AnomalyAlert.fiscal_year == fiscal_year)
        if company_codes:
            material_subq = (
                self.db.query(PurchaseRecord.material_code)
                .filter(
                    PurchaseRecord.deleted_at.is_(None),
                    PurchaseRecord.company_code.in_(company_codes),
                )
                .distinct()
                .subquery()
            )
            q = q.filter(AnomalyAlert.material_code.in_(material_subq))
        rows = q.group_by(AnomalyAlert.status).all()
        counts = {s: c for s, c in rows}
        return {
            "open": counts.get("open", 0),
            "acknowledged": counts.get("acknowledged", 0),
            "resolved": counts.get("resolved", 0),
            "total": sum(counts.values()),
        }

    def acknowledge(self, alert_id: int, username: str) -> Optional[AnomalyAlert]:
        alert = self.db.query(AnomalyAlert).filter(AnomalyAlert.id == alert_id).first()
        if not alert:
            return None
        now = datetime.now(CST).replace(tzinfo=None)
        alert.status = "acknowledged"
        alert.acknowledged_by = username
        alert.acknowledged_at = now
        alert.updated_at = now
        self.db.commit()
        self.db.refresh(alert)
        return alert

    def resolve(self, alert_id: int, username: str) -> Optional[AnomalyAlert]:
        alert = self.db.query(AnomalyAlert).filter(AnomalyAlert.id == alert_id).first()
        if not alert:
            return None
        now = datetime.now(CST).replace(tzinfo=None)
        alert.status = "resolved"
        if not alert.acknowledged_by:
            alert.acknowledged_by = username
            alert.acknowledged_at = now
        alert.resolved_at = now
        alert.updated_at = now
        self.db.commit()
        self.db.refresh(alert)
        return alert

    @staticmethod
    def to_dict(alert: AnomalyAlert) -> dict:
        return {
            "id": alert.id,
            "alert_type": alert.alert_type,
            "fiscal_year": alert.fiscal_year,
            "material_code": alert.material_code,
            "material_name": alert.material_name,
            "supplier_name": alert.supplier_name,
            "currency": alert.currency,
            "company_scope": alert.company_scope,
            "metric_value": alert.metric_value,
            "threshold": alert.threshold,
            "severity": alert.severity,
            "status": alert.status,
            "title": alert.title,
            "detail": alert.detail,
            "fingerprint": alert.fingerprint,
            "acknowledged_by": alert.acknowledged_by,
            "acknowledged_at": alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
            "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
            "created_at": alert.created_at.isoformat() if alert.created_at else None,
            "updated_at": alert.updated_at.isoformat() if alert.updated_at else None,
        }
