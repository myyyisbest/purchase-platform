"""
组织架构服务
支持 集团 → 事业部 → 板块 → 公司 四层CRUD和树形查询
"""
from sqlalchemy.orm import Session
from ..models import Group, BusinessUnit, BusinessSector, Company
from ..schemas import (
    GroupCreate, GroupUpdate,
    BusinessUnitCreate, BusinessUnitUpdate,
    BusinessSectorCreate, BusinessSectorUpdate,
    CompanyCreate, CompanyUpdate,
    GroupTreeNode, UnitTreeNode, SectorTreeNode, CompanyTreeNode,
)
from typing import List, Optional


# ============================================
# 树形查询
# ============================================
def get_org_tree(db: Session) -> List[GroupTreeNode]:
    """获取完整组织架构树"""
    groups = db.query(Group).all()
    result = []
    for g in groups:
        units = db.query(BusinessUnit).filter(BusinessUnit.group_id == g.id).all()
        unit_nodes = []
        for u in units:
            sectors = db.query(BusinessSector).filter(BusinessSector.unit_id == u.id).all()
            sector_nodes = []
            for s in sectors:
                companies = db.query(Company).filter(Company.sector_id == s.id).all()
                company_nodes = [
                    CompanyTreeNode(id=c.id, code=c.company_code, name=c.company_name, sector_id=c.sector_id)
                    for c in companies
                ]
                sector_nodes.append(SectorTreeNode(
                    id=s.id, code=s.sector_code, name=s.sector_name,
                    unit_id=s.unit_id, companies=company_nodes
                ))
            unit_nodes.append(UnitTreeNode(
                id=u.id, code=u.unit_code, name=u.unit_name,
                group_id=u.group_id, sectors=sector_nodes
            ))
        result.append(GroupTreeNode(
            id=g.id, code=g.group_code, name=g.group_name, units=unit_nodes
        ))
    return result


# ============================================
# 集团 CRUD
# ============================================
def get_groups(db: Session) -> List[Group]:
    return db.query(Group).order_by(Group.id).all()


def get_group(db: Session, group_id: int) -> Optional[Group]:
    return db.query(Group).filter(Group.id == group_id).first()


def create_group(db: Session, data: GroupCreate) -> Group:
    obj = Group(**data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_group(db: Session, group_id: int, data: GroupUpdate) -> Optional[Group]:
    obj = get_group(db, group_id)
    if not obj:
        return None
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


def delete_group(db: Session, group_id: int) -> bool:
    obj = get_group(db, group_id)
    if not obj:
        return False
    # 检查是否有下属事业部
    child_count = db.query(BusinessUnit).filter(BusinessUnit.group_id == group_id).count()
    if child_count > 0:
        return False
    db.delete(obj)
    db.commit()
    return True


# ============================================
# 事业部 CRUD
# ============================================
def get_units(db: Session, group_id: Optional[int] = None) -> List[BusinessUnit]:
    q = db.query(BusinessUnit)
    if group_id:
        q = q.filter(BusinessUnit.group_id == group_id)
    return q.order_by(BusinessUnit.id).all()


def get_unit(db: Session, unit_id: int) -> Optional[BusinessUnit]:
    return db.query(BusinessUnit).filter(BusinessUnit.id == unit_id).first()


def create_unit(db: Session, data: BusinessUnitCreate) -> BusinessUnit:
    obj = BusinessUnit(**data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_unit(db: Session, unit_id: int, data: BusinessUnitUpdate) -> Optional[BusinessUnit]:
    obj = get_unit(db, unit_id)
    if not obj:
        return None
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


def delete_unit(db: Session, unit_id: int) -> bool:
    obj = get_unit(db, unit_id)
    if not obj:
        return False
    child_count = db.query(BusinessSector).filter(BusinessSector.unit_id == unit_id).count()
    if child_count > 0:
        return False
    db.delete(obj)
    db.commit()
    return True


# ============================================
# 板块 CRUD
# ============================================
def get_sectors(db: Session, unit_id: Optional[int] = None) -> List[BusinessSector]:
    q = db.query(BusinessSector)
    if unit_id:
        q = q.filter(BusinessSector.unit_id == unit_id)
    return q.order_by(BusinessSector.id).all()


def get_sector(db: Session, sector_id: int) -> Optional[BusinessSector]:
    return db.query(BusinessSector).filter(BusinessSector.id == sector_id).first()


def create_sector(db: Session, data: BusinessSectorCreate) -> BusinessSector:
    obj = BusinessSector(**data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_sector(db: Session, sector_id: int, data: BusinessSectorUpdate) -> Optional[BusinessSector]:
    obj = get_sector(db, sector_id)
    if not obj:
        return None
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


def delete_sector(db: Session, sector_id: int) -> bool:
    obj = get_sector(db, sector_id)
    if not obj:
        return False
    child_count = db.query(Company).filter(Company.sector_id == sector_id).count()
    if child_count > 0:
        return False
    db.delete(obj)
    db.commit()
    return True


# ============================================
# 公司 CRUD
# ============================================
def get_companies(db: Session, sector_id: Optional[int] = None) -> List[Company]:
    q = db.query(Company)
    if sector_id:
        q = q.filter(Company.sector_id == sector_id)
    return q.order_by(Company.id).all()


def get_company(db: Session, company_id: int) -> Optional[Company]:
    return db.query(Company).filter(Company.id == company_id).first()


def create_company(db: Session, data: CompanyCreate) -> Company:
    obj = Company(**data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_company(db: Session, company_id: int, data: CompanyUpdate) -> Optional[Company]:
    obj = get_company(db, company_id)
    if not obj:
        return None
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


def delete_company(db: Session, company_id: int) -> bool:
    obj = get_company(db, company_id)
    if not obj:
        return False
    db.delete(obj)
    db.commit()
    return True
