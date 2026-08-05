"""
公共 API 依赖与参数类型别名

设计目的：消除各 API 文件中重复的 Query 参数定义与 Depends 注入。
使用 FastAPI 0.100+ 的 Annotated 类型提示，在端点签名中直接引用类型别名即可。

用法示例：
    @router.get("/kpis")
    def get_kpis(
        fiscal_year: FiscalYear,
        company_codes: CompanyCodes,
        current_user: CurrentUser,
        db: DbSession,
    ): ...
"""
from typing import Annotated, Optional, List

from fastapi import Query, Depends
from sqlalchemy.orm import Session

from .database import get_db
from .models import User
from .auth import get_current_user, get_effective_company_codes

# ============ 通用查询参数（Annotated 别名，消除重复） ============

FiscalYear = Annotated[Optional[int], Query(description="财年，如2025")]
CompanyName = Annotated[Optional[str], Query(description="公司名称（精确匹配）")]
CompanyCodes = Annotated[Optional[List[str]], Query(description="公司代码列表（多选）")]
MaterialCode = Annotated[Optional[str], Query(description="物料编码（精确）")]
MaterialKeyword = Annotated[Optional[str], Query(description="物料编码/名称模糊搜索")]
MajorCategory = Annotated[Optional[str], Query(description="物料大类")]

# ============ 公共依赖注入 ============

CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[Session, Depends(get_db)]


def resolve_company_codes(
    current_user: CurrentUser,
    requested: CompanyCodes,
    db: DbSession,
) -> Optional[List[str]]:
    """计算用户有效公司过滤范围（admin 不限制，普通用户取授权交集）"""
    return get_effective_company_codes(current_user, requested, db)
