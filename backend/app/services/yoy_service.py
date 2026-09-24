"""
采购同期对比分析服务
实现当年累计 vs 上年同期（默认）/ 上年全年 的对比分析逻辑
参考 purchase analysis 项目的 analyze() 函数
"""
from sqlalchemy.orm import Session
from sqlalchemy import func, text, and_, extract, or_
from ..models import PurchaseRecord, MaterialMajorCategory
from decimal import Decimal
from typing import Optional, List


def _apply_major_filter(db: Session, conditions: list, major_category: Optional[str]) -> None:
    """根据物料大类在 conditions 列表上叠加过滤条件"""
    if not major_category:
        return
    sub_rows = (
        db.query(MaterialMajorCategory.company_code, MaterialMajorCategory.material_code)
        .filter(MaterialMajorCategory.major_category == major_category)
        .all()
    )
    if not sub_rows:
        conditions.append(or_(PurchaseRecord.id.is_(None), PurchaseRecord.id == -1))
    else:
        conditions.append(
            and_(
                PurchaseRecord.company_code.in_([r[0] for r in sub_rows]),
                PurchaseRecord.material_code.in_([r[1] for r in sub_rows]),
            )
        )


class YoYAnalysisService:
    """采购同期对比分析服务"""

    def __init__(self, db: Session):
        self.db = db

    def get_available_years(self) -> List[int]:
        """获取数据中可用的年份列表"""
        years = self.db.query(PurchaseRecord.fiscal_year).filter(
            PurchaseRecord.deleted_at.is_(None)
        ).distinct().order_by(
            PurchaseRecord.fiscal_year.desc()
        ).all()
        return [y[0] for y in years if y[0] is not None]

    def get_available_companies(
        self,
        year: Optional[int] = None,
        company_codes: Optional[list] = None,
    ) -> List[dict]:
        """获取数据中可用的公司列表"""
        query = self.db.query(
            PurchaseRecord.company_code,
            PurchaseRecord.company_name
        ).filter(PurchaseRecord.deleted_at.is_(None)).distinct()
        if year:
            query = query.filter(PurchaseRecord.fiscal_year == year)
        if company_codes:
            query = query.filter(PurchaseRecord.company_code.in_(company_codes))
        results = query.order_by(PurchaseRecord.company_code).all()
        return [{"code": r[0], "name": r[1]} for r in results]

    def get_available_materials(
        self,
        year: Optional[int] = None,
        company_name: Optional[str] = None,
        company_codes: Optional[list] = None,
        material_keyword: Optional[str] = None,
        major_category: Optional[str] = None,
    ) -> List[dict]:
        """获取数据中可用的物料列表（用于筛选）"""
        query = self.db.query(
            PurchaseRecord.material_code,
            PurchaseRecord.material_name
        ).distinct().filter(
            PurchaseRecord.deleted_at.is_(None),
            PurchaseRecord.material_code != '',
            PurchaseRecord.material_code.isnot(None)
        )
        if year:
            query = query.filter(PurchaseRecord.fiscal_year == year)
        if company_name:
            query = query.filter(PurchaseRecord.company_name == company_name)
        if company_codes:
            query = query.filter(PurchaseRecord.company_code.in_(company_codes))
        if material_keyword:
            pattern = f"%{material_keyword}%"
            query = query.filter(
                or_(
                    PurchaseRecord.material_code.ilike(pattern),
                    PurchaseRecord.material_name.ilike(pattern),
                )
            )
        # 修复：原代码误传 [query] 进 _apply_major_filter，导致物料大类过滤完全失效
        major_conditions: list = []
        _apply_major_filter(self.db, major_conditions, major_category)
        if major_conditions:
            query = query.filter(*major_conditions)
        results = query.order_by(PurchaseRecord.material_code).all()
        return [{"code": r[0], "name": r[1]} for r in results]

    def analyze(
        self,
        current_year: int,
        period: int,  # 1-12, 截止月份
        company_name: Optional[str] = None,
        company_codes: Optional[list] = None,
        material_name: Optional[str] = None,
        material_code: Optional[str] = None,
        major_category: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
        compare_mode: str = "same_period",  # same_period | full_year
    ) -> dict:
        """
        采购同期对比分析

        逻辑：
        - 当年：累计1月~N月的采购数据
        - 上年（默认 same_period）：同样过滤 1月~N月，保证可比
        - 上年（full_year）：全年1月~12月（兼容旧口径，需显式指定）
        - 分组维度：物料代码 + 公司代码
        - 计算指标：
          - 当年平均单价 = 当年CNY金额累计 / 当年采购量累计
          - 上年平均单价 = 上年CNY金额累计 / 上年采购量累计
          - 单价变动 = 当年单价 - 上年单价
          - 变动率 = (当年单价 - 上年单价) / 上年单价 × 100%
          - 成本变动 = 单价变动 × 当年采购量

        Returns:
            分析结果，包含分组列表、汇总信息、分页信息
        """
        prev_year = current_year - 1

        # 构建基础筛选条件（含软删除过滤）
        base_filters = [PurchaseRecord.deleted_at.is_(None)]
        if company_name:
            base_filters.append(PurchaseRecord.company_name == company_name)
        if company_codes:
            base_filters.append(PurchaseRecord.company_code.in_(company_codes))
        if material_code:
            base_filters.append(PurchaseRecord.material_code == material_code)
        _apply_major_filter(self.db, base_filters, major_category)

        # 当年数据：1月到指定月份的累计
        current_query = self.db.query(
            PurchaseRecord.company_code,
            PurchaseRecord.company_name,
            PurchaseRecord.material_code,
            PurchaseRecord.material_name,
            func.sum(PurchaseRecord.cny_amount).label('current_amount'),
            func.sum(PurchaseRecord.quantity).label('current_qty')
        ).filter(
            PurchaseRecord.fiscal_year == current_year,
            extract('month', PurchaseRecord.transaction_date) <= period,
            PurchaseRecord.material_code != '',
            PurchaseRecord.material_code.isnot(None),
            *base_filters
        )

        if material_name:
            pattern = f"%{material_name}%"
            current_query = current_query.filter(
                or_(
                    PurchaseRecord.material_code.ilike(pattern),
                    PurchaseRecord.material_name.ilike(pattern),
                )
            )

        current_data = current_query.group_by(
            PurchaseRecord.company_code,
            PurchaseRecord.company_name,
            PurchaseRecord.material_code,
            PurchaseRecord.material_name
        ).all()

        # 上年数据：默认同期（1~N月）；full_year 则全年
        if compare_mode not in ("same_period", "full_year"):
            compare_mode = "same_period"
        prev_filters = list(base_filters)
        prev_query = self.db.query(
            PurchaseRecord.company_code,
            PurchaseRecord.material_code,
            func.sum(PurchaseRecord.cny_amount).label('prev_amount'),
            func.sum(PurchaseRecord.quantity).label('prev_qty')
        ).filter(
            PurchaseRecord.fiscal_year == prev_year,
            PurchaseRecord.material_code != '',
            PurchaseRecord.material_code.isnot(None),
            *prev_filters
        )
        if compare_mode == "same_period":
            prev_query = prev_query.filter(
                extract('month', PurchaseRecord.transaction_date) <= period
            )

        if material_name:
            pattern = f"%{material_name}%"
            prev_query = prev_query.filter(
                or_(
                    PurchaseRecord.material_code.ilike(pattern),
                    PurchaseRecord.material_name.ilike(pattern),
                )
            )

        prev_data = prev_query.group_by(
            PurchaseRecord.company_code,
            PurchaseRecord.material_code
        ).all()

        # 构建上年数据字典：{ (company_code, material_code): (amount, qty) }
        prev_dict = {}
        for row in prev_data:
            key = (row.company_code, row.material_code)
            prev_dict[key] = {
                'amount': float(row.prev_amount or 0),
                'qty': float(row.prev_qty or 0)
            }

        # 组合当年和上年数据，计算对比指标
        results = []
        for row in current_data:
            current_qty = float(row.current_qty or 0)
            if current_qty <= 0:
                continue  # 当年无采购量的不纳入

            current_amount = float(row.current_amount or 0)
            current_avg_price = current_amount / current_qty if current_qty > 0 else 0

            key = (row.company_code, row.material_code)
            prev_info = prev_dict.get(key, {'amount': 0, 'qty': 0})

            prev_amount = prev_info['amount']
            prev_qty = prev_info['qty']
            prev_avg_price = prev_amount / prev_qty if prev_qty > 0 else 0

            can_compare = prev_qty > 0  # 上年有数据才能对比

            price_change = current_avg_price - prev_avg_price if can_compare else 0
            price_change_rate = (price_change / prev_avg_price * 100) if can_compare and prev_avg_price > 0 else 0
            cost_change = price_change * current_qty if can_compare else 0

            results.append({
                'company_code': row.company_code,
                'company_name': row.company_name,
                'material_code': row.material_code,
                'material_name': row.material_name,
                'current_amount': round(current_amount, 2),
                'current_qty': round(current_qty, 4),
                'current_avg_price': round(current_avg_price, 2),
                'prev_amount': round(prev_amount, 2),
                'prev_qty': round(prev_qty, 4),
                'prev_avg_price': round(prev_avg_price, 2),
                'can_compare': can_compare,
                'price_change': round(price_change, 2),
                'price_change_rate': round(price_change_rate, 2),
                'cost_change': round(cost_change, 2)
            })

        # 按公司代码、物料代码排序
        results.sort(key=lambda x: (x['company_code'], x['material_code']))

        # 汇总统计
        total_current_amount = sum(r['current_amount'] for r in results)
        total_current_qty = sum(r['current_qty'] for r in results)
        total_prev_amount = sum(r['prev_amount'] for r in results)
        total_prev_qty = sum(r['prev_qty'] for r in results)
        comparable_count = sum(1 for r in results if r['can_compare'])
        price_down_count = sum(1 for r in results if r['can_compare'] and r['price_change'] < 0)
        price_up_count = sum(1 for r in results if r['can_compare'] and r['price_change'] > 0)
        total_cost_saving = sum(r['cost_change'] for r in results if r['can_compare'] and r['cost_change'] < 0)

        # 分页
        total_items = len(results)
        start = (page - 1) * page_size
        end = start + page_size
        page_results = results[start:end]

        return {
            'current_year': current_year,
            'prev_year': prev_year,
            'period': period,
            'compare_mode': compare_mode,
            'company_name': company_name,
            'material_name': material_name,
            'summary': {
                'total_items': total_items,
                'comparable_count': comparable_count,
                'price_down_count': price_down_count,
                'price_up_count': price_up_count,
                'total_current_amount': round(total_current_amount, 2),
                'total_prev_amount': round(total_prev_amount, 2),
                'total_cost_saving': round(total_cost_saving, 2),
                'total_current_qty': round(total_current_qty, 4),
                'total_prev_qty': round(total_prev_qty, 4)
            },
            'items': page_results,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total': total_items,
                'total_pages': (total_items + page_size - 1) // page_size
            }
        }

    def export_analysis(
        self,
        current_year: int,
        period: int,
        company_name: Optional[str] = None,
        company_codes: Optional[list] = None,
        material_name: Optional[str] = None,
        material_code: Optional[str] = None,
        major_category: Optional[str] = None,
        compare_mode: str = "same_period",
    ) -> list:
        """导出全部分析结果（不分页）"""
        result = self.analyze(
            current_year=current_year,
            period=period,
            company_name=company_name,
            company_codes=company_codes,
            material_name=material_name,
            material_code=material_code,
            major_category=major_category,
            compare_mode=compare_mode,
            page=1,
            page_size=999999  # 取全部数据
        )
        return result['items']