"""
SQLAlchemy模型定义
对应PostgreSQL数据库表结构

组织层级：集团(Group) → 事业部(BusinessUnit) → 板块(BusinessSector) → 公司(Company)
"""
from sqlalchemy import Column, Integer, String, Text, DECIMAL, Date, DateTime, Boolean, ForeignKey, Float, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base


class Group(Base):
    """集团表 - 顶层组织"""
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, index=True)
    group_code = Column(String(20), unique=True, nullable=False, index=True)
    group_name = Column(String(100), nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    units = relationship("BusinessUnit", back_populates="group", lazy="select")


class BusinessUnit(Base):
    """事业部表 - 隶属于集团"""
    __tablename__ = "business_units"

    id = Column(Integer, primary_key=True, index=True)
    unit_code = Column(String(20), unique=True, nullable=False, index=True)
    unit_name = Column(String(100), nullable=False)
    group_id = Column(Integer, ForeignKey("groups.id"))
    description = Column(Text)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    group = relationship("Group", back_populates="units")
    sectors = relationship("BusinessSector", back_populates="unit", lazy="select")


class BusinessSector(Base):
    """板块表 - 隶属于事业部"""
    __tablename__ = "business_sectors"

    id = Column(Integer, primary_key=True, index=True)
    sector_code = Column(String(20), unique=True, nullable=False, index=True)
    sector_name = Column(String(100), nullable=False)
    unit_id = Column(Integer, ForeignKey("business_units.id"))
    description = Column(Text)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    unit = relationship("BusinessUnit", back_populates="sectors")
    companies = relationship("Company", back_populates="sector", lazy="select")


class Company(Base):
    """公司表 - 隶属于板块"""
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    company_code = Column(String(20), unique=True, nullable=False, index=True)
    company_name = Column(String(200), nullable=False)
    sector_id = Column(Integer, ForeignKey("business_sectors.id"))
    tax_number = Column(String(50))
    address = Column(Text)
    contact_person = Column(String(100))
    contact_phone = Column(String(50))
    description = Column(Text)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    sector = relationship("BusinessSector", back_populates="companies")

class Supplier(Base):
    """供应商表"""
    __tablename__ = "suppliers"
    
    id = Column(Integer, primary_key=True, index=True)
    supplier_code = Column(String(50), unique=True, nullable=False, index=True)
    supplier_name = Column(String(200), nullable=False)
    category = Column(String(20))  # 关联方/非关联方
    risk_level = Column(String(20))
    contact_person = Column(String(100))
    contact_phone = Column(String(50))
    email = Column(String(100))
    address = Column(Text)
    description = Column(Text)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

class Material(Base):
    """物料表"""
    __tablename__ = "materials"
    
    id = Column(Integer, primary_key=True, index=True)
    material_code = Column(String(50), unique=True, nullable=False, index=True)
    material_name = Column(String(200), nullable=False)
    category = Column(String(50))
    subcategory = Column(String(50))
    specification = Column(Text)
    unit = Column(String(20))
    description = Column(Text)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

class ExchangeRate(Base):
    """汇率表 - 区间有效期模型，每条覆盖 [effective_date, expiry_date]"""
    __tablename__ = "exchange_rates"

    id = Column(Integer, primary_key=True, index=True)
    from_currency = Column(String(10), nullable=False, index=True)
    to_currency = Column(String(10), nullable=False, default='CNY')
    effective_date = Column(Date, nullable=False, index=True)
    expiry_date = Column(Date, index=True)  # 失效日期（NULL=永久生效）
    exchange_rate = Column(DECIMAL(18, 6), nullable=False)
    source = Column(String(50))
    description = Column(Text)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # 兼容 PostgreSQL/MySQL：MySQL 无 schema 概念，仅在部署时通过环境变量中 DB_TYPE 区分
    __table_args__ = ()

class PurchaseRecord(Base):
    """采购记录表"""
    __tablename__ = "purchase_records"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # 公司信息
    company_id = Column(Integer, ForeignKey("companies.id"), index=True)
    company_code = Column(String(20))
    company_name = Column(String(200))
    
    # 时间信息
    fiscal_year = Column(Integer, index=True)
    transaction_date = Column(Date, index=True)
    
    # 供应商信息
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), index=True)
    supplier_code = Column(String(50))
    supplier_name = Column(String(200))
    supplier_category = Column(String(20))
    
    # 物料信息
    material_id = Column(Integer, ForeignKey("materials.id"), index=True)
    material_code = Column(String(50))
    material_name = Column(String(200))
    specification = Column(String(200))
    material_category = Column(String(50))
    wgbez = Column(String(200), default='')  # WGBEZ 物料组描述（中文名）
    
    # 采购信息（本位币）
    base_currency = Column(String(10), default='CNY')
    unit = Column(String(20))
    quantity = Column(DECIMAL(18, 4))  # 采购数量
    unit_price = Column(DECIMAL(18, 4))  # 采购单价（本位币）
    amount = Column(DECIMAL(18, 2))  # 采购金额（本位币）
    
    # 订单货币信息
    order_currency = Column(String(10), index=True)  # 订单货币
    order_unit_price = Column(DECIMAL(18, 4))  # 单价(订单货币)
    order_amount = Column(DECIMAL(18, 2))  # 金额(订单货币)
    
    # 汇率转换后的金额（核心字段）
    exchange_rate = Column(DECIMAL(18, 6))  # 汇率
    cny_amount = Column(DECIMAL(18, 2))  # 采购金额(CNY换算后)
    
    # 发票信息
    invoice_quantity = Column(DECIMAL(18, 4))
    invoice_unit_price = Column(DECIMAL(18, 4))
    invoice_amount = Column(DECIMAL(18, 2))
    invoice_tax = Column(DECIMAL(18, 2))
    invoice_total = Column(DECIMAL(18, 2))
    invoice_date = Column(Date)
    
    # 暂估信息
    estimate_quantity = Column(DECIMAL(18, 4))
    estimate_total = Column(DECIMAL(18, 2))
    estimate_amount = Column(DECIMAL(18, 2))
    
    # 其他信息
    purchase_purpose = Column(String(50))
    po_number = Column(String(50))
    material_doc = Column(String(50))
    line_item = Column(String(20))
    accounting_doc = Column(String(50))
    movement_type = Column(String(10))
    movement_type_desc = Column(String(100))
    reversal_flag = Column(String(10))
    line_item_category = Column(String(20))
    gr_based_invoice = Column(String(10))
    line_item_text = Column(Text)
    
    # 系统字段
    data_source = Column(String(50))
    import_batch_id = Column(String(50))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    # 软删除字段：NULL=正常有效；非 NULL=HANA 视图已删除/冲销，业务侧应过滤
    deleted_at = Column(DateTime, index=True)

class User(Base):
    """用户表"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    real_name = Column(String(100))
    email = Column(String(100))
    role = Column(String(20), nullable=False, default='user')  # admin/user
    company_id = Column(Integer, ForeignKey("companies.id"))  # 普通用户所属公司（保留兼容）
    is_active = Column(Boolean, default=True)
    must_change_password = Column(Boolean, default=False)  # 首次登录强制改密
    last_login = Column(DateTime)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class UserCompanyAccess(Base):
    """用户-公司访问权限表（多对多）"""
    __tablename__ = "user_company_access"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    company_code = Column(String(20), nullable=False, index=True)
    created_at = Column(DateTime, default=func.now())

    __table_args__ = (
        # 同一用户对同一公司只授权一次
    )


class MaterialMajorCategory(Base):
    """物料大类维护表
    按 (company_code, material_code) 唯一，维护一个物料在某公司下的大类分类
    """
    __tablename__ = "material_major_categories"

    id = Column(Integer, primary_key=True, index=True)
    company_code = Column(String(20), nullable=False, index=True)
    material_code = Column(String(50), nullable=False, index=True)
    material_name = Column(String(200), nullable=False, default='')
    major_category = Column(String(100), nullable=False, index=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class AuditLog(Base):
    """操作审计日志表：记录关键写操作（POST/PUT/DELETE），用于安全审计与追溯"""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)          # 操作者ID（未登录= NULL）
    username = Column(String(50))                   # 操作者用户名（冗余，便于直接查阅）
    method = Column(String(10), nullable=False)     # HTTP 方法
    path = Column(String(500), nullable=False)      # 请求路径
    status_code = Column(Integer)                   # 响应状态码
    client_ip = Column(String(50))                  # 客户端IP
    body_summary = Column(Text)                     # 请求体摘要（截断，防止超长）
    cost_ms = Column(Integer)                       # 请求耗时（毫秒）
    created_at = Column(DateTime, default=func.now(), index=True)


class HanaSyncState(Base):
    """HANA 同步状态记录表，记录每次同步的水位和统计"""
    __tablename__ = "hana_sync_state"

    id = Column(Integer, primary_key=True, index=True)
    sync_type = Column(String(20), nullable=False, default='full')  # full / incremental
    last_sync_at = Column(DateTime, nullable=False, default=func.now())
    last_batch_id = Column(String(50))
    total_hana_rows = Column(Integer, default=0)
    total_inserted = Column(Integer, default=0)
    total_updated = Column(Integer, default=0)
    total_deleted = Column(Integer, default=0)
    status = Column(String(20), default='completed')    # running / completed / failed
    error_message = Column(Text)
    created_at = Column(DateTime, default=func.now())


class PurchaseRecordOrigin(Base):
    """HANA 原始数据表 - 存储 HANA 视图的原始行，不做任何类型转换"""
    __tablename__ = "purchase_records_origin"

    id = Column(Integer, primary_key=True, index=True)
    import_batch_id = Column(String(50), nullable=False, default='')

    # HANA 视图原始字段（全部 VARCHAR，列名小写匹配 PG）
    gjahr      = Column(String(10), default='')
    budat      = Column(String(10), default='')
    groes      = Column(String(200), default='')
    matl_group = Column(String(50), default='')
    waers      = Column(String(10), default='')
    zddhb      = Column(String(10), default='')
    erfme      = Column(String(20), default='')
    erfmg      = Column(String(50), default='')
    zdj_ddhb   = Column(String(50), default='')
    zje_ddhb   = Column(String(50), default='')
    price_po   = Column(String(50), default='')
    dmbtr      = Column(String(50), default='')
    price_iv   = Column(String(50), default='')
    wrbtr      = Column(String(50), default='')
    budat_iv   = Column(String(10), default='')
    menge_es   = Column(String(50), default='')
    wrbtr_es   = Column(String(50), default='')
    zgze       = Column(String(50), default='')
    purpose    = Column(String(50), default='')
    mblnr      = Column(String(50), default='')
    zeile      = Column(String(20), default='')
    ebeln      = Column(String(50), default='')
    bwart      = Column(String(10), default='')
    btext      = Column(String(100), default='')
    rev        = Column(String(10), default='')
    pstyp      = Column(String(20), default='')
    webre      = Column(String(10), default='')
    remark     = Column(Text, default='')

    # 额外手动取值的字段
    vbund      = Column(String(20), default='')
    material   = Column(String(50), default='')
    matnr      = Column(String(50), default='')
    vendor     = Column(String(50), default='')
    lifnr      = Column(String(50), default='')
    name1      = Column(String(200), default='')
    maktx      = Column(String(200), default='')
    comp_code  = Column(String(20), default='')
    butxt      = Column(String(200), default='')

    # ── HANA 视图其余原始字段（动态同步后补齐，与 SELECT * 完全一致）──
    gn_r3_ssy  = Column(String(20), default='')   # GN_R3_SSY 源系统标识
    recordmode = Column(String(10), default='')   # RECORDMODE 增量记录模式(N/U/D)
    calday     = Column(String(10), default='')   # CALDAY 日历日
    calmonth   = Column(String(10), default='')   # CALMONTH 日历月
    calmonth2  = Column(String(10), default='')   # CALMONTH2 日历月(fisc)
    calyear    = Column(String(10), default='')   # CALYEAR 日历年
    menge      = Column(String(50), default='')   # MENGE 订单数量（金额计算用此数量）
    zgcb       = Column(String(50), default='')   # ZGCB
    zghz       = Column(String(50), default='')   # ZGHZ
    wgbez      = Column(String(200), default='')  # WGBEZ 物料组描述
    solvent    = Column(String(50), default='')   # SOLVENT
    ebelnp     = Column(String(20), default='')   # EBELP 采购订单行项目号
    ernam      = Column(String(50), default='')   # ERNAM 创建人
    erdat      = Column(String(10), default='')   # ERDAT 创建日期
    erzet      = Column(String(10), default='')   # ERZET 创建时间
    aenam      = Column(String(50), default='')   # AENAM 修改人
    aedat      = Column(String(10), default='')   # AEDAT 修改日期
    aezet      = Column(String(10), default='')   # AEZET 修改时间

    created_at = Column(DateTime, default=func.now())


class AnomalyAlert(Base):
    """异常预警表：单源供应 / 单价波动等预警的生命周期记录"""
    __tablename__ = "anomaly_alerts"

    id = Column(Integer, primary_key=True, index=True)
    alert_type = Column(String(30), nullable=False, index=True)  # single_source | price_volatility
    fiscal_year = Column(Integer, nullable=False, index=True)
    material_code = Column(String(50), nullable=False, index=True)
    material_name = Column(String(200), default='')
    supplier_name = Column(String(200))
    currency = Column(String(10))
    company_scope = Column(Text)  # JSON 字符串：相关公司代码列表
    metric_value = Column(Float)
    threshold = Column(Float)
    severity = Column(String(10), default='medium')  # high | medium | low
    status = Column(String(20), nullable=False, default='open', index=True)  # open | acknowledged | resolved
    title = Column(String(300), nullable=False, default='')
    detail = Column(Text)  # JSON 或文本详情
    fingerprint = Column(String(200), unique=True, nullable=False, index=True)
    acknowledged_by = Column(String(50))
    acknowledged_at = Column(DateTime)
    resolved_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

