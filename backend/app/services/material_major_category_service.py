"""
物料大类维护服务
按 (company_code, material_code) 唯一维护物料的大类分类
"""
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import Optional, List, Tuple
from ..models import MaterialMajorCategory
from ..schemas import MaterialMajorCategoryCreate, MaterialMajorCategoryUpdate


def list_categories(
    db: Session,
    company_code: Optional[str] = None,
    material_code: Optional[str] = None,
    major_category: Optional[str] = None,
    keyword: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[List[MaterialMajorCategory], int]:
    """分页查询物料大类维护记录"""
    q = db.query(MaterialMajorCategory)
    if company_code:
        q = q.filter(MaterialMajorCategory.company_code == company_code)
    if material_code:
        q = q.filter(MaterialMajorCategory.material_code == material_code)
    if major_category:
        q = q.filter(MaterialMajorCategory.major_category == major_category)
    if keyword:
        pattern = f"%{keyword}%"
        q = q.filter(
            (MaterialMajorCategory.material_code.ilike(pattern))
            | (MaterialMajorCategory.material_name.ilike(pattern))
            | (MaterialMajorCategory.major_category.ilike(pattern))
        )
    total = q.count()
    items = (
        q.order_by(
            MaterialMajorCategory.company_code,
            MaterialMajorCategory.material_code,
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def get_category(db: Session, id_: int) -> Optional[MaterialMajorCategory]:
    return db.query(MaterialMajorCategory).filter(MaterialMajorCategory.id == id_).first()


def create_category(db: Session, data: MaterialMajorCategoryCreate) -> MaterialMajorCategory:
    obj = MaterialMajorCategory(**data.model_dump())
    db.add(obj)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValueError(f"公司 {data.company_code} 下物料 {data.material_code} 已存在大类维护记录，请勿重复添加")
    db.refresh(obj)
    return obj


def update_category(db: Session, id_: int, data: MaterialMajorCategoryUpdate) -> Optional[MaterialMajorCategory]:
    obj = get_category(db, id_)
    if not obj:
        return None
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


def delete_category(db: Session, id_: int) -> bool:
    obj = get_category(db, id_)
    if not obj:
        return False
    db.delete(obj)
    db.commit()
    return True


def list_major_categories(db: Session, company_code: Optional[str] = None) -> List[str]:
    """返回所有不重复的物料大类（用于全局筛选器下拉）"""
    q = db.query(MaterialMajorCategory.major_category).distinct()
    if company_code:
        q = q.filter(MaterialMajorCategory.company_code == company_code)
    return sorted([r[0] for r in q.all() if r[0]])


def get_material_major_category(db: Session, company_code: str, material_code: str) -> Optional[str]:
    """获取指定公司+物料的大类"""
    row = (
        db.query(MaterialMajorCategory.major_category)
        .filter(
            MaterialMajorCategory.company_code == company_code,
            MaterialMajorCategory.material_code == material_code,
        )
        .first()
    )
    return row[0] if row else None
