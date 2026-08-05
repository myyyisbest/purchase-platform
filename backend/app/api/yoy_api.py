"""
采购同期对比分析API路由
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, List
from ..database import get_db
from ..models import User
from ..auth import get_current_user, get_effective_company_codes
from ..services.yoy_service import YoYAnalysisService
from ..services.export_service import ExportService

router = APIRouter()


@router.get("/years")
def get_available_years(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取数据中可用的年份列表"""
    service = YoYAnalysisService(db)
    years = service.get_available_years()
    return {"code": 200, "data": years}


@router.get("/companies")
def get_available_companies(
    year: Optional[int] = Query(None, description="筛选年份"),
    company_codes: Optional[List[str]] = Query(None, description="公司代码过滤"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取数据中可用的公司列表"""
    service = YoYAnalysisService(db)
    company_codes = get_effective_company_codes(current_user, company_codes, db)
    companies = service.get_available_companies(year, company_codes=company_codes)
    return {"code": 200, "data": companies}


@router.get("/materials")
def get_available_materials(
    year: Optional[int] = Query(None, description="筛选年份"),
    company_name: Optional[str] = Query(None, description="筛选公司名称"),
    company_codes: Optional[List[str]] = Query(None, description="公司代码过滤"),
    material_keyword: Optional[str] = Query(None, description="物料编码/名称模糊搜索"),
    major_category: Optional[str] = Query(None, description="物料大类"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取数据中可用的物料列表"""
    service = YoYAnalysisService(db)
    # 越权防护：company_codes 必须经过当前用户授权范围过滤
    effective_codes = get_effective_company_codes(current_user, company_codes, db)
    materials = service.get_available_materials(
        year, company_name, company_codes=effective_codes,
        material_keyword=material_keyword, major_category=major_category,
    )
    return {"code": 200, "data": materials}


@router.get("/analyze")
def analyze(
    current_year: int = Query(..., description="当年年份，如2026"),
    period: int = Query(..., ge=1, le=12, description="截止月份(1-12)"),
    company_name: Optional[str] = Query(None, description="筛选公司名称"),
    company_codes: Optional[List[str]] = Query(None, description="公司代码列表（多选用这个，优先级高于 company_name）"),
    material_name: Optional[str] = Query(None, description="筛选物料名称(模糊搜索)"),
    material_code: Optional[str] = Query(None, description="物料编码(精确)"),
    material_keyword: Optional[str] = Query(None, description="物料编码/名称模糊搜索"),
    major_category: Optional[str] = Query(None, description="物料大类"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=10, le=10000, description="每页条数"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    采购同期对比分析

    当年：累计1月到指定月份的采购数据
    上年：全年1月到12月的采购数据
    分组维度：物料 + 公司
    """
    service = YoYAnalysisService(db)

    years = service.get_available_years()
    if current_year not in years:
        prev_year = current_year - 1
        if prev_year not in years:
            raise HTTPException(
                status_code=404,
                detail=f"数据库中缺少 {current_year} 和 {prev_year} 年的数据，请先导入采购台账数据"
            )

    # 越权防护：company_codes 必须经过当前用户授权范围过滤
    effective_codes = get_effective_company_codes(current_user, company_codes, db)

    result = service.analyze(
        current_year=current_year,
        period=period,
        company_name=company_name,
        company_codes=effective_codes,
        material_name=material_name or material_keyword,
        material_code=material_code,
        major_category=major_category,
        page=page,
        page_size=page_size
    )

    return {"code": 200, "data": result}


@router.get("/export")
def export_analysis(
    current_year: int = Query(..., description="当年年份"),
    period: int = Query(..., ge=1, le=12, description="截止月份"),
    company_name: Optional[str] = Query(None, description="筛选公司名称"),
    company_codes: Optional[List[str]] = Query(None, description="公司代码列表"),
    material_name: Optional[str] = Query(None, description="筛选物料名称"),
    material_keyword: Optional[str] = Query(None, description="物料编码/名称模糊搜索"),
    major_category: Optional[str] = Query(None, description="物料大类"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """导出分析结果为Excel文件"""
    service = YoYAnalysisService(db)
    export_service = ExportService(db)

    # 越权防护：company_codes 必须经过当前用户授权范围过滤
    effective_codes = get_effective_company_codes(current_user, company_codes, db)

    items = service.export_analysis(
        current_year=current_year,
        period=period,
        company_name=company_name,
        company_codes=effective_codes,
        material_name=material_name or material_keyword,
        major_category=major_category,
    )

    return export_service.generate_yoy_excel(
        items=items,
        current_year=current_year,
        period=period,
        company_name=company_name
    )