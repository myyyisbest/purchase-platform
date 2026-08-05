"""
物料单价趋势 API
提供：物料趋势查询、TOP物料列表、物料搜索
支持集团→事业部→板块→公司四级过滤 + 物料大类过滤

鉴权策略：所有登录用户可访问；company_codes 必须经过授权范围过滤防越权
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional, List

from ..database import get_db
from ..models import User
from ..auth import get_current_user, get_effective_company_codes
from ..services.price_trend_service import PriceTrendService

router = APIRouter()


def _ok(data=None, message="成功"):
    return {"code": 200, "message": message, "data": data}


@router.get("/trend/{material_code}", summary="获取物料滚动N个月单价趋势")
def get_material_trend(
    material_code: str,
    months: int = Query(13, ge=1, le=36, description="滚动月数，默认13"),
    company_codes: Optional[List[str]] = Query(None, description="公司代码列表"),
    major_category: Optional[str] = Query(None, description="物料大类"),
    end_month: Optional[str] = Query(None, description="截止月份 YYYY-MM 格式，为空则使用最新月份"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # 越权防护：company_codes 必须经过当前用户授权范围过滤
    effective_codes = get_effective_company_codes(current_user, company_codes, db)
    svc = PriceTrendService(db)
    data = svc.get_material_price_trend(
        material_code, months=months,
        company_codes=effective_codes, major_category=major_category,
        end_month=end_month,
    )
    return _ok(data)


@router.get("/top", summary="获取TOP N物料（按最近12个月采购金额）")
def get_top_materials(
    limit: int = Query(20, ge=1, le=50),
    company_codes: Optional[List[str]] = Query(None),
    major_category: Optional[str] = Query(None),
    end_month: Optional[str] = Query(None, description="截止月份 YYYY-MM"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    effective_codes = get_effective_company_codes(current_user, company_codes, db)
    svc = PriceTrendService(db)
    codes = svc.get_top_materials_for_trend(
        limit=limit, company_codes=effective_codes, major_category=major_category,
        end_month=end_month,
    )
    return _ok(codes)


@router.get("/top/trends", summary="批量获取TOP N物料的单价趋势（合并接口）")
def get_top_material_trends(
    limit: int = Query(20, ge=1, le=30),
    months: int = Query(13, ge=1, le=36),
    company_codes: Optional[List[str]] = Query(None),
    major_category: Optional[str] = Query(None),
    end_month: Optional[str] = Query(None, description="截止月份 YYYY-MM"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """一次性返回 TOP N 物料的趋势数据，减少前端请求数"""
    effective_codes = get_effective_company_codes(current_user, company_codes, db)
    svc = PriceTrendService(db)
    codes = svc.get_top_materials_for_trend(
        limit=limit, company_codes=effective_codes, major_category=major_category,
        end_month=end_month,
    )
    trends = []
    for code in codes:
        trend = svc.get_material_price_trend(
            code, months=months,
            company_codes=effective_codes, major_category=major_category,
            end_month=end_month,
        )
        if "error" not in trend:
            trends.append(trend)
    return _ok(trends)


@router.get("/search", summary="搜索物料（按编码或名称模糊匹配）")
def search_materials(
    keyword: str = Query(..., min_length=1, description="搜索关键词"),
    limit: int = Query(20, ge=1, le=50),
    company_codes: Optional[List[str]] = Query(None),
    major_category: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    effective_codes = get_effective_company_codes(current_user, company_codes, db)
    svc = PriceTrendService(db)
    results = svc.search_materials(
        keyword, limit=limit, company_codes=effective_codes, major_category=major_category,
    )
    return _ok(results)
