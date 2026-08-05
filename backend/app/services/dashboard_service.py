"""
采购分析面板 Dashboard 服务

提供 8 大分析视图的 API 数据：
1. KPI 关键指标（采购总额、笔数、物料数、供应商数、单价波动率等）
2. 月度趋势（金额 + 笔数 + 单价）
3. 季度分布
4. 公司对比
5. 供应商 TOP 榜
6. 物料 TOP 榜（按金额、单价波动）
7. 物料类别分布（环形图）
8. 物料大类分布（来自 material_major_categories 维护表）
9. 单价异常波动（按月同比 + 环比）
10. 公司 × 月度 热力图
11. 事业部 / 板块 分布
"""
from sqlalchemy import func, and_, or_, case, extract
from sqlalchemy.orm import Session
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List
import calendar

from ..models import (
    PurchaseRecord, Supplier, Material, ExchangeRate, Company,
    BusinessSector, BusinessUnit, Group, MaterialMajorCategory,
)


def _to_float(v):
    """Decimal/float → float 转换"""
    if v is None:
        return 0
    if isinstance(v, Decimal):
        return float(v)
    return float(v)


class DashboardService:
    """Dashboard 数据服务"""

    def __init__(self, db: Session):
        self.db = db

    # ==================== 公共筛选条件 ====================
    def _base_filter(
        self,
        fiscal_year: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        company_name: Optional[str] = None,
        company_codes: Optional[list] = None,
        material_code: Optional[str] = None,
        material_keyword: Optional[str] = None,
        material_category: Optional[str] = None,
        major_category: Optional[str] = None,
    ):
        """构造基础查询过滤条件"""
        conditions = []
        # 软删除过滤：始终排除已冲销/已删除的记录（HANA 端真删/冲销会置 deleted_at）
        conditions.append(PurchaseRecord.deleted_at.is_(None))
        if fiscal_year:
            conditions.append(PurchaseRecord.fiscal_year == fiscal_year)
        if start_date:
            conditions.append(PurchaseRecord.transaction_date >= start_date)
        if end_date:
            conditions.append(PurchaseRecord.transaction_date <= end_date)
        if company_name:
            conditions.append(PurchaseRecord.company_name == company_name)
        if company_codes:
            conditions.append(PurchaseRecord.company_code.in_(company_codes))
        if material_code:
            conditions.append(PurchaseRecord.material_code == material_code)
        if material_keyword:
            pattern = f"%{material_keyword}%"
            conditions.append(
                or_(
                    PurchaseRecord.material_code.ilike(pattern),
                    PurchaseRecord.material_name.ilike(pattern),
                )
            )
        if material_category:
            conditions.append(PurchaseRecord.material_category == material_category)
        if major_category:
            # 通过维护表过滤：只有 (company_code, material_code) 落在该 major_category 下的采购记录才纳入
            sub_q = self.db.query(MaterialMajorCategory.company_code, MaterialMajorCategory.material_code).filter(
                MaterialMajorCategory.major_category == major_category
            )
            sub_rows = sub_q.all()
            if not sub_rows:
                # 没有任何维护记录时，返回空（用 1=0 强制为空）
                conditions.append(or_(PurchaseRecord.id.is_(None), PurchaseRecord.id == -1))
            else:
                # 用 EXISTS 子查询避免笛卡尔积爆炸
                conditions.append(
                    and_(
                        PurchaseRecord.company_code.in_([r[0] for r in sub_rows]),
                        PurchaseRecord.material_code.in_([r[1] for r in sub_rows]),
                    )
                )
        return and_(*conditions) if conditions else None

    # ==================== 1. KPI 关键指标 ====================
    def get_kpis(
        self,
        fiscal_year: Optional[int] = None,
        company_name: Optional[str] = None,
        company_codes: Optional[list] = None,
        material_code: Optional[str] = None,
        material_keyword: Optional[str] = None,
        major_category: Optional[str] = None,
    ) -> dict:
        """KPI 指标卡：总金额、笔数、物料数、供应商数、单笔均价、平均单价、币种分布"""
        cond = self._base_filter(
            fiscal_year=fiscal_year,
            company_name=company_name,
            company_codes=company_codes,
            material_code=material_code,
            material_keyword=material_keyword,
            major_category=major_category,
        )
        q = self.db.query(
            func.coalesce(func.sum(PurchaseRecord.cny_amount), 0).label('total'),
            func.count(PurchaseRecord.id).label('cnt'),
            func.count(func.distinct(PurchaseRecord.material_code)).label('mat_cnt'),
            func.count(func.distinct(PurchaseRecord.supplier_code)).label('sup_cnt'),
            func.count(func.distinct(PurchaseRecord.company_name)).label('comp_cnt'),
            func.count(func.distinct(PurchaseRecord.order_currency)).label('cur_cnt'),
            func.min(PurchaseRecord.transaction_date).label('min_date'),
            func.max(PurchaseRecord.transaction_date).label('max_date'),
        )
        if cond is not None:
            q = q.filter(cond)
        row = q.first()

        # 数据范围：实际覆盖的月份
        date_range = None
        if row.min_date and row.max_date:
            date_range = {
                "start": row.min_date.isoformat(),
                "end": row.max_date.isoformat(),
                "months_covered": (row.max_date.year - row.min_date.year) * 12 + row.max_date.month - row.min_date.month + 1
            }

        # 同比：当前年度 vs 上一年度的金额（仅当上一年数据完整时）
        yoy_data = None
        if fiscal_year and date_range:
            prev_year = fiscal_year - 1
            prev_cond = self._base_filter(
                fiscal_year=prev_year,
                company_name=company_name,
                company_codes=company_codes,
                material_code=material_code,
                material_keyword=material_keyword,
                major_category=major_category,
            )
            prev_q = self.db.query(
                func.coalesce(func.sum(PurchaseRecord.cny_amount), 0),
                func.min(PurchaseRecord.transaction_date),
                func.max(PurchaseRecord.transaction_date)
            )
            if prev_cond is not None:
                prev_q = prev_q.filter(prev_cond)
            prev_total, prev_min, prev_max = prev_q.first()
            prev_total = _to_float(prev_total)
            curr_total = _to_float(row.total)
            if prev_total > 0:
                is_full_year = date_range['months_covered'] >= 12
                yoy_rate = (curr_total - prev_total) / prev_total * 100
                yoy_data = {
                    "current_total": round(curr_total, 2),
                    "previous_total": round(prev_total, 2),
                    "yoy_rate": round(yoy_rate, 2),
                    "is_full_year": is_full_year,
                    "warning": "" if is_full_year else f"仅对比{date_range['months_covered']}个月数据"
                }

        # 币种分布
        cur_q = self.db.query(
            PurchaseRecord.order_currency,
            func.coalesce(func.sum(PurchaseRecord.cny_amount), 0).label('amt')
        )
        if cond is not None:
            cur_q = cur_q.filter(cond)
        cur_q = cur_q.group_by(PurchaseRecord.order_currency).order_by(func.sum(PurchaseRecord.cny_amount).desc())
        currency_dist = [
            {"currency": c or "未指定", "amount_cny": round(_to_float(a), 2)}
            for c, a in cur_q.all()
        ]

        total = _to_float(row.total)
        cnt = int(row.cnt or 0)
        avg_per_order = total / cnt if cnt > 0 else 0

        return {
            "fiscal_year": fiscal_year,
            "total_cny": round(total, 2),
            "order_count": cnt,
            "material_count": int(row.mat_cnt or 0),
            "supplier_count": int(row.sup_cnt or 0),
            "company_count": int(row.comp_cnt or 0),
            "currency_count": int(row.cur_cnt or 0),
            "avg_per_order": round(avg_per_order, 2),
            "yoy": yoy_data,
            "date_range": date_range,
            "currency_distribution": currency_dist,
        }

    # ==================== 2. 月度趋势 ====================
    def get_monthly_trend(
        self,
        fiscal_year: Optional[int] = None,
        company_name: Optional[str] = None,
        company_codes: Optional[list] = None,
        material_code: Optional[str] = None,
        material_keyword: Optional[str] = None,
        major_category: Optional[str] = None,
    ) -> list:
        """月度采购趋势：金额 + 笔数 + 平均单价"""
        cond = self._base_filter(
            fiscal_year=fiscal_year, company_name=company_name, company_codes=company_codes,
            material_code=material_code, material_keyword=material_keyword, major_category=major_category,
        )
        month_col = extract('month', PurchaseRecord.transaction_date)
        q = self.db.query(
            month_col.label('month'),
            func.coalesce(func.sum(PurchaseRecord.cny_amount), 0).label('amt'),
            func.count(PurchaseRecord.id).label('cnt'),
            func.coalesce(func.avg(PurchaseRecord.cny_amount), 0).label('avg_amt'),
            func.coalesce(func.avg(PurchaseRecord.unit_price), 0).label('avg_unit_price'),
        )
        if cond is not None:
            q = q.filter(cond)
        q = q.group_by(month_col).order_by(month_col)

        result = []
        for m, amt, cnt, avg_a, avg_p in q.all():
            result.append({
                "month": int(m),
                "month_name": f"{int(m)}月",
                "amount_cny": round(_to_float(amt), 2),
                "order_count": int(cnt or 0),
                "avg_order_amount": round(_to_float(avg_a), 2),
                "avg_unit_price": round(_to_float(avg_p), 4),
            })
        return result

    # ==================== 3. 季度分布 ====================
    def get_quarterly_distribution(
        self,
        fiscal_year: Optional[int] = None,
        company_name: Optional[str] = None,
        company_codes: Optional[list] = None,
        material_code: Optional[str] = None,
        material_keyword: Optional[str] = None,
        major_category: Optional[str] = None,
    ) -> list:
        """季度采购分布"""
        cond = self._base_filter(
            fiscal_year=fiscal_year, company_name=company_name, company_codes=company_codes,
            material_code=material_code, material_keyword=material_keyword, major_category=major_category,
        )
        month_col = extract('month', PurchaseRecord.transaction_date)
        quarter_expr = func.ceil(month_col / 3.0).label('quarter')

        q = self.db.query(
            quarter_expr,
            func.coalesce(func.sum(PurchaseRecord.cny_amount), 0).label('amt'),
            func.count(PurchaseRecord.id).label('cnt'),
        )
        if cond is not None:
            q = q.filter(cond)
        q = q.group_by(quarter_expr).order_by(quarter_expr)

        result = []
        for q_, amt, cnt in q.all():
            result.append({
                "quarter": int(q_),
                "quarter_name": f"Q{int(q_)}",
                "amount_cny": round(_to_float(amt), 2),
                "order_count": int(cnt or 0),
            })
        return result

    # ==================== 4. 公司对比 ====================
    def get_company_comparison(
        self,
        fiscal_year: Optional[int] = None,
        company_name: Optional[str] = None,
        company_codes: Optional[list] = None,
        material_code: Optional[str] = None,
        material_keyword: Optional[str] = None,
        major_category: Optional[str] = None,
    ) -> list:
        """各公司采购对比"""
        cond = self._base_filter(
            fiscal_year=fiscal_year, company_name=company_name, company_codes=company_codes,
            material_code=material_code, material_keyword=material_keyword, major_category=major_category,
        )
        q = self.db.query(
            PurchaseRecord.company_code,
            PurchaseRecord.company_name,
            func.coalesce(func.sum(PurchaseRecord.cny_amount), 0).label('amt'),
            func.count(PurchaseRecord.id).label('cnt'),
            func.count(func.distinct(PurchaseRecord.material_code)).label('mat_cnt'),
            func.count(func.distinct(PurchaseRecord.supplier_code)).label('sup_cnt'),
        )
        if cond is not None:
            q = q.filter(cond)
        q = q.group_by(
            PurchaseRecord.company_code,
            PurchaseRecord.company_name
        ).order_by(func.sum(PurchaseRecord.cny_amount).desc())

        return [
            {
                "company_code": c,
                "company_name": n,
                "amount_cny": round(_to_float(a), 2),
                "order_count": int(cnt or 0),
                "material_count": int(mc or 0),
                "supplier_count": int(sc or 0),
            }
            for c, n, a, cnt, mc, sc in q.all()
        ]

    # ==================== 5. 供应商 TOP 榜 ====================
    def get_top_suppliers(
        self,
        fiscal_year: Optional[int] = None,
        limit: int = 20,
        company_name: Optional[str] = None,
        company_codes: Optional[list] = None,
        material_code: Optional[str] = None,
        material_keyword: Optional[str] = None,
        major_category: Optional[str] = None,
    ) -> list:
        """供应商 TOP榜：按采购金额排序"""
        cond = self._base_filter(
            fiscal_year=fiscal_year, company_name=company_name, company_codes=company_codes,
            material_code=material_code, material_keyword=material_keyword, major_category=major_category,
        )
        q = self.db.query(
            PurchaseRecord.supplier_code,
            PurchaseRecord.supplier_name,
            func.coalesce(func.sum(PurchaseRecord.cny_amount), 0).label('amt'),
            func.count(PurchaseRecord.id).label('cnt'),
            func.count(func.distinct(PurchaseRecord.material_code)).label('mat_cnt'),
            func.count(func.distinct(PurchaseRecord.company_name)).label('co_cnt'),
        )
        if cond is not None:
            q = q.filter(cond)
        q = q.group_by(
            PurchaseRecord.supplier_code,
            PurchaseRecord.supplier_name
        ).order_by(func.sum(PurchaseRecord.cny_amount).desc()).limit(limit)

        return [
            {
                "supplier_code": c,
                "supplier_name": n,
                "amount_cny": round(_to_float(a), 2),
                "order_count": int(cnt or 0),
                "material_count": int(mc or 0),
                "company_count": int(co or 0),
            }
            for c, n, a, cnt, mc, co in q.all()
        ]

    # ==================== 6. 物料 TOP 榜 ====================
    def get_top_materials(
        self,
        fiscal_year: Optional[int] = None,
        limit: int = 20,
        company_name: Optional[str] = None,
        company_codes: Optional[list] = None,
        material_code: Optional[str] = None,
        material_keyword: Optional[str] = None,
        major_category: Optional[str] = None,
    ) -> list:
        """物料 TOP榜：按采购金额排序"""
        cond = self._base_filter(
            fiscal_year=fiscal_year, company_name=company_name, company_codes=company_codes,
            material_code=material_code, material_keyword=material_keyword, major_category=major_category,
        )
        q = self.db.query(
            PurchaseRecord.material_code,
            PurchaseRecord.material_name,
            PurchaseRecord.specification,
            PurchaseRecord.material_category,
            func.coalesce(func.sum(PurchaseRecord.cny_amount), 0).label('amt'),
            func.count(PurchaseRecord.id).label('cnt'),
            func.coalesce(func.sum(PurchaseRecord.quantity), 0).label('qty'),
            func.coalesce(func.avg(PurchaseRecord.unit_price), 0).label('avg_price'),
            func.count(func.distinct(PurchaseRecord.supplier_code)).label('sup_cnt'),
        )
        if cond is not None:
            q = q.filter(cond)
        q = q.group_by(
            PurchaseRecord.material_code,
            PurchaseRecord.material_name,
            PurchaseRecord.specification,
            PurchaseRecord.material_category,
        ).order_by(func.sum(PurchaseRecord.cny_amount).desc()).limit(limit)

        return [
            {
                "material_code": c,
                "material_name": n,
                "specification": spec or "",
                "category": cat or "未分类",
                "amount_cny": round(_to_float(a), 2),
                "order_count": int(cnt or 0),
                "quantity": round(_to_float(qty), 4),
                "avg_unit_price": round(_to_float(ap), 4),
                "supplier_count": int(sc or 0),
            }
            for c, n, spec, cat, a, cnt, qty, ap, sc in q.all()
        ]

    # ==================== 7. 物料类别分布 ====================
    def get_category_distribution(
        self,
        fiscal_year: Optional[int] = None,
        company_name: Optional[str] = None,
        company_codes: Optional[list] = None,
        material_code: Optional[str] = None,
        material_keyword: Optional[str] = None,
        major_category: Optional[str] = None,
    ) -> list:
        """物料类别采购金额分布（优先使用 WGBEZ 中文描述，回退到 MATL_GROUP 编码）"""
        cond = self._base_filter(
            fiscal_year=fiscal_year, company_name=company_name, company_codes=company_codes,
            material_code=material_code, material_keyword=material_keyword, major_category=major_category,
        )
        # WGBEZ 有中文描述时优先使用，否则回退到 material_category（SAP 物料组编码）
        cat_label = case(
            (func.coalesce(PurchaseRecord.wgbez, '') != '', PurchaseRecord.wgbez),
            else_=func.coalesce(PurchaseRecord.material_category, '未分类')
        )
        q = self.db.query(
            cat_label.label('cat'),
            func.coalesce(func.sum(PurchaseRecord.cny_amount), 0).label('amt'),
            func.count(PurchaseRecord.id).label('cnt'),
            func.count(func.distinct(PurchaseRecord.material_code)).label('mat_cnt'),
        )
        if cond is not None:
            q = q.filter(cond)
        q = q.group_by('cat').order_by(func.sum(PurchaseRecord.cny_amount).desc())

        return [
            {
                "category": c,
                "amount_cny": round(_to_float(a), 2),
                "order_count": int(cnt or 0),
                "material_count": int(mc or 0),
            }
            for c, a, cnt, mc in q.all()
        ]

    # ==================== 7b. 物料大类分布 ====================
    def get_major_category_distribution(
        self,
        fiscal_year: Optional[int] = None,
        company_name: Optional[str] = None,
        company_codes: Optional[list] = None,
        material_code: Optional[str] = None,
        material_keyword: Optional[str] = None,
        major_category: Optional[str] = None,
    ) -> list:
        """物料大类分布：来自 material_major_categories 维护表

        取每条采购记录对应的物料大类（公司+物料编码），按大类汇总金额
        如果用户已经选了 major_category，则只返回该类的金额
        """
        cond = self._base_filter(
            fiscal_year=fiscal_year, company_name=company_name, company_codes=company_codes,
            material_code=material_code, material_keyword=material_keyword, major_category=major_category,
        )

        # 用 JOIN + GROUP BY 一次取出（公司编码+物料编码 对应的大类）
        major_col = func.coalesce(MaterialMajorCategory.major_category, '未维护').label('major')
        q = (
            self.db.query(
                major_col,
                func.coalesce(func.sum(PurchaseRecord.cny_amount), 0).label('amt'),
                func.count(PurchaseRecord.id).label('cnt'),
                func.count(func.distinct(PurchaseRecord.material_code)).label('mat_cnt'),
            )
            .outerjoin(
                MaterialMajorCategory,
                (PurchaseRecord.company_code == MaterialMajorCategory.company_code)
                & (PurchaseRecord.material_code == MaterialMajorCategory.material_code),
            )
        )
        if cond is not None:
            q = q.filter(cond)
        q = q.group_by('major').order_by(func.sum(PurchaseRecord.cny_amount).desc())

        return [
            {
                "major_category": m,
                "amount_cny": round(_to_float(a), 2),
                "order_count": int(cnt or 0),
                "material_count": int(mc or 0),
            }
            for m, a, cnt, mc in q.all()
        ]

    # ==================== 8. 采购用途分布 ====================
    def get_purpose_distribution(
        self,
        fiscal_year: Optional[int] = None,
        company_name: Optional[str] = None,
        company_codes: Optional[list] = None,
        material_code: Optional[str] = None,
        material_keyword: Optional[str] = None,
        major_category: Optional[str] = None,
    ) -> list:
        """采购用途分布"""
        cond = self._base_filter(
            fiscal_year=fiscal_year, company_name=company_name, company_codes=company_codes,
            material_code=material_code, material_keyword=material_keyword, major_category=major_category,
        )
        q = self.db.query(
            func.coalesce(PurchaseRecord.purchase_purpose, '未指定').label('p'),
            func.coalesce(func.sum(PurchaseRecord.cny_amount), 0).label('amt'),
            func.count(PurchaseRecord.id).label('cnt'),
        )
        if cond is not None:
            q = q.filter(cond)
        q = q.group_by('p').order_by(func.sum(PurchaseRecord.cny_amount).desc())

        return [
            {
                "purpose": p,
                "amount_cny": round(_to_float(a), 2),
                "order_count": int(cnt or 0),
            }
            for p, a, cnt in q.all()
        ]

    # ==================== 9. 单价波动分析 ====================
    def get_price_volatility(
        self,
        fiscal_year: Optional[int] = None,
        limit: int = 30,
        company_name: Optional[str] = None,
        company_codes: Optional[list] = None,
        material_code: Optional[str] = None,
        material_keyword: Optional[str] = None,
        major_category: Optional[str] = None,
    ) -> list:
        """物料单价波动分析：对比上一年同物料同币种的平均单价"""
        if not fiscal_year:
            return []

        prev_year_row = self.db.query(func.max(PurchaseRecord.fiscal_year)).filter(
            PurchaseRecord.fiscal_year < fiscal_year
        ).scalar()
        if not prev_year_row:
            return []
        prev_year = int(prev_year_row)

        curr_cond = self._base_filter(
            fiscal_year=fiscal_year, company_name=company_name, company_codes=company_codes,
            material_code=material_code, material_keyword=material_keyword, major_category=major_category,
        )
        curr_q = self.db.query(
            PurchaseRecord.material_code,
            PurchaseRecord.material_name,
            PurchaseRecord.order_currency,
            func.coalesce(
                func.sum(PurchaseRecord.cny_amount) / func.nullif(func.sum(PurchaseRecord.quantity), 0),
                0
            ).label('avg_price'),
            func.coalesce(func.sum(PurchaseRecord.cny_amount), 0).label('amt'),
            func.count(PurchaseRecord.id).label('cnt'),
        )
        if curr_cond is not None:
            curr_q = curr_q.filter(curr_cond)
        curr_q = curr_q.group_by(
            PurchaseRecord.material_code,
            PurchaseRecord.material_name,
            PurchaseRecord.order_currency,
        ).having(func.count(PurchaseRecord.id) >= 3)

        curr_data = {}
        for mc, mn, cur, ap, a, cnt in curr_q.all():
            key = (mc, cur)
            curr_data[key] = {
                "material_code": mc,
                "material_name": mn,
                "currency": cur,
                "current_avg_price": _to_float(ap),
                "current_amount": _to_float(a),
                "current_count": int(cnt or 0),
            }

        prev_cond = self._base_filter(
            fiscal_year=prev_year, company_name=company_name, company_codes=company_codes,
            material_code=material_code, material_keyword=material_keyword, major_category=major_category,
        )
        prev_q = self.db.query(
            PurchaseRecord.material_code,
            PurchaseRecord.order_currency,
            func.coalesce(
                func.sum(PurchaseRecord.cny_amount) / func.nullif(func.sum(PurchaseRecord.quantity), 0),
                0
            ).label('avg_price'),
            func.coalesce(func.sum(PurchaseRecord.cny_amount), 0).label('amt'),
            func.count(PurchaseRecord.id).label('cnt'),
        )
        if prev_cond is not None:
            prev_q = prev_q.filter(prev_cond)
        prev_q = prev_q.group_by(
            PurchaseRecord.material_code,
            PurchaseRecord.order_currency,
        ).having(func.count(PurchaseRecord.id) >= 2)

        prev_data = {}
        for mc, cur, ap, a, cnt in prev_q.all():
            prev_data[(mc, cur)] = {
                "previous_avg_price": _to_float(ap),
                "previous_amount": _to_float(a),
                "previous_count": int(cnt or 0),
            }

        result = []
        for key, curr in curr_data.items():
            mc, cur = key
            prev = prev_data.get(key)
            if not prev:
                continue
            prev_price = prev["previous_avg_price"]
            curr_price = curr["current_avg_price"]
            if prev_price <= 0 or curr_price <= 0:
                continue
            change_rate = (curr_price - prev_price) / prev_price * 100

            if curr["current_amount"] < 10000:
                continue

            result.append({
                "material_code": mc,
                "material_name": curr["material_name"],
                "currency": cur,
                "current_avg_price": round(curr_price, 4),
                "previous_avg_price": round(prev_price, 4),
                "change_rate": round(change_rate, 2),
                "current_amount": round(curr["current_amount"], 2),
                "current_count": curr["current_count"],
                "compare_year": prev_year,
            })

        result.sort(key=lambda x: abs(x["change_rate"]), reverse=True)
        return result[:limit]

    # ==================== 10. 公司 × 月度 热力图数据 ====================
    def get_company_month_matrix(
        self,
        fiscal_year: Optional[int] = None,
        company_name: Optional[str] = None,
        company_codes: Optional[list] = None,
        material_code: Optional[str] = None,
        material_keyword: Optional[str] = None,
        major_category: Optional[str] = None,
    ) -> dict:
        """公司 × 月度 热力图：每个公司每个月的采购金额"""
        cond = self._base_filter(
            fiscal_year=fiscal_year, company_name=company_name, company_codes=company_codes,
            material_code=material_code, material_keyword=material_keyword, major_category=major_category,
        )
        month_col = extract('month', PurchaseRecord.transaction_date)
        q = self.db.query(
            PurchaseRecord.company_name,
            month_col.label('month'),
            func.coalesce(func.sum(PurchaseRecord.cny_amount), 0).label('amt'),
        )
        if cond is not None:
            q = q.filter(cond)
        q = q.group_by(PurchaseRecord.company_name, month_col).order_by(
            PurchaseRecord.company_name, month_col
        )

        companies = set()
        matrix = {}
        for cn, m, amt in q.all():
            companies.add(cn)
            matrix[(cn, int(m))] = round(_to_float(amt), 2)

        return {
            "companies": sorted(list(companies)),
            "months": list(range(1, 13)),
            "matrix": [
                {"company": c, "month": m, "amount_cny": matrix.get((c, m), 0)}
                for c in sorted(companies) for m in range(1, 13)
            ]
        }

    # ==================== 11. 事业部采购占比分布 ====================
    def get_unit_distribution(
        self,
        fiscal_year: Optional[int] = None,
        company_name: Optional[str] = None,
        company_codes: Optional[list] = None,
        material_code: Optional[str] = None,
        material_keyword: Optional[str] = None,
        major_category: Optional[str] = None,
    ) -> list:
        """各事业部采购金额分布（通过 公司→板块→事业部 JOIN）"""
        cond = self._base_filter(
            fiscal_year=fiscal_year, company_name=company_name, company_codes=company_codes,
            material_code=material_code, material_keyword=material_keyword, major_category=major_category,
        )
        q = self.db.query(
            BusinessUnit.id.label('unit_id'),
            BusinessUnit.unit_code,
            BusinessUnit.unit_name,
            func.coalesce(func.sum(PurchaseRecord.cny_amount), 0).label('amt'),
            func.count(PurchaseRecord.id).label('cnt'),
            func.count(func.distinct(PurchaseRecord.company_code)).label('co_cnt'),
        ).join(
            Company, PurchaseRecord.company_code == Company.company_code
        ).join(
            BusinessSector, Company.sector_id == BusinessSector.id
        ).join(
            BusinessUnit, BusinessSector.unit_id == BusinessUnit.id
        )
        if cond is not None:
            q = q.filter(cond)
        q = q.group_by(BusinessUnit.id, BusinessUnit.unit_code, BusinessUnit.unit_name)
        q = q.order_by(func.sum(PurchaseRecord.cny_amount).desc())

        return [
            {
                "unit_id": uid,
                "unit_code": uc,
                "unit_name": un,
                "amount_cny": round(_to_float(a), 2),
                "order_count": int(cnt or 0),
                "company_count": int(co or 0),
            }
            for uid, uc, un, a, cnt, co in q.all()
        ]

    def get_sector_distribution_by_unit(
        self,
        unit_id: int,
        fiscal_year: Optional[int] = None,
        company_name: Optional[str] = None,
        company_codes: Optional[list] = None,
        material_code: Optional[str] = None,
        material_keyword: Optional[str] = None,
        major_category: Optional[str] = None,
    ) -> list:
        """指定事业部下的各板块采购金额分布"""
        cond = self._base_filter(
            fiscal_year=fiscal_year, company_name=company_name, company_codes=company_codes,
            material_code=material_code, material_keyword=material_keyword, major_category=major_category,
        )
        q = self.db.query(
            BusinessSector.id.label('sector_id'),
            BusinessSector.sector_code,
            BusinessSector.sector_name,
            func.coalesce(func.sum(PurchaseRecord.cny_amount), 0).label('amt'),
            func.count(PurchaseRecord.id).label('cnt'),
            func.count(func.distinct(PurchaseRecord.company_code)).label('co_cnt'),
        ).join(
            Company, PurchaseRecord.company_code == Company.company_code
        ).join(
            BusinessSector, Company.sector_id == BusinessSector.id
        ).filter(
            BusinessSector.unit_id == unit_id
        )
        if cond is not None:
            q = q.filter(cond)
        q = q.group_by(BusinessSector.id, BusinessSector.sector_code, BusinessSector.sector_name)
        q = q.order_by(func.sum(PurchaseRecord.cny_amount).desc())

        return [
            {
                "sector_id": sid,
                "sector_code": sc,
                "sector_name": sn,
                "amount_cny": round(_to_float(a), 2),
                "order_count": int(cnt or 0),
                "company_count": int(co or 0),
            }
            for sid, sc, sn, a, cnt, co in q.all()
        ]

    # ==================== 综合 Dashboard ====================
    def get_full_dashboard(
        self,
        fiscal_year: Optional[int] = None,
        company_name: Optional[str] = None,
        company_codes: Optional[list] = None,
        material_code: Optional[str] = None,
        material_keyword: Optional[str] = None,
        major_category: Optional[str] = None,
    ) -> dict:
        """一次性返回所有 dashboard 数据"""
        return {
            "kpis": self.get_kpis(
                fiscal_year=fiscal_year, company_name=company_name, company_codes=company_codes,
                material_code=material_code, material_keyword=material_keyword, major_category=major_category,
            ),
            "monthly_trend": self.get_monthly_trend(
                fiscal_year=fiscal_year, company_name=company_name, company_codes=company_codes,
                material_code=material_code, material_keyword=material_keyword, major_category=major_category,
            ),
            "quarterly": self.get_quarterly_distribution(
                fiscal_year=fiscal_year, company_name=company_name, company_codes=company_codes,
                material_code=material_code, material_keyword=material_keyword, major_category=major_category,
            ),
            "company_comparison": self.get_company_comparison(
                fiscal_year=fiscal_year, company_name=company_name, company_codes=company_codes,
                material_code=material_code, material_keyword=material_keyword, major_category=major_category,
            ),
            "top_suppliers": self.get_top_suppliers(
                fiscal_year=fiscal_year, limit=20, company_name=company_name, company_codes=company_codes,
                material_code=material_code, material_keyword=material_keyword, major_category=major_category,
            ),
            "top_materials": self.get_top_materials(
                fiscal_year=fiscal_year, limit=20, company_name=company_name, company_codes=company_codes,
                material_code=material_code, material_keyword=material_keyword, major_category=major_category,
            ),
            "category_distribution": self.get_category_distribution(
                fiscal_year=fiscal_year, company_name=company_name, company_codes=company_codes,
                material_code=material_code, material_keyword=material_keyword, major_category=major_category,
            ),
            "major_category_distribution": self.get_major_category_distribution(
                fiscal_year=fiscal_year, company_name=company_name, company_codes=company_codes,
                material_code=material_code, material_keyword=material_keyword, major_category=major_category,
            ),
            "price_volatility": self.get_price_volatility(
                fiscal_year=fiscal_year, limit=30, company_name=company_name, company_codes=company_codes,
                material_code=material_code, material_keyword=material_keyword, major_category=major_category,
            ),
            "unit_distribution": self.get_unit_distribution(
                fiscal_year=fiscal_year, company_codes=company_codes,
                material_code=material_code, material_keyword=material_keyword, major_category=major_category,
            ),
        }

    def search_materials_from_records(
        self,
        keyword: str,
        limit: int = 20,
        company_codes: Optional[List[str]] = None,
    ) -> list:
        """从采购记录中模糊搜索物料（编码或名称），返回去重列表"""
        pattern = f"%{keyword}%"
        query = (
            self.db.query(
                PurchaseRecord.material_code,
                func.max(PurchaseRecord.material_name).label("material_name"),
                func.sum(PurchaseRecord.cny_amount).label("total_cny"),
            )
            .filter(
                # 软删除过滤：排除已冲销/删除记录
                PurchaseRecord.deleted_at.is_(None),
                PurchaseRecord.material_code != '',
                PurchaseRecord.material_code.isnot(None),
                or_(
                    PurchaseRecord.material_code.ilike(pattern),
                    PurchaseRecord.material_name.ilike(pattern),
                )
            )
        )
        if company_codes:
            query = query.filter(PurchaseRecord.company_code.in_(company_codes))
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
                "total_amount_cny": round(_to_float(r[2]), 2),
            }
            for r in rows
        ]

    # ========== 下钻查询 ==========

    def get_supplier_top_materials(
        self,
        supplier_name: str,
        fiscal_year: Optional[int] = None,
        company_codes: Optional[List[str]] = None,
        limit: int = 10,
    ) -> list:
        """供应商下钻：获取某供应商的前10大物料（编码、名称、金额）"""
        query = self.db.query(
            PurchaseRecord.material_code,
            func.max(PurchaseRecord.material_name).label('material_name'),
            func.sum(PurchaseRecord.cny_amount).label('total_cny'),
        ).filter(
            # 软删除过滤：排除已冲销/删除记录
            PurchaseRecord.deleted_at.is_(None),
            PurchaseRecord.supplier_name == supplier_name,
            PurchaseRecord.material_code != '',
            PurchaseRecord.material_code.isnot(None),
        )
        if fiscal_year:
            query = query.filter(PurchaseRecord.fiscal_year == fiscal_year)
        if company_codes:
            query = query.filter(PurchaseRecord.company_code.in_(company_codes))
        rows = (
            query
            .group_by(PurchaseRecord.material_code)
            .order_by(func.sum(PurchaseRecord.cny_amount).desc())
            .limit(limit)
            .all()
        )
        return [
            {
                'material_code': r[0],
                'material_name': r[1] or '',
                'amount_cny': round(_to_float(r[2]), 2),
            }
            for r in rows
        ]

    def get_material_top_suppliers(
        self,
        material_code: str,
        fiscal_year: Optional[int] = None,
        company_codes: Optional[List[str]] = None,
        limit: int = 10,
    ) -> list:
        """物料下钻：获取某物料的前10大供应商（名称、金额）"""
        query = self.db.query(
            PurchaseRecord.supplier_name,
            func.sum(PurchaseRecord.cny_amount).label('total_cny'),
        ).filter(
            # 软删除过滤：排除已冲销/删除记录
            PurchaseRecord.deleted_at.is_(None),
            PurchaseRecord.material_code == material_code,
            PurchaseRecord.supplier_name != '',
            PurchaseRecord.supplier_name.isnot(None),
        )
        if fiscal_year:
            query = query.filter(PurchaseRecord.fiscal_year == fiscal_year)
        if company_codes:
            query = query.filter(PurchaseRecord.company_code.in_(company_codes))
        rows = (
            query
            .group_by(PurchaseRecord.supplier_name)
            .order_by(func.sum(PurchaseRecord.cny_amount).desc())
            .limit(limit)
            .all()
        )
        return [
            {
                'supplier_name': r[0],
                'amount_cny': round(_to_float(r[1]), 2),
            }
            for r in rows
        ]

    # ========== 供应商深度分析 ==========

    def get_single_source_risk(
        self,
        fiscal_year: Optional[int] = None,
        company_codes: Optional[List[str]] = None,
        limit: int = 50,
    ) -> list:
        """
        单源供应风险清单：找出只有1个供应商的物料，按采购金额降序排列
        返回：物料编码、物料名称、唯一供应商、采购金额、HHI指数(=1.0)
        """
        # 子查询：每个物料的供应商数量和总金额
        subq = (
            self.db.query(
                PurchaseRecord.material_code,
                func.max(PurchaseRecord.material_name).label('material_name'),
                func.count(func.distinct(PurchaseRecord.supplier_name)).label('supplier_count'),
                func.sum(PurchaseRecord.cny_amount).label('total_amount'),
            )
            .filter(
                # 软删除过滤：排除已冲销/删除记录
                PurchaseRecord.deleted_at.is_(None),
                PurchaseRecord.material_code != '',
                PurchaseRecord.material_code.isnot(None),
                PurchaseRecord.supplier_name != '',
                PurchaseRecord.supplier_name.isnot(None),
            )
        )
        if fiscal_year:
            subq = subq.filter(PurchaseRecord.fiscal_year == fiscal_year)
        if company_codes:
            subq = subq.filter(PurchaseRecord.company_code.in_(company_codes))
        
        subq = subq.group_by(PurchaseRecord.material_code).subquery()
        
        # 筛选出只有1个供应商的物料
        risk_query = (
            self.db.query(
                subq.c.material_code,
                subq.c.material_name,
                subq.c.supplier_count,
                subq.c.total_amount,
            )
            .filter(subq.c.supplier_count == 1)
            .order_by(subq.c.total_amount.desc())
            .limit(limit)
        )
        
        risk_items = risk_query.all()

        # 批量获取所有物料的唯一供应商名（一次查询替代原循环内 N+1 查询）
        material_codes = [r[0] for r in risk_items]
        supplier_map: dict[str, str] = {}
        if material_codes:
            supplier_rows = (
                self.db.query(
                    PurchaseRecord.material_code,
                    PurchaseRecord.supplier_name,
                )
                .filter(
                    PurchaseRecord.deleted_at.is_(None),
                    PurchaseRecord.material_code.in_(material_codes),
                    PurchaseRecord.supplier_name != '',
                )
                .distinct()
                .all()
            )
            for mc, sn in supplier_rows:
                # 单源物料只会有一个供应商，取第一个即可
                supplier_map.setdefault(mc, sn)

        result = []
        for r in risk_items:
            supplier_name = supplier_map.get(r[0], '未知')

            result.append({
                'material_code': r[0],
                'material_name': r[1] or '',
                'supplier_count': r[2],
                'amount_cny': round(_to_float(r[3]), 2),
                'supplier_name': supplier_name,
                'hhi': 1.0,  # 单源供应 HHI = 1.0
            })

        return result

    def get_supplier_price_comparison(
        self,
        material_code: str,
        fiscal_year: Optional[int] = None,
        company_codes: Optional[List[str]] = None,
    ) -> dict:
        """
        供应商比价分析：对指定物料，统计各供应商的采购量、金额、均价
        返回：供应商列表 + 均价 + 降本测算
        """
        query = self.db.query(
            PurchaseRecord.supplier_name,
            func.sum(PurchaseRecord.quantity).label('total_qty'),
            func.sum(PurchaseRecord.cny_amount).label('total_amount'),
            func.avg(PurchaseRecord.unit_price).label('avg_price'),
            func.max(PurchaseRecord.transaction_date).label('last_date'),
        ).filter(
            # 软删除过滤：排除已冲销/删除记录
            PurchaseRecord.deleted_at.is_(None),
            PurchaseRecord.material_code == material_code,
            PurchaseRecord.supplier_name != '',
            PurchaseRecord.supplier_name.isnot(None),
        )
        if fiscal_year:
            query = query.filter(PurchaseRecord.fiscal_year == fiscal_year)
        if company_codes:
            query = query.filter(PurchaseRecord.company_code.in_(company_codes))
        
        rows = (
            query
            .group_by(PurchaseRecord.supplier_name)
            .order_by(func.sum(PurchaseRecord.cny_amount).desc())
            .all()
        )
        
        if not rows:
            return {'suppliers': [], 'avg_price': 0, 'min_price': 0, 'savings_potential': 0}
        
        suppliers = []
        total_qty = 0
        total_amount = 0
        prices = []
        
        for r in rows:
            qty = _to_float(r[1])
            amt = _to_float(r[2])
            avg_p = _to_float(r[3])
            suppliers.append({
                'supplier_name': r[0],
                'quantity': round(qty, 2),
                'amount_cny': round(amt, 2),
                'avg_price': round(avg_p, 4),
                'last_purchase_date': str(r[4]) if r[4] else '',
            })
            total_qty += qty
            total_amount += amt
            if avg_p > 0:
                prices.append(avg_p)
        
        overall_avg = total_amount / total_qty if total_qty > 0 else 0
        min_price = min(prices) if prices else 0
        
        # 降本测算：如果全部切换到最低价供应商，能省多少
        savings = 0
        if min_price > 0 and total_qty > 0:
            current_total = total_amount
            ideal_total = total_qty * min_price
            savings = current_total - ideal_total
        
        # 计算各供应商与均价的偏差
        for s in suppliers:
            if overall_avg > 0:
                s['price_vs_avg'] = round((s['avg_price'] - overall_avg) / overall_avg * 100, 2)
            else:
                s['price_vs_avg'] = 0
        
        return {
            'suppliers': suppliers,
            'avg_price': round(overall_avg, 4),
            'min_price': round(min_price, 4),
            'savings_potential': round(savings, 2),
            'total_amount': round(total_amount, 2),
            'total_quantity': round(total_qty, 2),
        }
