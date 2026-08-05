-- 采购分析平台数据库初始化脚本（幂等可重入）
-- 创建时间: 2026-06-17，最近合并: 2026-07-27
-- 组织层级：集团(Group) → 事业部(BusinessUnit) → 板块(BusinessSector) → 公司(Company)
-- 历史迁移（expiry_date/origin/soft_delete/users_auth/material_major_category）
-- 已全部并入本脚本，根目录不再保留独立 migration_*.sql 文件

-- ============================================
-- 1. 创建数据库（需要在外部执行）
-- CREATE DATABASE purchase_db;
-- ============================================

-- 连接到 purchase_db 后执行以下脚本

-- ============================================
-- 2. 创建集团表
-- ============================================
CREATE TABLE IF NOT EXISTS groups (
    id SERIAL PRIMARY KEY,
    group_code VARCHAR(20) UNIQUE NOT NULL,
    group_name VARCHAR(100) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE groups IS '集团表';
COMMENT ON COLUMN groups.group_code IS '集团代码';
COMMENT ON COLUMN groups.group_name IS '集团名称';

CREATE INDEX IF NOT EXISTS idx_groups_code ON groups(group_code);

-- ============================================
-- 3. 创建事业部表
-- ============================================
CREATE TABLE IF NOT EXISTS business_units (
    id SERIAL PRIMARY KEY,
    unit_code VARCHAR(20) UNIQUE NOT NULL,
    unit_name VARCHAR(100) NOT NULL,
    group_id INTEGER REFERENCES groups(id),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE business_units IS '事业部表';
COMMENT ON COLUMN business_units.unit_code IS '事业部代码';
COMMENT ON COLUMN business_units.unit_name IS '事业部名称';
COMMENT ON COLUMN business_units.group_id IS '所属集团ID';

CREATE INDEX IF NOT EXISTS idx_business_units_group ON business_units(group_id);

-- ============================================
-- 4. 创建板块表
-- ============================================
CREATE TABLE IF NOT EXISTS business_sectors (
    id SERIAL PRIMARY KEY,
    sector_code VARCHAR(20) UNIQUE NOT NULL,
    sector_name VARCHAR(100) NOT NULL,
    unit_id INTEGER REFERENCES business_units(id),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE business_sectors IS '板块表';
COMMENT ON COLUMN business_sectors.sector_code IS '板块代码';
COMMENT ON COLUMN business_sectors.sector_name IS '板块名称';
COMMENT ON COLUMN business_sectors.unit_id IS '所属事业部ID';

CREATE INDEX IF NOT EXISTS idx_business_sectors_unit ON business_sectors(unit_id);

-- ============================================
-- 5. 创建公司表
-- ============================================
CREATE TABLE IF NOT EXISTS companies (
    id SERIAL PRIMARY KEY,
    company_code VARCHAR(20) UNIQUE NOT NULL,
    company_name VARCHAR(200) NOT NULL,
    sector_id INTEGER REFERENCES business_sectors(id),
    tax_number VARCHAR(50),
    address TEXT,
    contact_person VARCHAR(100),
    contact_phone VARCHAR(50),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE companies IS '公司表';
COMMENT ON COLUMN companies.company_code IS '公司代码';
COMMENT ON COLUMN companies.company_name IS '公司名称';
COMMENT ON COLUMN companies.sector_id IS '所属板块ID';

CREATE INDEX IF NOT EXISTS idx_companies_sector ON companies(sector_id);

-- ============================================
-- 5. 创建供应商表
-- ============================================
CREATE TABLE IF NOT EXISTS suppliers (
    id SERIAL PRIMARY KEY,
    supplier_code VARCHAR(50) UNIQUE NOT NULL,
    supplier_name VARCHAR(200) NOT NULL,
    category VARCHAR(20),  -- 关联方/非关联方
    risk_level VARCHAR(20),  -- 风险等级
    contact_person VARCHAR(100),
    contact_phone VARCHAR(50),
    email VARCHAR(100),
    address TEXT,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE suppliers IS '供应商表';
COMMENT ON COLUMN suppliers.supplier_code IS '供应商编号';
COMMENT ON COLUMN suppliers.supplier_name IS '供应商名称';
COMMENT ON COLUMN suppliers.category IS '供应商类别（关联方/非关联方）';

-- ============================================
-- 6. 创建物料表
-- ============================================
CREATE TABLE IF NOT EXISTS materials (
    id SERIAL PRIMARY KEY,
    material_code VARCHAR(50) UNIQUE NOT NULL,
    material_name VARCHAR(200) NOT NULL,
    category VARCHAR(50),  -- 物料类别
    subcategory VARCHAR(50),
    specification TEXT,  -- 规格型号
    unit VARCHAR(20),  -- 默认单位
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE materials IS '物料表';
COMMENT ON COLUMN materials.material_code IS '物料代码';
COMMENT ON COLUMN materials.material_name IS '物料名称';
COMMENT ON COLUMN materials.category IS '物料类别（管件类、电仪类等）';

-- ============================================
-- 7. 创建汇率表
-- ============================================
CREATE TABLE IF NOT EXISTS exchange_rates (
    id SERIAL PRIMARY KEY,
    from_currency VARCHAR(10) NOT NULL,
    to_currency VARCHAR(10) NOT NULL DEFAULT 'CNY',
    effective_date DATE NOT NULL,
    expiry_date DATE,  -- 失效日期（NULL=永久生效；区间有效期模型）
    exchange_rate DECIMAL(18,6) NOT NULL,
    source VARCHAR(50),  -- 数据来源
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(from_currency, effective_date)
);

COMMENT ON TABLE exchange_rates IS '汇率表';
COMMENT ON COLUMN exchange_rates.from_currency IS '源货币（如USD、IDR）';
COMMENT ON COLUMN exchange_rates.to_currency IS '目标货币（固定CNY）';
COMMENT ON COLUMN exchange_rates.effective_date IS '生效日期';
COMMENT ON COLUMN exchange_rates.exchange_rate IS '汇率';

CREATE INDEX idx_exchange_rates_currency_date ON exchange_rates(from_currency, effective_date);

-- ============================================
-- 7.5 创建 HANA 原始快照表（HANA 视图全字段 VARCHAR 落地，清洗后入 purchase_records）
-- ============================================
CREATE TABLE IF NOT EXISTS purchase_records_origin (
    id              SERIAL PRIMARY KEY,
    import_batch_id VARCHAR(50) NOT NULL DEFAULT '',

    -- HANA 视图原始字段（全部 VARCHAR，保留原始值，不做类型转换）
    GJAHR           VARCHAR(10)  DEFAULT '',
    BUDAT           VARCHAR(10)  DEFAULT '',
    GROES           VARCHAR(200) DEFAULT '',
    MATL_GROUP      VARCHAR(50)  DEFAULT '',
    WAERS           VARCHAR(10)  DEFAULT '',
    ZDDHB           VARCHAR(10)  DEFAULT '',
    ERFME           VARCHAR(20)  DEFAULT '',
    ERFMG           VARCHAR(50)  DEFAULT '',
    ZDJ_DDHB        VARCHAR(50)  DEFAULT '',
    ZJE_DDHB        VARCHAR(50)  DEFAULT '',
    PRICE_PO        VARCHAR(50)  DEFAULT '',
    DMBTR           VARCHAR(50)  DEFAULT '',
    PRICE_IV        VARCHAR(50)  DEFAULT '',
    WRBTR           VARCHAR(50)  DEFAULT '',
    BUDAT_IV        VARCHAR(10)  DEFAULT '',
    MENGE_ES        VARCHAR(50)  DEFAULT '',
    WRBTR_ES        VARCHAR(50)  DEFAULT '',
    ZGZE            VARCHAR(50)  DEFAULT '',
    PURPOSE         VARCHAR(50)  DEFAULT '',
    MBLNR           VARCHAR(50)  DEFAULT '',
    ZEILE           VARCHAR(20)  DEFAULT '',
    EBELN           VARCHAR(50)  DEFAULT '',
    BWART           VARCHAR(10)  DEFAULT '',
    BTEXT           VARCHAR(100) DEFAULT '',
    REV             VARCHAR(10)  DEFAULT '',
    PSTYP           VARCHAR(20)  DEFAULT '',
    WEBRE           VARCHAR(10)  DEFAULT '',
    REMARK          TEXT DEFAULT '',

    -- 额外手动取值的字段（视图里别名映射过来的导航属性）
    VBUND           VARCHAR(20)  DEFAULT '',
    MATERIAL        VARCHAR(50)  DEFAULT '',
    MATNR           VARCHAR(50)  DEFAULT '',
    VENDOR          VARCHAR(50)  DEFAULT '',
    LIFNR           VARCHAR(50)  DEFAULT '',
    NAME1           VARCHAR(200) DEFAULT '',
    MAKTX           VARCHAR(200) DEFAULT '',
    COMP_CODE       VARCHAR(20)  DEFAULT '',
    BUTXT           VARCHAR(200) DEFAULT '',

    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE purchase_records_origin IS 'HANA 视图原始快照表（全字段 VARCHAR，清洗后入 purchase_records）';

CREATE INDEX IF NOT EXISTS idx_origin_material_doc ON purchase_records_origin (MBLNR);
CREATE INDEX IF NOT EXISTS idx_origin_batch         ON purchase_records_origin (import_batch_id);
CREATE INDEX IF NOT EXISTS idx_origin_budat         ON purchase_records_origin (BUDAT);

-- ============================================
-- 8. 创建采购记录表（清洗后业务分析表）
-- ============================================
CREATE TABLE IF NOT EXISTS purchase_records (
    id SERIAL PRIMARY KEY,
    
    -- 公司信息
    company_id INTEGER REFERENCES companies(id),
    company_code VARCHAR(20),
    company_name VARCHAR(200),
    
    -- 时间信息
    fiscal_year INTEGER,
    transaction_date DATE,
    
    -- 供应商信息
    supplier_id INTEGER REFERENCES suppliers(id),
    supplier_code VARCHAR(50),
    supplier_name VARCHAR(200),
    supplier_category VARCHAR(20),  -- 关联方/非关联方
    
    -- 物料信息
    material_id INTEGER REFERENCES materials(id),
    material_code VARCHAR(50),
    material_name VARCHAR(200),
    specification VARCHAR(200),
    material_category VARCHAR(50),
    wgbez VARCHAR(200) DEFAULT '',  -- WGBEZ 物料组描述（中文名，与 HANA 视图对齐）
    
    -- 采购信息（本位币）
    base_currency VARCHAR(10) DEFAULT 'CNY',
    unit VARCHAR(20),
    quantity DECIMAL(18,4),  -- 采购数量（L列）
    unit_price DECIMAL(18,4),  -- 采购单价（本位币）
    amount DECIMAL(18,2),  -- 采购金额（本位币）
    
    -- 订单货币信息
    order_currency VARCHAR(10),  -- 订单货币（AT列）
    order_unit_price DECIMAL(18,4),  -- 单价(订单货币)（AR列）
    order_amount DECIMAL(18,2),  -- 金额(订单货币)
    
    -- 汇率转换后的金额（核心字段）
    exchange_rate DECIMAL(18,6),  -- 汇率（订单货币→CNY）
    cny_amount DECIMAL(18,2),  -- 采购金额(CNY换算后)
    
    -- 发票信息
    invoice_quantity DECIMAL(18,4),
    invoice_unit_price DECIMAL(18,4),
    invoice_amount DECIMAL(18,2),
    invoice_tax DECIMAL(18,2),
    invoice_total DECIMAL(18,2),
    invoice_date DATE,
    
    -- 暂估信息
    estimate_quantity DECIMAL(18,4),
    estimate_total DECIMAL(18,2),
    estimate_amount DECIMAL(18,2),
    
    -- 其他信息
    purchase_purpose VARCHAR(50),
    po_number VARCHAR(50),  -- 采购订单号
    material_doc VARCHAR(50),  -- 物料凭证
    line_item VARCHAR(20),
    accounting_doc VARCHAR(50),  -- 会计凭证号码
    movement_type VARCHAR(10),  -- 移动类型
    movement_type_desc VARCHAR(100),
    reversal_flag VARCHAR(10),  -- 冲销标识
    line_item_category VARCHAR(20),
    gr_based_invoice VARCHAR(10),  -- 基于收货的发票验证
    line_item_text TEXT,
    
    -- 系统字段
    data_source VARCHAR(50),  -- 数据来源（Excel文件名 / HANA 同步）
    import_batch_id VARCHAR(50),  -- 导入批次ID
    deleted_at TIMESTAMP,  -- 软删除时间（NULL=正常；非 NULL=HANA 视图已删除/冲销）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE purchase_records IS '采购记录表';
COMMENT ON COLUMN purchase_records.quantity IS '采购数量';
COMMENT ON COLUMN purchase_records.order_unit_price IS '单价(订单货币)';
COMMENT ON COLUMN purchase_records.order_currency IS '订单货币';
COMMENT ON COLUMN purchase_records.exchange_rate IS '汇率（订单货币→CNY）';
COMMENT ON COLUMN purchase_records.cny_amount IS '采购金额(CNY换算后)';

-- 创建索引
CREATE INDEX idx_purchase_records_company ON purchase_records(company_id);
CREATE INDEX idx_purchase_records_date ON purchase_records(transaction_date);
CREATE INDEX idx_purchase_records_supplier ON purchase_records(supplier_id);
CREATE INDEX idx_purchase_records_material ON purchase_records(material_id);
CREATE INDEX idx_purchase_records_year ON purchase_records(fiscal_year);
CREATE INDEX idx_purchase_records_currency ON purchase_records(order_currency);
CREATE INDEX IF NOT EXISTS idx_purchase_records_deleted_at ON purchase_records(deleted_at);
CREATE INDEX IF NOT EXISTS idx_exchange_rates_currency_active ON exchange_rates(from_currency);

-- ============================================
-- 9. 创建用户表
-- ============================================
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    real_name VARCHAR(100),
    email VARCHAR(100),
    role VARCHAR(20) NOT NULL DEFAULT 'user',  -- admin/user
    company_id INTEGER REFERENCES companies(id),  -- 普通用户所属公司
    is_active BOOLEAN DEFAULT TRUE,
    must_change_password BOOLEAN DEFAULT FALSE,  -- 首次登录强制改密
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE users IS '用户表';
COMMENT ON COLUMN users.role IS '角色（admin/user）';
COMMENT ON COLUMN users.company_id IS '所属公司ID（普通用户）';
COMMENT ON COLUMN users.must_change_password IS '首次登录强制改密标识';

-- ============================================
-- 9.5 创建用户-公司权限关联表（一个普通用户可访问多个公司）
-- ============================================
CREATE TABLE IF NOT EXISTS user_company_access (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    company_code VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE user_company_access IS '用户公司访问权限表（一对多）';

CREATE INDEX IF NOT EXISTS idx_uca_user ON user_company_access(user_id);
CREATE INDEX IF NOT EXISTS idx_uca_company ON user_company_access(company_code);

-- ============================================
-- 9.6 创建物料大类维护表
-- 按"公司代码+物料编码"维护物料的大类分类，作为采购面板全员筛选器
-- ============================================
CREATE TABLE IF NOT EXISTS material_major_categories (
    id              SERIAL PRIMARY KEY,
    company_code    VARCHAR(20)  NOT NULL,
    material_code   VARCHAR(50)  NOT NULL,
    material_name   VARCHAR(200) NOT NULL DEFAULT '',
    major_category  VARCHAR(100) NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (company_code, material_code)
);

COMMENT ON TABLE  material_major_categories IS '物料大类维护表';
COMMENT ON COLUMN material_major_categories.company_code   IS '公司代码';
COMMENT ON COLUMN material_major_categories.material_code  IS '物料编码';
COMMENT ON COLUMN material_major_categories.material_name  IS '物料名称';
COMMENT ON COLUMN material_major_categories.major_category IS '物料大类';

CREATE INDEX IF NOT EXISTS idx_mmc_company       ON material_major_categories(company_code);
CREATE INDEX IF NOT EXISTS idx_mmc_material_code ON material_major_categories(material_code);
CREATE INDEX IF NOT EXISTS idx_mmc_major         ON material_major_categories(major_category);

-- ============================================
-- 9.7 创建 HANA 同步状态表（记录每次同步批次与水位）
-- ============================================
CREATE TABLE IF NOT EXISTS hana_sync_state (
    id              SERIAL PRIMARY KEY,
    sync_type       VARCHAR(20)  NOT NULL DEFAULT 'full',  -- full / incremental
    last_sync_at    TIMESTAMP    NOT NULL DEFAULT NOW(),   -- 最近一次同步时间
    last_batch_id   VARCHAR(50),                            -- 最近批次ID
    total_hana_rows INTEGER      DEFAULT 0,                 -- HANA 拉取行数
    total_inserted  INTEGER      DEFAULT 0,                 -- 新增行数
    total_updated   INTEGER      DEFAULT 0,                 -- 更新行数
    total_deleted   INTEGER      DEFAULT 0,                 -- 软删除行数
    status          VARCHAR(20)  DEFAULT 'completed',       -- running / completed / failed
    error_message   TEXT,
    created_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE hana_sync_state IS 'HANA 同步状态记录表，记录每次同步的水位和统计';

CREATE INDEX IF NOT EXISTS idx_hana_sync_state_last_sync ON hana_sync_state(last_sync_at);
CREATE INDEX IF NOT EXISTS idx_hana_sync_state_type      ON hana_sync_state(sync_type);

-- ============================================
-- 9.8 创建操作审计日志表（记录关键写操作，安全审计与追溯）
-- ============================================
CREATE TABLE IF NOT EXISTS audit_logs (
    id           SERIAL PRIMARY KEY,
    user_id      INTEGER,                         -- 操作者ID（未登录= NULL）
    username     VARCHAR(50),                     -- 操作者用户名
    method       VARCHAR(10)  NOT NULL,           -- HTTP 方法
    path         VARCHAR(500) NOT NULL,           -- 请求路径
    status_code  INTEGER,                         -- 响应状态码
    client_ip    VARCHAR(50),                     -- 客户端IP
    body_summary TEXT,                            -- 请求体摘要（截断防超长）
    cost_ms      INTEGER,                         -- 请求耗时（毫秒）
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE audit_logs IS '操作审计日志表（记录写操作，用于安全审计）';

CREATE INDEX IF NOT EXISTS idx_audit_logs_user    ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_path    ON audit_logs(path);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created ON audit_logs(created_at);


-- ============================================
-- 10. 插入初始数据
-- ============================================

-- 插入集团数据
INSERT INTO groups (group_code, group_name, description) VALUES
('GP001', '示例集团', '示例集团总部')
ON CONFLICT (group_code) DO NOTHING;

-- 插入事业部数据
INSERT INTO business_units (unit_code, unit_name, group_id, description)
SELECT 'BU001', '示例事业部', g.id, '示例事业部'
FROM groups g WHERE g.group_code = 'GP001'
ON CONFLICT (unit_code) DO NOTHING;

-- 插入板块数据
INSERT INTO business_sectors (sector_code, sector_name, unit_id, description)
SELECT 'SC001', '示例板块', bu.id, '示例业务板块'
FROM business_units bu WHERE bu.unit_code = 'BU001'
ON CONFLICT (sector_code) DO NOTHING;

-- 插入公司数据（示例数据）
INSERT INTO companies (company_code, company_name, sector_id)
SELECT 'E510', '示例生物科技有限公司', bs.id
FROM business_sectors bs WHERE bs.sector_code = 'SC001'
ON CONFLICT (company_code) DO NOTHING;

INSERT INTO companies (company_code, company_name, sector_id)
SELECT 'D230', '示例科技有限公司', bs.id
FROM business_sectors bs WHERE bs.sector_code = 'SC001'
ON CONFLICT (company_code) DO NOTHING;

INSERT INTO companies (company_code, company_name, sector_id)
SELECT 'D510', 'PT. Example International', bs.id
FROM business_sectors bs WHERE bs.sector_code = 'SC001'
ON CONFLICT (company_code) DO NOTHING;

-- 插入常用汇率数据（示例）
INSERT INTO exchange_rates (from_currency, to_currency, effective_date, exchange_rate, source) VALUES
('USD', 'CNY', '2025-01-01', 7.2, '手动维护'),
('USD', 'CNY', '2026-01-01', 7.1, '手动维护'),
('IDR', 'CNY', '2025-01-01', 0.00045, '手动维护'),
('IDR', 'CNY', '2026-01-01', 0.00044, '手动维护'),
('SGD', 'CNY', '2025-01-01', 5.3, '手动维护'),
('JPY', 'CNY', '2025-01-01', 0.048, '手动维护')
ON CONFLICT (from_currency, effective_date) DO NOTHING;

-- 创建更新时间触发器函数
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 为所有表创建更新时间触发器
CREATE OR REPLACE TRIGGER update_groups_updated_at BEFORE UPDATE ON groups
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE OR REPLACE TRIGGER update_business_sectors_updated_at BEFORE UPDATE ON business_sectors
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE OR REPLACE TRIGGER update_business_units_updated_at BEFORE UPDATE ON business_units
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE OR REPLACE TRIGGER update_companies_updated_at BEFORE UPDATE ON companies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE OR REPLACE TRIGGER update_suppliers_updated_at BEFORE UPDATE ON suppliers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE OR REPLACE TRIGGER update_materials_updated_at BEFORE UPDATE ON materials
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE OR REPLACE TRIGGER update_exchange_rates_updated_at BEFORE UPDATE ON exchange_rates
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE OR REPLACE TRIGGER update_purchase_records_updated_at BEFORE UPDATE ON purchase_records
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE OR REPLACE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE OR REPLACE TRIGGER update_material_major_categories_updated_at BEFORE UPDATE ON material_major_categories
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 完成提示
SELECT '数据库初始化完成！' AS message;
