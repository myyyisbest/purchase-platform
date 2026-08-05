"""
Pydantic验证模型
用于请求和响应的数据验证

组织层级：集团(Group) → 事业部(BusinessUnit) → 板块(BusinessSector) → 公司(Company)
"""
from pydantic import BaseModel, Field, model_validator
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List


# ============================================
# 集团相关Schema
# ============================================
class GroupBase(BaseModel):
    group_code: str = Field(..., description="集团代码")
    group_name: str = Field(..., description="集团名称")
    description: Optional[str] = None


class GroupCreate(GroupBase):
    pass


class GroupUpdate(BaseModel):
    group_name: Optional[str] = None
    description: Optional[str] = None


class GroupResponse(GroupBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============================================
# 事业部相关Schema
# ============================================
class BusinessUnitBase(BaseModel):
    unit_code: str = Field(..., description="事业部代码")
    unit_name: str = Field(..., description="事业部名称")
    group_id: int = Field(..., description="所属集团ID")
    description: Optional[str] = None


class BusinessUnitCreate(BusinessUnitBase):
    pass


class BusinessUnitUpdate(BaseModel):
    unit_name: Optional[str] = None
    group_id: Optional[int] = None
    description: Optional[str] = None


class BusinessUnitResponse(BusinessUnitBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============================================
# 板块相关Schema
# ============================================
class BusinessSectorBase(BaseModel):
    sector_code: str = Field(..., description="板块代码")
    sector_name: str = Field(..., description="板块名称")
    unit_id: int = Field(..., description="所属事业部ID")
    description: Optional[str] = None


class BusinessSectorCreate(BusinessSectorBase):
    pass


class BusinessSectorUpdate(BaseModel):
    sector_name: Optional[str] = None
    unit_id: Optional[int] = None
    description: Optional[str] = None


class BusinessSectorResponse(BusinessSectorBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============================================
# 公司相关Schema
# ============================================
class CompanyBase(BaseModel):
    company_code: str = Field(..., description="公司代码")
    company_name: str = Field(..., description="公司名称")
    sector_id: int = Field(..., description="所属板块ID")
    tax_number: Optional[str] = None
    address: Optional[str] = None
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    description: Optional[str] = None


class CompanyCreate(CompanyBase):
    pass


class CompanyUpdate(BaseModel):
    company_name: Optional[str] = None
    sector_id: Optional[int] = None
    tax_number: Optional[str] = None
    address: Optional[str] = None
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    description: Optional[str] = None


class CompanyResponse(CompanyBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============================================
# 组织架构树形Schema
# ============================================
class CompanyTreeNode(BaseModel):
    """公司节点（叶子节点）"""
    id: int
    code: str
    name: str
    sector_id: int


class SectorTreeNode(BaseModel):
    """板块节点"""
    id: int
    code: str
    name: str
    unit_id: int
    companies: List[CompanyTreeNode] = []


class UnitTreeNode(BaseModel):
    """事业部节点"""
    id: int
    code: str
    name: str
    group_id: int
    sectors: List[SectorTreeNode] = []


class GroupTreeNode(BaseModel):
    """集团节点（根节点）"""
    id: int
    code: str
    name: str
    units: List[UnitTreeNode] = []


class OrgTreeResponse(BaseModel):
    """完整组织架构树"""
    groups: List[GroupTreeNode]

# ============================================
# 供应商相关Schema
# ============================================
class SupplierBase(BaseModel):
    supplier_code: str
    supplier_name: str
    category: Optional[str] = None
    risk_level: Optional[str] = None
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    description: Optional[str] = None

class SupplierCreate(SupplierBase):
    pass

class SupplierUpdate(BaseModel):
    supplier_name: Optional[str] = None
    category: Optional[str] = None
    risk_level: Optional[str] = None
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    description: Optional[str] = None

class SupplierResponse(SupplierBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# ============================================
# 物料相关Schema
# ============================================
class MaterialBase(BaseModel):
    material_code: str
    material_name: str
    category: Optional[str] = None
    subcategory: Optional[str] = None
    specification: Optional[str] = None
    unit: Optional[str] = None
    description: Optional[str] = None

class MaterialCreate(MaterialBase):
    pass

class MaterialUpdate(BaseModel):
    material_name: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    specification: Optional[str] = None
    unit: Optional[str] = None
    description: Optional[str] = None

class MaterialResponse(MaterialBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# ============================================
# 汇率相关Schema（区间有效期模型）
# ============================================
class ExchangeRateBase(BaseModel):
    from_currency: str = Field(..., description="源货币")
    to_currency: str = Field(default="CNY", description="目标货币")
    effective_date: date = Field(..., description="生效日期")
    expiry_date: Optional[date] = Field(None, description="失效日期（NULL=永久生效）")
    exchange_rate: Decimal = Field(..., description="汇率")
    source: Optional[str] = None
    description: Optional[str] = None

    @model_validator(mode='after')
    def check_date_range(self):
        """生效日期必须早于失效日期（若失效日期非空）"""
        if self.expiry_date and self.effective_date >= self.expiry_date:
            raise ValueError("生效日期必须早于失效日期")
        return self


class ExchangeRateCreate(ExchangeRateBase):
    pass


class ExchangeRateUpdate(BaseModel):
    effective_date: Optional[date] = None
    expiry_date: Optional[date] = None
    exchange_rate: Optional[Decimal] = None
    source: Optional[str] = None
    description: Optional[str] = None

    @model_validator(mode='after')
    def check_date_range(self):
        """更新时也校验区间合法性（仅当两个字段都传了）"""
        if self.effective_date and self.expiry_date and self.effective_date >= self.expiry_date:
            raise ValueError("生效日期必须早于失效日期")
        return self


class ExchangeRateResponse(ExchangeRateBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# ============================================
# 采购记录相关Schema
# ============================================
class PurchaseRecordBase(BaseModel):
    company_code: Optional[str] = None
    company_name: Optional[str] = None
    fiscal_year: Optional[int] = None
    transaction_date: Optional[date] = None
    supplier_code: Optional[str] = None
    supplier_name: Optional[str] = None
    supplier_category: Optional[str] = None
    material_code: Optional[str] = None
    material_name: Optional[str] = None
    specification: Optional[str] = None
    material_category: Optional[str] = None
    base_currency: Optional[str] = "CNY"
    unit: Optional[str] = None
    quantity: Optional[Decimal] = None
    unit_price: Optional[Decimal] = None
    amount: Optional[Decimal] = None
    order_currency: Optional[str] = None
    order_unit_price: Optional[Decimal] = None
    order_amount: Optional[Decimal] = None
    exchange_rate: Optional[Decimal] = None
    cny_amount: Optional[Decimal] = None

class PurchaseRecordCreate(PurchaseRecordBase):
    pass

class PurchaseRecordResponse(PurchaseRecordBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# ============================================
# 用户相关Schema
# ============================================
class UserBase(BaseModel):
    username: str
    real_name: Optional[str] = None
    email: Optional[str] = None
    role: str = "user"
    company_id: Optional[int] = None

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    real_name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    company_id: Optional[int] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None

class UserResponse(UserBase):
    id: int
    is_active: Optional[bool] = True
    must_change_password: Optional[bool] = False
    company_codes: Optional[List[str]] = []  # 授权公司代码列表
    last_login: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============================================
# 认证相关Schema
# ============================================
class LoginRequest(BaseModel):
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., description="旧密码")
    new_password: str = Field(..., description="新密码（至少8位，含字母和数字）", min_length=8)


# ============================================
# 用户管理相关Schema
# ============================================
class UserCreateRequest(BaseModel):
    username: str = Field(..., description="用户名")
    real_name: Optional[str] = None
    email: Optional[str] = None
    role: str = Field("user", description="角色: admin/user")
    password: Optional[str] = Field(None, description="初始密码，留空则用默认值")
    company_codes: Optional[List[str]] = Field([], description="授权公司代码列表")


class UserEditRequest(BaseModel):
    real_name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    company_codes: Optional[List[str]] = None


class UserCompanyAccessUpdate(BaseModel):
    company_codes: List[str] = Field(..., description="授权的公司代码列表")


# ============================================
# 物料大类维护相关 Schema
# ============================================
class MaterialMajorCategoryBase(BaseModel):
    company_code: str = Field(..., description="公司代码")
    material_code: str = Field(..., description="物料编码")
    material_name: Optional[str] = Field('', description="物料名称")
    major_category: str = Field(..., description="物料大类")


class MaterialMajorCategoryCreate(MaterialMajorCategoryBase):
    pass


class MaterialMajorCategoryUpdate(BaseModel):
    material_name: Optional[str] = None
    major_category: Optional[str] = None


class MaterialMajorCategoryResponse(MaterialMajorCategoryBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# ============================================
# 通用响应Schema
# ============================================
class ResponseModel(BaseModel):
    code: int = 200
    message: str = "成功"
    data: Optional[object] = None

class PageResponseModel(BaseModel):
    code: int = 200
    message: str = "成功"
    data: Optional[List[object]] = None
    total: int = 0
    page: int = 1
    page_size: int = 20
