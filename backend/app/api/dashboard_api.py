"""
采购分析面板 Dashboard API
支持财年 + 公司代码列表 + 物料编码 + 物料大类 等多维过滤
"""
from fastapi import APIRouter, Query
from typing import Optional, List

from ..dependencies import (
    FiscalYear, CompanyName, CompanyCodes, MaterialCode,
    MaterialKeyword, MajorCategory, CurrentUser, DbSession,
)
from ..auth import get_effective_company_codes
from ..services.dashboard_service import DashboardService
from ..services.export_service import ExportService

router = APIRouter()


def _resolve(user: CurrentUser, codes: CompanyCodes, db: DbSession) -> Optional[List[str]]:
    """计算有效公司过滤范围（admin=不限制，普通用户=授权交集）"""
    return get_effective_company_codes(user, codes, db)


@router.get("/kpis")
def get_kpis(
    fiscal_year: FiscalYear = None,
    company_name: CompanyName = None,
    company_codes: CompanyCodes = None,
    material_code: MaterialCode = None,
    material_keyword: MaterialKeyword = None,
    major_category: MajorCategory = None,
    current_user: CurrentUser = None,
    db: DbSession = None,
):
    """KPI 关键指标"""
    return DashboardService(db).get_kpis(
        fiscal_year=fiscal_year, company_name=company_name or None,
        company_codes=_resolve(current_user, company_codes, db),
        material_code=material_code or None, material_keyword=material_keyword or None,
        major_category=major_category or None,
    )


@router.get("/monthly-trend")
def get_monthly_trend(
    fiscal_year: FiscalYear = None,
    company_name: CompanyName = None,
    company_codes: CompanyCodes = None,
    material_code: MaterialCode = None,
    material_keyword: MaterialKeyword = None,
    major_category: MajorCategory = None,
    current_user: CurrentUser = None,
    db: DbSession = None,
):
    """月度采购趋势（金额 + 笔数 + 单价）"""
    return DashboardService(db).get_monthly_trend(
        fiscal_year=fiscal_year, company_name=company_name or None,
        company_codes=_resolve(current_user, company_codes, db),
        material_code=material_code or None, material_keyword=material_keyword or None,
        major_category=major_category or None,
    )


@router.get("/quarterly")
def get_quarterly(
    fiscal_year: FiscalYear = None,
    company_name: CompanyName = None,
    company_codes: CompanyCodes = None,
    material_code: MaterialCode = None,
    material_keyword: MaterialKeyword = None,
    major_category: MajorCategory = None,
    current_user: CurrentUser = None,
    db: DbSession = None,
):
    """季度采购分布"""
    return DashboardService(db).get_quarterly_distribution(
        fiscal_year=fiscal_year, company_name=company_name or None,
        company_codes=_resolve(current_user, company_codes, db),
        material_code=material_code or None, material_keyword=material_keyword or None,
        major_category=major_category or None,
    )


@router.get("/company-comparison")
def get_company_comparison(
    fiscal_year: FiscalYear = None,
    company_name: CompanyName = None,
    company_codes: CompanyCodes = None,
    material_code: MaterialCode = None,
    material_keyword: MaterialKeyword = None,
    major_category: MajorCategory = None,
    current_user: CurrentUser = None,
    db: DbSession = None,
):
    """公司采购对比"""
    return DashboardService(db).get_company_comparison(
        fiscal_year=fiscal_year, company_name=company_name or None,
        company_codes=_resolve(current_user, company_codes, db),
        material_code=material_code or None, material_keyword=material_keyword or None,
        major_category=major_category or None,
    )


@router.get("/top-suppliers")
def get_top_suppliers(
    fiscal_year: FiscalYear = None,
    company_name: CompanyName = None,
    company_codes: CompanyCodes = None,
    material_code: MaterialCode = None,
    material_keyword: MaterialKeyword = None,
    major_category: MajorCategory = None,
    current_user: CurrentUser = None,
    db: DbSession = None,
    limit: int = Query(20, ge=1, le=100),
):
    """供应商 TOP 榜"""
    return DashboardService(db).get_top_suppliers(
        fiscal_year=fiscal_year, limit=limit, company_name=company_name or None,
        company_codes=_resolve(current_user, company_codes, db),
        material_code=material_code or None, material_keyword=material_keyword or None,
        major_category=major_category or None,
    )


@router.get("/top-materials")
def get_top_materials(
    fiscal_year: FiscalYear = None,
    company_name: CompanyName = None,
    company_codes: CompanyCodes = None,
    material_code: MaterialCode = None,
    material_keyword: MaterialKeyword = None,
    major_category: MajorCategory = None,
    current_user: CurrentUser = None,
    db: DbSession = None,
    limit: int = Query(20, ge=1, le=100),
):
    """物料 TOP 榜"""
    return DashboardService(db).get_top_materials(
        fiscal_year=fiscal_year, limit=limit, company_name=company_name or None,
        company_codes=_resolve(current_user, company_codes, db),
        material_code=material_code or None, material_keyword=material_keyword or None,
        major_category=major_category or None,
    )


@router.get("/category-distribution")
def get_category_distribution(
    fiscal_year: FiscalYear = None,
    company_name: CompanyName = None,
    company_codes: CompanyCodes = None,
    material_code: MaterialCode = None,
    material_keyword: MaterialKeyword = None,
    major_category: MajorCategory = None,
    current_user: CurrentUser = None,
    db: DbSession = None,
):
    """物料类别分布（来自 Excel 物料类别字段）"""
    return DashboardService(db).get_category_distribution(
        fiscal_year=fiscal_year, company_name=company_name or None,
        company_codes=_resolve(current_user, company_codes, db),
        material_code=material_code or None, material_keyword=material_keyword or None,
        major_category=major_category or None,
    )


@router.get("/major-category-distribution")
def get_major_category_distribution(
    fiscal_year: FiscalYear = None,
    company_name: CompanyName = None,
    company_codes: CompanyCodes = None,
    material_code: MaterialCode = None,
    material_keyword: MaterialKeyword = None,
    major_category: MajorCategory = None,
    current_user: CurrentUser = None,
    db: DbSession = None,
):
    """物料大类分布（来自 material_major_categories 维护表）"""
    return DashboardService(db).get_major_category_distribution(
        fiscal_year=fiscal_year, company_name=company_name or None,
        company_codes=_resolve(current_user, company_codes, db),
        material_code=material_code or None, material_keyword=material_keyword or None,
        major_category=major_category or None,
    )


@router.get("/price-volatility")
def get_price_volatility(
    fiscal_year: FiscalYear = None,
    company_name: CompanyName = None,
    company_codes: CompanyCodes = None,
    material_code: MaterialCode = None,
    material_keyword: MaterialKeyword = None,
    major_category: MajorCategory = None,
    current_user: CurrentUser = None,
    db: DbSession = None,
    limit: int = Query(30, ge=1, le=500),
):
    """单价波动分析（按订单货币维度同比）"""
    return DashboardService(db).get_price_volatility(
        fiscal_year=fiscal_year, limit=limit, company_name=company_name or None,
        company_codes=_resolve(current_user, company_codes, db),
        material_code=material_code or None, material_keyword=material_keyword or None,
        major_category=major_category or None,
    )


@router.get("/sector-distribution/{unit_id}")
def get_sector_distribution_by_unit(
    unit_id: int,
    fiscal_year: FiscalYear = None,
    company_codes: CompanyCodes = None,
    material_code: MaterialCode = None,
    material_keyword: MaterialKeyword = None,
    major_category: MajorCategory = None,
    current_user: CurrentUser = None,
    db: DbSession = None,
):
    """指定事业部下的板块采购金额分布"""
    return DashboardService(db).get_sector_distribution_by_unit(
        unit_id=unit_id, fiscal_year=fiscal_year,
        company_codes=_resolve(current_user, company_codes, db),
        material_code=material_code or None, material_keyword=material_keyword or None,
        major_category=major_category or None,
    )


@router.get("/unit-distribution")
def get_unit_distribution(
    fiscal_year: FiscalYear = None,
    company_codes: CompanyCodes = None,
    material_code: MaterialCode = None,
    material_keyword: MaterialKeyword = None,
    major_category: MajorCategory = None,
    current_user: CurrentUser = None,
    db: DbSession = None,
):
    """事业部采购金额分布（支持全部过滤参数）"""
    return DashboardService(db).get_unit_distribution(
        fiscal_year=fiscal_year,
        company_codes=_resolve(current_user, company_codes, db),
        material_code=material_code or None, material_keyword=material_keyword or None,
        major_category=major_category or None,
    )


@router.get("/search-materials")
def search_materials(
    company_codes: CompanyCodes = None,
    current_user: CurrentUser = None,
    db: DbSession = None,
    keyword: str = Query(..., min_length=1, description="搜索关键词"),
    limit: int = Query(20, ge=1, le=50),
):
    """从采购记录中搜索物料（编码或名称模糊匹配），用于筛选器自动补全"""
    return DashboardService(db).search_materials_from_records(
        keyword=keyword, limit=limit,
        company_codes=_resolve(current_user, company_codes, db),
    )


@router.get("/full")
def get_full_dashboard(
    fiscal_year: FiscalYear = None,
    company_name: CompanyName = None,
    company_codes: CompanyCodes = None,
    material_code: MaterialCode = None,
    material_keyword: MaterialKeyword = None,
    major_category: MajorCategory = None,
    current_user: CurrentUser = None,
    db: DbSession = None,
):
    """综合 Dashboard：一次性返回所有数据（用于首屏加载）"""
    return DashboardService(db).get_full_dashboard(
        fiscal_year=fiscal_year, company_name=company_name or None,
        company_codes=_resolve(current_user, company_codes, db),
        material_code=material_code or None, material_keyword=material_keyword or None,
        major_category=major_category or None,
    )


# ========== 下钻查询 ==========

@router.get("/supplier-drill")
def get_supplier_drill(
    fiscal_year: FiscalYear = None,
    company_codes: CompanyCodes = None,
    current_user: CurrentUser = None,
    db: DbSession = None,
    supplier_name: str = Query(..., min_length=1, description="供应商名称"),
):
    """供应商下钻：查看该供应商的前10大物料"""
    return DashboardService(db).get_supplier_top_materials(
        supplier_name=supplier_name, fiscal_year=fiscal_year,
        company_codes=_resolve(current_user, company_codes, db),
    )


@router.get("/material-drill")
def get_material_drill(
    fiscal_year: FiscalYear = None,
    company_codes: CompanyCodes = None,
    current_user: CurrentUser = None,
    db: DbSession = None,
    material_code: str = Query(..., min_length=1, description="物料编码"),
):
    """物料下钻：查看该物料的前10大供应商"""
    return DashboardService(db).get_material_top_suppliers(
        material_code=material_code, fiscal_year=fiscal_year,
        company_codes=_resolve(current_user, company_codes, db),
    )


# ========== 供应商深度分析 ==========

@router.get("/single-source-risk")
def get_single_source_risk(
    fiscal_year: FiscalYear = None,
    company_codes: CompanyCodes = None,
    current_user: CurrentUser = None,
    db: DbSession = None,
    limit: int = Query(50, ge=1, le=200),
):
    """单源供应风险清单：找出只有1个供应商的物料"""
    return DashboardService(db).get_single_source_risk(
        fiscal_year=fiscal_year,
        company_codes=_resolve(current_user, company_codes, db),
        limit=limit,
    )


@router.get("/single-source-risk/export")
def export_single_source_risk(
    fiscal_year: FiscalYear = None,
    company_codes: CompanyCodes = None,
    current_user: CurrentUser = None,
    db: DbSession = None,
    limit: int = Query(200, ge=1, le=500),
):
    """单源供应风险清单 Excel 导出"""
    data = DashboardService(db).get_single_source_risk(
        fiscal_year=fiscal_year,
        company_codes=_resolve(current_user, company_codes, db),
        limit=limit,
    )
    return ExportService().generate_single_source_risk_excel(data, fiscal_year)


@router.get("/supplier-price-comparison")
def get_supplier_price_comparison(
    fiscal_year: FiscalYear = None,
    company_codes: CompanyCodes = None,
    current_user: CurrentUser = None,
    db: DbSession = None,
    material_code: str = Query(..., min_length=1, description="物料编码"),
):
    """供应商比价分析：对指定物料，统计各供应商的采购量、金额、均价"""
    return DashboardService(db).get_supplier_price_comparison(
        material_code=material_code, fiscal_year=fiscal_year,
        company_codes=_resolve(current_user, company_codes, db),
    )
