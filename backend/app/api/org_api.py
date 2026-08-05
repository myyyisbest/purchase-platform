"""
组织架构管理API
支持 集团 → 事业部 → 板块 → 公司 四层CRUD和树形查询

鉴权策略：
- GET（读）：所有登录用户可访问（用于筛选器/导航）
- POST/PUT/DELETE（写）：仅 admin
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from ..database import get_db
from ..auth import get_current_user, require_admin
from ..models import User
from ..services import org_service
from ..schemas import (
    GroupCreate, GroupUpdate, GroupResponse,
    BusinessUnitCreate, BusinessUnitUpdate, BusinessUnitResponse,
    BusinessSectorCreate, BusinessSectorUpdate, BusinessSectorResponse,
    CompanyCreate, CompanyUpdate, CompanyResponse,
    OrgTreeResponse,
)

router = APIRouter()


def _ok(data=None, message="成功"):
    return {"code": 200, "message": message, "data": data}


# ============================================
# 组织架构树（读，所有登录用户）
# ============================================
@router.get("/tree", summary="获取完整组织架构树")
def get_org_tree(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tree = org_service.get_org_tree(db)
    return _ok([t.model_dump() for t in tree])


# ============================================
# 集团 CRUD
# ============================================
@router.get("/groups", summary="获取集团列表")
def list_groups(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items = org_service.get_groups(db)
    return _ok([GroupResponse.model_validate(i).model_dump() for i in items])


@router.get("/groups/{group_id}", summary="获取集团详情")
def get_group(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = org_service.get_group(db, group_id)
    if not item:
        raise HTTPException(404, "集团不存在")
    return _ok(GroupResponse.model_validate(item).model_dump())


@router.post("/groups", summary="创建集团")
def create_group(
    data: GroupCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    try:
        item = org_service.create_group(db, data)
        return _ok(GroupResponse.model_validate(item).model_dump())
    except Exception as e:
        raise HTTPException(400, f"创建失败: {str(e)}")


@router.put("/groups/{group_id}", summary="更新集团")
def update_group(
    group_id: int,
    data: GroupUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    item = org_service.update_group(db, group_id, data)
    if not item:
        raise HTTPException(404, "集团不存在")
    return _ok(GroupResponse.model_validate(item).model_dump())


@router.delete("/groups/{group_id}", summary="删除集团")
def delete_group(
    group_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    ok = org_service.delete_group(db, group_id)
    if not ok:
        raise HTTPException(400, "删除失败：集团不存在或仍有下属事业部")
    return _ok(message="删除成功")


# ============================================
# 事业部 CRUD
# ============================================
@router.get("/units", summary="获取事业部列表")
def list_units(
    group_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items = org_service.get_units(db, group_id)
    return _ok([BusinessUnitResponse.model_validate(i).model_dump() for i in items])


@router.get("/units/{unit_id}", summary="获取事业部详情")
def get_unit(
    unit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = org_service.get_unit(db, unit_id)
    if not item:
        raise HTTPException(404, "事业部不存在")
    return _ok(BusinessUnitResponse.model_validate(item).model_dump())


@router.post("/units", summary="创建事业部")
def create_unit(
    data: BusinessUnitCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    try:
        item = org_service.create_unit(db, data)
        return _ok(BusinessUnitResponse.model_validate(item).model_dump())
    except Exception as e:
        raise HTTPException(400, f"创建失败: {str(e)}")


@router.put("/units/{unit_id}", summary="更新事业部")
def update_unit(
    unit_id: int,
    data: BusinessUnitUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    item = org_service.update_unit(db, unit_id, data)
    if not item:
        raise HTTPException(404, "事业部不存在")
    return _ok(BusinessUnitResponse.model_validate(item).model_dump())


@router.delete("/units/{unit_id}", summary="删除事业部")
def delete_unit(
    unit_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    ok = org_service.delete_unit(db, unit_id)
    if not ok:
        raise HTTPException(400, "删除失败：事业部不存在或仍有下属板块")
    return _ok(message="删除成功")


# ============================================
# 板块 CRUD
# ============================================
@router.get("/sectors", summary="获取板块列表")
def list_sectors(
    unit_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items = org_service.get_sectors(db, unit_id)
    return _ok([BusinessSectorResponse.model_validate(i).model_dump() for i in items])


@router.get("/sectors/{sector_id}", summary="获取板块详情")
def get_sector(
    sector_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = org_service.get_sector(db, sector_id)
    if not item:
        raise HTTPException(404, "板块不存在")
    return _ok(BusinessSectorResponse.model_validate(item).model_dump())


@router.post("/sectors", summary="创建板块")
def create_sector(
    data: BusinessSectorCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    try:
        item = org_service.create_sector(db, data)
        return _ok(BusinessSectorResponse.model_validate(item).model_dump())
    except Exception as e:
        raise HTTPException(400, f"创建失败: {str(e)}")


@router.put("/sectors/{sector_id}", summary="更新板块")
def update_sector(
    sector_id: int,
    data: BusinessSectorUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    item = org_service.update_sector(db, sector_id, data)
    if not item:
        raise HTTPException(404, "板块不存在")
    return _ok(BusinessSectorResponse.model_validate(item).model_dump())


@router.delete("/sectors/{sector_id}", summary="删除板块")
def delete_sector(
    sector_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    ok = org_service.delete_sector(db, sector_id)
    if not ok:
        raise HTTPException(400, "删除失败：板块不存在或仍有下属公司")
    return _ok(message="删除成功")


# ============================================
# 公司 CRUD
# ============================================
@router.get("/companies", summary="获取公司列表")
def list_companies(
    sector_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items = org_service.get_companies(db, sector_id)
    return _ok([CompanyResponse.model_validate(i).model_dump() for i in items])


@router.get("/companies/{company_id}", summary="获取公司详情")
def get_company(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = org_service.get_company(db, company_id)
    if not item:
        raise HTTPException(404, "公司不存在")
    return _ok(CompanyResponse.model_validate(item).model_dump())


@router.post("/companies", summary="创建公司")
def create_company(
    data: CompanyCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    try:
        item = org_service.create_company(db, data)
        return _ok(CompanyResponse.model_validate(item).model_dump())
    except Exception as e:
        raise HTTPException(400, f"创建失败: {str(e)}")


@router.put("/companies/{company_id}", summary="更新公司")
def update_company(
    company_id: int,
    data: CompanyUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    item = org_service.update_company(db, company_id, data)
    if not item:
        raise HTTPException(404, "公司不存在")
    return _ok(CompanyResponse.model_validate(item).model_dump())


@router.delete("/companies/{company_id}", summary="删除公司")
def delete_company(
    company_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    ok = org_service.delete_company(db, company_id)
    if not ok:
        raise HTTPException(400, "删除失败：公司不存在")
    return _ok(message="删除成功")


@router.get("/hierarchy", summary="获取组织架构层级数据（用于全局筛选器）")
def get_org_hierarchy(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """返回集团→事业部→板块→公司四层完整树形结构，供筛选器级联使用"""
    from ..models import Group, BusinessUnit, BusinessSector, Company

    groups = db.query(Group).order_by(Group.group_name).all()
    result = []
    for g in groups:
        g_item = {
            "id": g.id, "code": g.group_code, "name": g.group_name,
            "units": []
        }
        units = db.query(BusinessUnit).filter(BusinessUnit.group_id == g.id).order_by(BusinessUnit.unit_name).all()
        for u in units:
            u_item = {
                "id": u.id, "code": u.unit_code, "name": u.unit_name,
                "sectors": []
            }
            sectors = db.query(BusinessSector).filter(BusinessSector.unit_id == u.id).order_by(BusinessSector.sector_name).all()
            for s in sectors:
                s_item = {
                    "id": s.id, "code": s.sector_code, "name": s.sector_name,
                    "companies": []
                }
                companies = db.query(Company).filter(Company.sector_id == s.id).order_by(Company.company_name).all()
                for c in companies:
                    s_item["companies"].append({
                        "id": c.id, "code": c.company_code, "name": c.company_name
                    })
                u_item["sectors"].append(s_item)
            g_item["units"].append(u_item)
        result.append(g_item)
    return _ok(result)
