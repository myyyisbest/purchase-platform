"""
物料单价趋势服务
提供：物料滚动12个月采购单价趋势、TOP物料排名、物料搜索
"""
from sqlalchemy import func, and_, extract, or_
from sqlalchemy.orm import Session
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional, List
from ..models import PurchaseRecord, MaterialMajorCategory


def _to_float(v):
    if v is None:
        return 0
    return float(v) if not isinstance(v, Decimal) else float(v)


class PriceTrendService:
    def __init__(self, db: Session):
        self.db = db

    def _get_latest_month(self) -> Optional[date]:
        """获取数据库中最新的交易日期所在月"""
        row = self.db.query(func.max(PurchaseRecord.transaction_date)).scalar()
        if not row:
            return None
        return row.replace(day=1)

    def _apply_major_filter(self, query, major_category: Optional[str]):
        """叠加物料大类过滤条件"""
        if not major_category:
            return query
        sub_rows = (
            self.db.query(MaterialMajorCategory.company_code, MaterialMajorCategory.material_code)
            .filter(MaterialMajorCategory.major_category == major_category)
            .all()
        )
        if not sub_rows:
            return query.filter(or_(PurchaseRecord.id.is_(None), PurchaseRecord.id == -1))
        return query.filter(
            and_(
                PurchaseRecord.company_code.in_([r[0] for r in sub_rows]),
                PurchaseRecord.material_code.in_([r[1] for r in sub_rows]),
            )
        )

    def get_material_price_trend(
        self,
        material_code: str,
        months: int = 12,
        company_codes: Optional[List[str]] = None,
        major_category: Optional[str] = None,
        end_month: Optional[str] = None,
    ) -> dict:
        """
        获取指定物料的滚动N个月采购单价趋势
        end_month: 截止月份 "YYYY-MM" 格式，为空则使用最新月份
        返回：物料基本信息 + 月度单价列表（按时间升序）
        """
        info_query = (
            self.db.query(
                PurchaseRecord.material_code,
                PurchaseRecord.material_name,
                PurchaseRecord.specification,
                PurchaseRecord.unit,
                PurchaseRecord.order_currency,
                func.sum(PurchaseRecord.cny_amount).label("total_amt"),
                func.count(PurchaseRecord.id).label("cnt"),
            )
            .filter(
                PurchaseRecord.material_code == material_code,
                PurchaseRecord.deleted_at.is_(None),
            )
        )
        if company_codes:
            info_query = info_query.filter(PurchaseRecord.company_code.in_(company_codes))
        info_query = self._apply_major_filter(info_query, major_category)
        info_row = (
            info_query
            .group_by(
                PurchaseRecord.material_code,
                PurchaseRecord.material_name,
                PurchaseRecord.specification,
                PurchaseRecord.unit,
                PurchaseRecord.order_currency,
            )
            .order_by(func.sum(PurchaseRecord.cny_amount).desc())
            .first()
        )
        if not info_row:
            return {"error": "物料不存在", "material_code": material_code, "monthly": []}

        # 确定滚动窗口
        if end_month:
            try:
                parts = end_month.split('-')
                latest = date(int(parts[0]), int(parts[1]), 1)
            except (ValueError, IndexError):
                latest = self._get_latest_month()
        else:
            latest = self._get_latest_month()
        if not latest:
            return {"error": "无数据", "material_code": material_code, "monthly": []}

        start_year = latest.year
        start_month = latest.month - months + 1
        while start_month <= 0:
            start_month += 12
            start_year -= 1
        start_date = date(start_year, start_month, 1)
        # 截止月份的下个月第一天（用于上界过滤）
        end_month_next = latest.month + 1
        end_year_next = latest.year
        if end_month_next > 12:
            end_month_next = 1
            end_year_next += 1
        end_date = date(end_year_next, end_month_next, 1)

        # 加权均价 = SUM(cny_amount) / SUM(quantity)
        # order_unit_price 在数据中全为 0，不可用，统一用 CNY 加权均价
        weighted_price = func.coalesce(
            func.sum(PurchaseRecord.cny_amount) / func.nullif(func.sum(PurchaseRecord.quantity), 0),
            0
        )
        rows_query = (
            self.db.query(
                extract("year", PurchaseRecord.transaction_date).label("yr"),
                extract("month", PurchaseRecord.transaction_date).label("mo"),
                weighted_price.label("avg_price"),
                weighted_price.label("avg_price_base"),
                func.sum(PurchaseRecord.quantity).label("qty"),
                func.sum(PurchaseRecord.cny_amount).label("amt"),
                func.count(PurchaseRecord.id).label("cnt"),
            )
            .filter(
                PurchaseRecord.material_code == material_code,
                PurchaseRecord.transaction_date >= start_date,
                PurchaseRecord.transaction_date < end_date,
                PurchaseRecord.deleted_at.is_(None),
            )
        )
        if company_codes:
            rows_query = rows_query.filter(PurchaseRecord.company_code.in_(company_codes))
        rows_query = self._apply_major_filter(rows_query, major_category)
        rows = (
            rows_query
            .group_by("yr", "mo")
            .order_by("yr", "mo")
            .all()
        )

        monthly = []
        for yr, mo, avg_p, avg_bp, qty, amt, cnt in rows:
            monthly.append({
                "year": int(yr),
                "month": int(mo),
                "label": f"{int(yr)}-{int(mo):02d}",
                "avg_order_price": round(_to_float(avg_p), 4),
                "avg_base_price": round(_to_float(avg_bp), 4),
                "quantity": round(_to_float(qty), 4),
                "amount_cny": round(_to_float(amt), 2),
                "order_count": int(cnt or 0),
            })

        return {
            "material_code": info_row.material_code,
            "material_name": info_row.material_name,
            "specification": info_row.specification or "",
            "unit": info_row.unit or "",
            "order_currency": info_row.order_currency or "",
            "total_amount_cny": round(_to_float(info_row.total_amt), 2),
            "total_orders": int(info_row.cnt or 0),
            "monthly": monthly,
        }

    def get_top_materials_for_trend(
        self,
        limit: int = 20,
        company_codes: Optional[List[str]] = None,
        major_category: Optional[str] = None,
        end_month: Optional[str] = None,
    ) -> List[str]:
        """
        按最近13个月采购金额(CNY)排名，返回TOP N物料的 material_code 列表
        """
        if end_month:
            try:
                parts = end_month.split('-')
                latest = date(int(parts[0]), int(parts[1]), 1)
            except (ValueError, IndexError):
                latest = self._get_latest_month()
        else:
            latest = self._get_latest_month()
        if not latest:
            return []

        start_year = latest.year
        start_month = latest.month - 12
        while start_month <= 0:
            start_month += 12
            start_year -= 1
        start_date = date(start_year, start_month, 1)
        # 截止月份的下个月第一天
        end_month_next = latest.month + 1
        end_year_next = latest.year
        if end_month_next > 12:
            end_month_next = 1
            end_year_next += 1
        end_date = date(end_year_next, end_month_next, 1)

        query = (
            self.db.query(
                PurchaseRecord.material_code,
                func.sum(PurchaseRecord.cny_amount).label("amt"),
            )
            .filter(
                PurchaseRecord.transaction_date >= start_date,
                PurchaseRecord.transaction_date < end_date,
                PurchaseRecord.deleted_at.is_(None),
            )
        )
        if company_codes:
            query = query.filter(PurchaseRecord.company_code.in_(company_codes))
        query = self._apply_major_filter(query, major_category)
        rows = (
            query
            .group_by(PurchaseRecord.material_code)
            .order_by(func.sum(PurchaseRecord.cny_amount).desc())
            .limit(limit)
            .all()
        )
        return [r[0] for r in rows]

    def search_materials(
        self,
        keyword: str,
        limit: int = 20,
        company_codes: Optional[List[str]] = None,
        major_category: Optional[str] = None,
    ) -> list:
        """
        按物料编码或名称模糊搜索，返回去重列表
        """
        pattern = f"%{keyword}%"
        query = (
            self.db.query(
                PurchaseRecord.material_code,
                func.max(PurchaseRecord.material_name).label("name"),
                func.max(PurchaseRecord.specification).label("spec"),
                func.sum(PurchaseRecord.cny_amount).label("amt"),
            )
            .filter(
                (PurchaseRecord.material_code.ilike(pattern))
                | (PurchaseRecord.material_name.ilike(pattern)),
                PurchaseRecord.deleted_at.is_(None),
            )
        )
        if company_codes:
            query = query.filter(PurchaseRecord.company_code.in_(company_codes))
        query = self._apply_major_filter(query, major_category)
        rows = (
            query
            .group_by(PurchaseRecord.material_code)
            .order_by(func.sum(PurchaseRecord.cny_amount).desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "material_code": r[0],
                "material_name": r[1] or "",
                "specification": r[2] or "",
                "total_amount_cny": round(_to_float(r[3]), 2),
            }
            for r in rows
        ]
