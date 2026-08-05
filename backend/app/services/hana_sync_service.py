"""
HANA 数据同步服务
从 SAP HANA 视图读取采购台账数据，映射到本地 purchase_records 表
同步逻辑：字段映射 → 手动配置汇率匹配 → 去重 → 主数据补充
支持全量同步和增量同步（基于 RECORDMODE + diff 比对）

汇率规则：
- 汇率从本地 exchange_rates 表手动配置，不同步外部央行数据
- cny_amount = ZDJ_DDHB（订单单价）× MENGE（订单数量）× 汇率；为0则 WAERS=CNY 取 DMBTR，否则记0
- order_currency 为 CNY 时，汇率恒为 1.0

优化策略（2026-07）：
- 全量同步：HANA → purchase_records_origin（原始数据，同库批量 INSERT）
- 清洗：purchase_records_origin → purchase_records（纯 SQL，极快）
- 增量同步：少量数据走原 Python 映射流程

边界修复（2026-07-02）：
- 修复 _batch_upsert_purchase_records 中 walrus 运算符优先级 bug
- 月度同步新增"反向删除比对"：本地存在但 HANA 视图已不存在的当月/上月记录，
  统一软删除（设置 deleted_at），避免 HANA 真删数据后本地仍误显
- 月度同步窗口扩展：lookback_months 默认 2，覆盖 BUDAT 跨月修改场景
- 同流程开始加 PG advisory lock（pg_try_advisory_lock）防并发执行
- 月度同步前清理 origin 表同日期范围内的旧批次，防止 origin 无界增长
- 时区统一：所有 now() 取 Asia/Shanghai 本地日历日，避免日切丢数据
"""
import calendar
import logging
import multiprocessing
from decimal import Decimal
from datetime import date, datetime, timedelta
from typing import Optional, List, Dict, Tuple

from sqlalchemy import and_, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ..hana_client import (
    fetch_all_data,
    fetch_all_data_parallel,
    fetch_all_incremental_data,
    fetch_data_by_date_range,
)
from ..models import (
    Company,
    ExchangeRate,
    HanaSyncState,
    Material,
    PurchaseRecord,
    PurchaseRecordOrigin,
    Supplier,
)
from ..services import exchange_rate_service

logger = logging.getLogger(__name__)

# 关联方类别过滤值列表
RELATED_PARTY_VALUES = {"关联方", "关联方供应商"}

# RECORDMODE → 操作类型映射
RECORDMODE_ACTION = {"N": "insert", "U": "update", "D": "delete"}

# PostgreSQL advisory lock 全局键（任意常量，不同同步类型互斥）
# 同一个 key 用于"防止任意 HANA 同步流程并发执行"
HANA_SYNC_ADVISORY_LOCK_KEY = 0x48414E41  # 'HANA' 的 32-bit 表示

# 月度同步默认回看窗口：覆盖上月+当月即可满足"BUDAT 跨月修改后能被刷新"的需求
DEFAULT_LOOKBACK_MONTHS = 2

def _build_origin_columns() -> List[str]:
    """从 ORM 模型动态获取 origin 表全部数据列名（小写，匹配 PG 列名）。
    排除 id / import_batch_id / created_at（由 DB/代码管理，非视图字段）。
    这样 HANA 视图新增字段、ORM 补列后自动纳入，杜绝"按错误结构裁字段"。
    """
    skip = {"id", "import_batch_id", "created_at"}
    return [name for name in PurchaseRecordOrigin.__mapper__.columns.keys() if name not in skip]


# origin 表列名（动态，与 ORM 模型、HANA 视图三者保持一致，绝不裁字段）
ORIGIN_COLUMNS = _build_origin_columns()


# ═══════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════

def _parse_date(value) -> Optional[date]:
    """将 HANA 返回的日期转换为 Python date"""
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    s = str(value).strip()
    if not s:
        return None
    try:
        if len(s) == 8 and s.isdigit():
            return date(int(s[:4]), int(s[4:6]), int(s[6:8]))
        return date.fromisoformat(s[:10])
    except (ValueError, TypeError):
        logger.warning(f"无法解析日期: {value}")
        return None


def _to_decimal(value) -> Optional[Decimal]:
    """将数值转换为 Decimal，空值返回 None"""
    if value is None:
        return None
    try:
        d = Decimal(str(value))
        if d.is_nan():
            return None
        return d
    except Exception:
        return None


def _clean_str(value, default="") -> str:
    """清洗字符串字段，处理 None / NaN"""
    if value is None:
        return default
    s = str(value).strip()
    if s.lower() == "nan" or s == "":
        return default
    return s


def _local_now() -> datetime:
    """获取 Asia/Shanghai 时区下的当前时刻。
    系统时区已配置为 Asia/Shanghai，直接用 naive 本地时间即可，
    避免存 TZ-aware 时间戳与既有 TIMESTAMP WITHOUT TIME ZONE 列冲突。
    """
    return datetime.now()


def _local_today() -> date:
    """获取 Asia/Shanghai 时区下的当前日历日"""
    return _local_now().date()


class _AdvisoryLockHeld(Exception):
    """advisory lock 已被其他进程占用，本次同步直接跳过"""


def _acquire_sync_lock(db: Session, lock_key: int = HANA_SYNC_ADVISORY_LOCK_KEY) -> None:
    """获取 PostgreSQL 会话级 advisory lock。
    若被占用直接抛 _AdvisoryLockHeld，调用方应记日志并跳过本次同步。
    会话结束时（连接归还池）锁自动释放，无需显式 unlock。
    """
    sql = text("SELECT pg_try_advisory_lock(:k)")
    acquired = db.execute(sql, {"k": lock_key}).scalar()
    if not acquired:
        raise _AdvisoryLockHeld(
            "已有同步流程在执行中（pg_try_advisory_lock 未获取），本次跳过"
        )


# ── HANA 字段 → purchase_records 字段映射 ──
# (hana_col, record_col, default, transform_fn)
# 公司/供应商/物料代码在 _map_row 中特殊处理
FIELD_MAPPING = [
    ("GJAHR",        "fiscal_year",       None, lambda v: int(v) if v else None),
    ("BUDAT",        "transaction_date",  None, _parse_date),
    ("GROES",        "specification",     "", None),
    ("MATL_GROUP",   "material_category", "", None),
    ("WGBEZ",        "wgbez",             "", None),
    ("WAERS",        "base_currency",     "CNY", None),
    ("ZDDHB",        "order_currency",    "CNY", None),
    ("ERFME",        "unit",              "", None),
    ("MENGE",        "quantity",          None, _to_decimal),  # 订单数量（金额=单价×此数量×汇率）
    ("ZDJ_DDHB",     "order_unit_price",  None, _to_decimal),
    ("ZJE_DDHB",     "order_amount",      None, _to_decimal),
    ("PRICE_PO",     "unit_price",        None, _to_decimal),
    ("DMBTR",        "amount",            None, _to_decimal),
    ("PRICE_IV",     "invoice_unit_price", None, _to_decimal),
    ("WRBTR",        "invoice_amount",    None, _to_decimal),
    ("BUDAT_IV",     "invoice_date",      None, _parse_date),
    ("MENGE_ES",     "estimate_quantity", None, _to_decimal),
    ("WRBTR_ES",     "estimate_amount",   None, _to_decimal),
    ("ZGZE",         "estimate_total",    None, _to_decimal),
    ("PURPOSE",      "purchase_purpose",  "", None),
    ("MBLNR",        "material_doc",      "", None),       # 去重键1
    ("ZEILE",        "line_item",         "", None),       # 去重键2
    ("EBELN",        "po_number",         "", None),
    ("BWART",        "movement_type",     "", None),
    ("BTEXT",        "movement_type_desc","", None),
    ("REV",          "reversal_flag",     "", None),
    ("PSTYP",        "line_item_category","", None),
    ("WEBRE",        "gr_based_invoice",  "", None),
    ("REMARK",       "line_item_text",    "", None),       # 备注 → 行项目文本
]


# ── 静态辅助：供多进程 worker 使用（不可访问 self.db）────

def _lookup_exchange_rate_static(rate_cache: Dict, currency: str, txn_date: Optional[date]) -> float:
    """从传入的汇率缓存查找汇率（供多进程 worker 使用）。
    缓存结构：{currency: [(effective_date, expiry_date, rate), ...]}
    """
    if not currency or currency.upper() == "CNY":
        return 1.0
    cur = currency.upper()
    intervals = rate_cache.get(cur)
    if not intervals or not txn_date:
        return 0.0
    # 按 effective_date 降序，第一条覆盖 txn_date 的即为最新生效汇率
    for eff, exp, rate in sorted(intervals, key=lambda x: x[0], reverse=True):
        if eff <= txn_date and (exp is None or exp >= txn_date):
            return rate
    return 0.0


def _calc_cny_amount_static(
    rate_cache: Dict,
    order_currency: str,
    order_unit_price: float,
    quantity: float,
    txn_date: Optional[date],
    base_currency: str = "CNY",
    amount: float = 0.0,
) -> Tuple[float, float]:
    """计算 CNY 金额和汇率（供多进程 worker 使用）。
    与 SQL 清洗规则一致：单价×数量×汇率；为0则 WAERS=CNY 取 DMBTR，否则记0。
    """
    if order_unit_price and quantity and order_unit_price > 0 and quantity > 0:
        if order_currency == "CNY":
            return round(order_unit_price * quantity, 2), 1.0
        rate = _lookup_exchange_rate_static(rate_cache, order_currency, txn_date)
        if rate > 0.0:
            return round(order_unit_price * quantity * rate, 2), rate
    # 单价/数量为 0 → 回退本位币金额 DMBTR（仅本位币 CNY 可直接当 CNY 金额）
    if (base_currency or "CNY").upper() == "CNY":
        return round(float(amount or 0), 2), 0.0
    return 0.0, 0.0


def _map_row_static(row: dict, rate_cache: Dict) -> Optional[dict]:
    """单条 HANA 行映射为 purchase_records 字段字典（无 self.db 依赖）。"""
    supplier_category = _clean_str(row.get("VBUND"))
    if supplier_category in RELATED_PARTY_VALUES:
        return None

    material_code = _clean_str(row.get("MATERIAL") or row.get("MATNR"))
    if not material_code:
        return None

    material_doc = _clean_str(row.get("MBLNR"))
    if not material_doc:
        return None

    supplier_code = _clean_str(row.get("VENDOR") or row.get("LIFNR"))

    record_data = {}
    for hana_col, rec_col, default, transform_fn in FIELD_MAPPING:
        raw_val = row.get(hana_col)
        if transform_fn and raw_val is not None:
            val = transform_fn(raw_val)
        elif isinstance(default, str):
            val = _clean_str(raw_val, default)
        else:
            val = raw_val if raw_val is not None else default
        record_data[rec_col] = val

    order_currency = _clean_str(row.get("ZDDHB"), "CNY")
    order_unit_price_val = record_data.get("order_unit_price")
    order_unit_price = float(order_unit_price_val) if order_unit_price_val is not None else 0.0
    quantity_val = record_data.get("quantity")
    quantity = float(quantity_val) if quantity_val is not None else 0.0
    txn_date = record_data.get("transaction_date")

    base_currency = record_data.get("base_currency") or "CNY"
    amount_val = record_data.get("amount")
    amount = float(amount_val) if amount_val is not None else 0.0
    cny_amount, exchange_rate = _calc_cny_amount_static(
        rate_cache, order_currency, order_unit_price, quantity, txn_date,
        base_currency, amount,
    )

    record_data["order_currency"] = order_currency
    record_data["cny_amount"] = cny_amount
    record_data["exchange_rate"] = exchange_rate
    record_data["supplier_code"] = supplier_code
    record_data["supplier_name"] = _clean_str(row.get("NAME1"))
    record_data["supplier_category"] = supplier_category
    record_data["material_code"] = material_code
    record_data["material_name"] = _clean_str(row.get("MAKTX"))
    record_data["company_code"] = _clean_str(row.get("COMP_CODE"))
    record_data["company_name"] = _clean_str(row.get("BUTXT"))
    record_data["data_source"] = "HANA"
    record_data["created_at"] = _local_now()
    record_data["updated_at"] = _local_now()

    return record_data


def _map_worker(args: Tuple[List[dict], Dict]) -> Tuple[List[dict], Dict[str, str], Dict[str, str], dict]:
    """
    多进程 worker：处理一批 HANA 行，返回映射结果 + 主数据收集。
    """
    rows, rate_cache = args
    mapped: List[dict] = []
    supplier_data: Dict[str, str] = {}
    material_data: Dict[str, str] = {}
    stats = {
        "filtered_related": 0,
        "filtered_empty_material": 0,
        "filtered_empty_doc": 0,
        "mapped": 0,
        "errors": [],
    }

    for row in rows:
        try:
            record_data = _map_row_static(row, rate_cache)
            if record_data is None:
                supplier_cat = _clean_str(row.get("VBUND"))
                material_code = _clean_str(row.get("MATERIAL") or row.get("MATNR"))
                material_doc = _clean_str(row.get("MBLNR"))
                if supplier_cat in RELATED_PARTY_VALUES:
                    stats["filtered_related"] += 1
                elif not material_code:
                    stats["filtered_empty_material"] += 1
                elif not material_doc:
                    stats["filtered_empty_doc"] += 1
                else:
                    stats["filtered_empty_material"] += 1
                continue

            sc = record_data.get("supplier_code", "")
            mc = record_data.get("material_code", "")
            sn = record_data.get("supplier_name", "")
            mn = record_data.get("material_name", "")
            if sc:
                supplier_data[sc] = sn
            if mc:
                material_data[mc] = mn

            mapped.append(record_data)
            stats["mapped"] += 1
        except Exception as e:
            stats["errors"].append({
                "row": str(row.get("MBLNR", "?")),
                "error": str(e),
            })

    return mapped, supplier_data, material_data, stats


# ═══════════════════════════════════════════
# HanaSyncService
# ═══════════════════════════════════════════

class HanaSyncService:
    """HANA 数据同步服务"""

    def __init__(self, db: Session):
        self.db = db
        # 汇率缓存：{currency: [(effective_date, expiry_date, rate), ...]}
        self._rate_cache: Dict[str, List[Tuple[date, Optional[date], float]]] = {}

    # ── 汇率查询（按交易日匹配，批量预加载）───────────────

    def _preload_all_exchange_rates(self) -> None:
        """
        一次性加载 exchange_rates 表全部记录。
        表数据量很小（通常 < 1000 条），全量加载无压力。
        缓存结构：{currency: [(effective_date, expiry_date, rate), ...]}
        """
        all_rates = self.db.query(ExchangeRate).all()
        for r in all_rates:
            cur = r.from_currency.upper()
            eff = r.effective_date
            exp = r.expiry_date
            rate = float(r.exchange_rate)
            self._rate_cache.setdefault(cur, []).append((eff, exp, rate))
        logger.info(f"汇率全量加载完成：{len(all_rates)} 条记录")

    def _get_rate_from_cache(self, currency: str, txn_date: Optional[date]) -> float:
        """从全量缓存中查找指定币种在交易日的生效汇率。"""
        if not currency or currency.upper() == "CNY":
            return 1.0
        cur = currency.upper()
        if cur not in self._rate_cache or not txn_date:
            return 0.0
        # 按 effective_date 降序，第一条覆盖 txn_date 的即为最新生效汇率
        for eff, exp, rate in sorted(self._rate_cache[cur], key=lambda x: x[0], reverse=True):
            if eff <= txn_date and (exp is None or exp >= txn_date):
                return rate
        return 0.0

    def _preload_exchange_rates(self, currencies: set, dates: set) -> None:
        """
        批量预加载所有需要的 (currency, date) 汇率组合（兼容旧接口）。
        在映射前一次性查出，避免映射阶段逐行 DB 查询。
        """
        if not currencies or not dates:
            return
        # 如果缓存为空，先全量加载
        if not self._rate_cache:
            self._preload_all_exchange_rates()

    def _lookup_exchange_rate(
        self, currency: str, txn_date: Optional[date]
    ) -> float:
        """
        从缓存查找生效汇率（需先调用 _preload_exchange_rates 预加载）。
        CNY 恒为 1.0。缓存未命中时降级为单次 DB 查询。
        """
        if not currency or currency.upper() == "CNY":
            return 1.0

        cur = currency.upper()
        rate = self._get_rate_from_cache(cur, txn_date)
        if rate != 0.0:
            return rate

        # 降级：缓存未命中时单次查询（向前兼容）
        rate_obj = exchange_rate_service.get_effective_rate(
            self.db, cur, txn_date or date.today()
        )
        if rate_obj:
            val = float(rate_obj.exchange_rate)
        else:
            logger.warning(f"缺少币种 {cur} 在 {txn_date} 的汇率，fallback 为 0")
            val = 0.0

        return val

    def _calc_cny_amount(
        self,
        order_currency: str,
        order_unit_price: float,  # ZDJ_DDHB 订单单价
        quantity: float,          # MENGE 订单数量
        txn_date: Optional[date],
        base_currency: str = "CNY",  # WAERS 本位币
        amount: float = 0.0,         # DMBTR 本位币金额（兜底）
    ) -> Tuple[float, float]:
        """
        计算 CNY 金额和汇率，与 SQL 清洗规则一致：
        单价×数量×汇率；为0则 WAERS=CNY 取 DMBTR，否则记0。
        Returns: (cny_amount, exchange_rate)
        """
        # 有单价且有数量 → 单价 × 数量 × 汇率
        if order_unit_price and quantity and order_unit_price > 0 and quantity > 0:
            if order_currency == "CNY":
                return round(order_unit_price * quantity, 2), 1.0
            rate = self._lookup_exchange_rate(order_currency, txn_date)
            if rate > 0.0:
                return round(order_unit_price * quantity * rate, 2), rate

        # 单价/数量为 0 → 回退本位币金额 DMBTR（仅本位币 CNY 可直接当 CNY 金额）
        if (base_currency or "CNY").upper() == "CNY":
            return round(float(amount or 0), 2), 0.0
        return 0.0, 0.0

    # ── 行映射 ─────────────────────────────────

    def _map_row(self, row: dict) -> Optional[dict]:
        """
        将 HANA 单行数据映射为 purchase_records 字段字典
        过滤规则：关联方跳过 / 物料代码为空跳过 / 物料凭证为空跳过

        Returns: 字段字典，或 None（跳过该行）
        """
        # ── 关联方过滤 ──
        supplier_category = _clean_str(row.get("VBUND"))
        if supplier_category in RELATED_PARTY_VALUES:
            return None

        # ── 物料代码：MATERIAL 优先，MATNR 回退 ──
        material_code = _clean_str(row.get("MATERIAL") or row.get("MATNR"))
        if not material_code:
            return None

        # ── 物料凭证（去重键）过滤 ──
        material_doc = _clean_str(row.get("MBLNR"))
        if not material_doc:
            return None

        # ── 供应商代码：VENDOR 优先，LIFNR 回退 ──
        supplier_code = _clean_str(row.get("VENDOR") or row.get("LIFNR"))

        # ── 构建通用字段映射 ──
        record_data = {}
        for hana_col, rec_col, default, transform_fn in FIELD_MAPPING:
            raw_val = row.get(hana_col)
            if transform_fn and raw_val is not None:
                val = transform_fn(raw_val)
            elif isinstance(default, str):
                val = _clean_str(raw_val, default)
            else:
                val = raw_val if raw_val is not None else default
            record_data[rec_col] = val

        # ── CNY 金额计算（公式：订单单价 × 数量 × 手动配置汇率）─────
        order_currency = _clean_str(row.get("ZDDHB"), "CNY")
        order_unit_price_val = record_data.get("order_unit_price")
        order_unit_price = float(order_unit_price_val) if order_unit_price_val is not None else 0.0
        quantity_val = record_data.get("quantity")
        quantity = float(quantity_val) if quantity_val is not None else 0.0
        txn_date = record_data.get("transaction_date")

        base_currency = record_data.get("base_currency") or "CNY"
        amount_val = record_data.get("amount")
        amount = float(amount_val) if amount_val is not None else 0.0
        cny_amount, exchange_rate = self._calc_cny_amount(
            order_currency, order_unit_price, quantity, txn_date,
            base_currency, amount,
        )
        record_data["order_currency"] = order_currency
        record_data["cny_amount"] = cny_amount
        record_data["exchange_rate"] = exchange_rate

        # ── 手动赋值字段（不在 FIELD_MAPPING 中的特殊处理）─────
        record_data["supplier_code"] = supplier_code
        record_data["supplier_name"] = _clean_str(row.get("NAME1"))
        record_data["supplier_category"] = supplier_category
        record_data["material_code"] = material_code
        record_data["material_name"] = _clean_str(row.get("MAKTX"))
        record_data["company_code"] = _clean_str(row.get("COMP_CODE"))
        record_data["company_name"] = _clean_str(row.get("BUTXT"))
        record_data["data_source"] = "HANA"
        record_data["created_at"] = _local_now()
        record_data["updated_at"] = _local_now()

        return record_data

    # ── 主数据补充 ─────────────────────────────

    def _upsert_master_data(
        self,
        supplier_data: Dict[str, str],     # {code: name}
        material_data: Dict[str, str],     # {code: name}
    ) -> Tuple[int, int]:
        """
        补充供应商和物料主数据（不存在则创建，存在则更新名称）
        Returns: (供应商新增数, 物料新增数)
        """
        suppliers_created = 0
        materials_created = 0

        # ── 供应商（分批 IN 查询 + savepoint 隔离，避免脏事务污染）──
        IN_CHUNK_SIZE = 100  # 保守控制每批参数数，避免 PostgreSQL 栈溢出/事务异常
        if supplier_data:
            existing = {}
            codes = list(supplier_data.keys())
            for i in range(0, len(codes), IN_CHUNK_SIZE):
                chunk = codes[i : i + IN_CHUNK_SIZE]
                # 每批用独立 savepoint 隔离错误
                try:
                    sp = self.db.begin_nested()
                    batch = (
                        self.db.query(Supplier)
                        .filter(Supplier.supplier_code.in_(chunk))
                        .all()
                    )
                    for s in batch:
                        existing[s.supplier_code] = s
                    sp.commit()
                except Exception:
                    sp.rollback()
                    logger.warning(f"供应商分批查询失败(第{i//IN_CHUNK_SIZE}批，{len(chunk)}条)，跳过")

            new_sups = []
            for code, name in supplier_data.items():
                if not code:
                    continue
                if code in existing:
                    sup = existing[code]
                    if sup.supplier_name == code and name and name != code:
                        sup.supplier_name = name
                else:
                    new_sups.append(Supplier(supplier_code=code, supplier_name=name or code))
                    suppliers_created += 1
            if new_sups:
                self.db.bulk_save_objects(new_sups)
                self.db.flush()

        # ── 物料（分批 IN 查询 + savepoint 隔离）─────────────────
        if material_data:
            existing = {}
            codes = list(material_data.keys())
            for i in range(0, len(codes), IN_CHUNK_SIZE):
                chunk = codes[i : i + IN_CHUNK_SIZE]
                try:
                    sp = self.db.begin_nested()
                    batch = (
                        self.db.query(Material)
                        .filter(Material.material_code.in_(chunk))
                        .all()
                    )
                    for m in batch:
                        existing[m.material_code] = m
                    sp.commit()
                except Exception:
                    sp.rollback()
                    logger.warning(f"物料分批查询失败(第{i//IN_CHUNK_SIZE}批，{len(chunk)}条)，跳过")

            new_mats = []
            for code, name in material_data.items():
                if not code:
                    continue
                if code in existing:
                    mat = existing[code]
                    if mat.material_name == code and name and name != code:
                        mat.material_name = name
                else:
                    new_mats.append(Material(material_code=code, material_name=name or code))
                    materials_created += 1
            if new_mats:
                self.db.bulk_save_objects(new_mats)
                self.db.flush()

        return suppliers_created, materials_created

    # ── 记录行级哈希（用于增量更新检测）─────────

    @staticmethod
    def _record_hash(record_data: dict) -> str:
        """
        对一条映射后的记录计算内容哈希，用于比对是否需要更新。
        排除系统字段（id, created_at, updated_at, import_batch_id, data_source 等）
        """
        import hashlib, json
        # 仅取业务字段做哈希
        skip_keys = {
            "id", "created_at", "updated_at", "import_batch_id",
            "data_source", "company_id",
            "supplier_id", "material_id",
        }
        biz_data = {
            k: (str(v) if isinstance(v, (date, datetime, Decimal)) else v)
            for k, v in record_data.items()
            if k not in skip_keys
        }
        raw = json.dumps(biz_data, sort_keys=True, default=str)
        return hashlib.md5(raw.encode()).hexdigest()

    # ── diff 比对：识别新增 / 更新 / 删除 ──────

    def _diff_with_local(
        self,
        hana_records: List[dict],
        import_batch_id: str,
    ) -> Dict[str, list]:
        """
        将 HANA 映射后的数据与本地 purchase_records 做 diff

        Returns:
            {
                "to_insert": [...],   # 新增记录（本地无此 key）
                "to_update": [...],   # 需要更新的记录（内容哈希变化）
                "to_delete_keys": [(doc, item), ...],  # 本地有但 HANA 无（仅增量模式用）
            }
        """
        result = {"to_insert": [], "to_update": [], "to_delete_keys": []}

        # ── 构建 HANA 行的 key → (record_data, hash) 映射 ──
        hana_map: Dict[Tuple[str, str], Tuple[dict, str]] = {}
        for rd in hana_records:
            key = (rd.get("material_doc", ""), rd.get("line_item", ""))
            if not key[0]:
                continue
            rd["import_batch_id"] = import_batch_id
            hana_map[key] = (rd, self._record_hash(rd))

        if not hana_map:
            return result

        # ── 批量查本地已有记录（分批 IN 查询 + savepoint 隔离）─────
        all_docs = list({k[0] for k in hana_map.keys()})
        local_rows = []
        IN_CHUNK_SIZE = 100
        for i in range(0, len(all_docs), IN_CHUNK_SIZE):
            chunk = all_docs[i : i + IN_CHUNK_SIZE]
            try:
                sp = self.db.begin_nested()
                batch = (
                    self.db.query(PurchaseRecord)
                    .filter(PurchaseRecord.material_doc.in_(chunk))
                    .all()
                )
                local_rows.extend(batch)
                sp.commit()
            except Exception:
                sp.rollback()
                logger.warning(f"本地记录分批查询失败(第{i//IN_CHUNK_SIZE}批，{len(chunk)}条)，跳过")

        # 本地记录 key → hashed 内容
        local_map: Dict[Tuple[str, str], Tuple[PurchaseRecord, str]] = {}
        for rec in local_rows:
            key = (rec.material_doc or "", rec.line_item or "")
            if not key[0]:
                continue
            # 从 ORM 对象构造业务字段 dict 再哈希
            local_data = {
                "company_code": rec.company_code,
                "company_name": rec.company_name,
                "fiscal_year": rec.fiscal_year,
                "transaction_date": rec.transaction_date,
                "supplier_code": rec.supplier_code,
                "supplier_name": rec.supplier_name,
                "supplier_category": rec.supplier_category,
                "material_code": rec.material_code,
                "material_name": rec.material_name,
                "specification": rec.specification,
                "material_category": rec.material_category,
                "base_currency": rec.base_currency,
                "unit": rec.unit,
                "quantity": rec.quantity,
                "unit_price": rec.unit_price,
                "amount": rec.amount,
                "order_currency": rec.order_currency,
                "order_unit_price": rec.order_unit_price,
                "order_amount": rec.order_amount,
                "exchange_rate": rec.exchange_rate,
                "cny_amount": rec.cny_amount,
                "invoice_quantity": rec.invoice_quantity,
                "invoice_unit_price": rec.invoice_unit_price,
                "invoice_amount": rec.invoice_amount,
                "invoice_tax": rec.invoice_tax,
                "invoice_total": rec.invoice_total,
                "invoice_date": rec.invoice_date,
                "estimate_quantity": rec.estimate_quantity,
                "estimate_total": rec.estimate_total,
                "estimate_amount": rec.estimate_amount,
                "purchase_purpose": rec.purchase_purpose,
                "po_number": rec.po_number,
                "material_doc": rec.material_doc,
                "line_item": rec.line_item,
                "accounting_doc": rec.accounting_doc,
                "movement_type": rec.movement_type,
                "movement_type_desc": rec.movement_type_desc,
                "reversal_flag": rec.reversal_flag,
                "line_item_category": rec.line_item_category,
                "gr_based_invoice": rec.gr_based_invoice,
                "line_item_text": rec.line_item_text,
            }
            import hashlib, json
            raw = json.dumps(local_data, sort_keys=True, default=str)
            local_hash = hashlib.md5(raw.encode()).hexdigest()
            local_map[key] = (rec, local_hash)

        # ── 逐 key 比对 ──
        for key, (hana_rd, hana_hash) in hana_map.items():
            if key not in local_map:
                # 本地不存在 → 新增
                result["to_insert"].append(hana_rd)
            else:
                local_rec, local_hash = local_map[key]
                if hana_hash != local_hash:
                    # 内容变化 → 更新（保留本地 id）
                    hana_rd["_update_id"] = local_rec.id
                    result["to_update"].append(hana_rd)

        return result

    # ── 批量 upsert 采购记录（PG 专属：INSERT ... ON CONFLICT DO UPDATE）────

    def _batch_upsert_purchase_records(
        self,
        records: List[dict],
        import_batch_id: str,
        batch_size: int = 5000,
    ) -> Tuple[int, int]:
        """
        使用 PostgreSQL ON CONFLICT upsert 批量写入采购记录。
        依赖唯一约束：purchase_records(material_doc, line_item)。
        通过 PG 的 xmax 系统列判断 inserted vs updated，无需提前查询。
        """
        upsert_columns = [
            "company_code", "company_name",
            "fiscal_year", "transaction_date",
            "supplier_code", "supplier_name", "supplier_category",
            "material_code", "material_name", "specification", "material_category",
            "base_currency", "unit", "quantity", "unit_price", "amount",
            "order_currency", "order_unit_price", "order_amount",
            "exchange_rate", "cny_amount",
            "invoice_quantity", "invoice_unit_price", "invoice_amount",
            "invoice_tax", "invoice_total", "invoice_date",
            "estimate_quantity", "estimate_total", "estimate_amount",
            "purchase_purpose", "po_number",
            "material_doc", "line_item",
            "accounting_doc", "movement_type", "movement_type_desc",
            "reversal_flag", "line_item_category", "gr_based_invoice", "line_item_text",
            "data_source", "import_batch_id",
            "created_at", "updated_at",
        ]

        original_total = len(records)
        if not original_total:
            return 0, 0

        # 去重：同一批次内相同 (material_doc, line_item) 只保留最后一条
        deduped = []
        seen = set()
        for r in reversed(records):
            key = (r.get("material_doc"), r.get("line_item"))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(r)
        deduped.reverse()
        records = deduped
        deduped_total = len(records)
        if deduped_total < original_total:
            logger.info(
                f"采购记录去重后：{deduped_total} 条"
                f"（原始 {original_total} 条，重复 {original_total - deduped_total} 条）"
            )

        inserted_count = 0
        updated_count = 0
        for i in range(0, deduped_total, batch_size):
            batch = records[i : i + batch_size]
            values = []
            for r in batch:
                r["import_batch_id"] = import_batch_id
                r["data_source"] = "HANA"
                row_dict = {col: r.get(col) for col in upsert_columns}
                values.append(row_dict)

            stmt = insert(PurchaseRecord).values(values)
            update_dict = {
                col: stmt.excluded[col]
                for col in upsert_columns
                if col not in ("id", "material_doc", "line_item", "created_at")
            }
            stmt = stmt.on_conflict_do_update(
                index_elements=["material_doc", "line_item"],
                set_=update_dict,
            )
            # 用 RETURNING xmax 区分 inserted (xmax=0) vs updated (xmax!=0)
            stmt = stmt.returning(
                text("xmax"),
                PurchaseRecord.material_doc,
            )
            result = self.db.execute(stmt)
            for row in result:
                xmax, _ = row
                # xmax=0 表示新插入；非 0 表示走 update 路径
                if xmax == 0 or xmax is None:
                    inserted_count += 1
                else:
                    updated_count += 1
            self.db.flush()
            logger.info(f"批量 upsert 采购记录 {min(i + batch_size, deduped_total)}/{deduped_total}")

        return inserted_count, updated_count

    # ═══════════════════════════════════════════
    # 全量同步（两阶段高速策略）
    # 阶段1: HANA SELECT * → TRUNCATE origin → 批量 INSERT 原始数据
    # 阶段2: PG 内纯 SQL 清洗（过滤+类型转换+汇率+upsert）
    # 阶段3: PG 内 SQL 补充供应商/物料主数据
    # ═══════════════════════════════════════════

    def sync_full(self, import_batch_id: Optional[str] = None, workers: int = 5) -> dict:
        """
        从 HANA 全量同步采购数据（两阶段高速版）。

        设计原则：Python 只做搬运，所有过滤/转换/匹配全在 PG 引擎内完成。
        - 阶段1: TRUNCATE origin → HANA 并行读取 → executemany 批量灌入
        - 阶段2: 一条 SQL 完成 过滤+类型转换+汇率匹配+upsert 到 purchase_records
        - 阶段3: SQL upsert 供应商/物料主数据
        """
        if import_batch_id is None:
            import_batch_id = _local_now().strftime("HANA_%Y%m%d%H%M%S")

        stats = self._init_stats("full", import_batch_id)
        logger.info(f"=== 开始 HANA 全量同步（两阶段高速版, workers={workers}） ===")

        # 防御性清理：回滚任何遗留的脏事务
        self.db.rollback()

        # 加 advisory lock 防止并发同步
        _acquire_sync_lock(self.db)

        # ── 阶段1-A: TRUNCATE origin 表（比 DELETE 快几个数量级）──
        t0 = _local_now()
        self.db.execute(text("TRUNCATE TABLE purchase_records_origin RESTART IDENTITY"))
        self.db.commit()
        logger.info("origin 表已 TRUNCATE")

        # ── 阶段1-B: 多进程并行读取 HANA 全量数据（按 BUDAT 分片）──
        hana_rows = fetch_all_data_parallel(workers=workers)
        stats["total_hana_rows"] = len(hana_rows)
        t1 = _local_now()
        logger.info(f"HANA 读取完成：{len(hana_rows)} 行，耗时 {(t1-t0).total_seconds():.1f}s")

        if not hana_rows:
            self._save_state(stats)
            return stats

        # ── 阶段1-C: executemany 批量灌入 origin 表（纯字符串，不做任何转换）──
        self._bulk_insert_origin(hana_rows, import_batch_id)
        self.db.commit()
        t2 = _local_now()
        logger.info(f"origin 表写入完成：{len(hana_rows)} 行，耗时 {(t2-t1).total_seconds():.1f}s")

        # ── 阶段2: PG 内纯 SQL 清洗（一条 SQL 搞定全部逻辑）──
        inserted, updated = self._cleanse_origin(import_batch_id)
        stats["inserted"] = inserted
        stats["updated"] = updated
        t3 = _local_now()
        logger.info(f"清洗完成：inserted={inserted}, updated={updated}，耗时 {(t3-t2).total_seconds():.1f}s")

        # ── 阶段3: SQL 补充供应商/物料主数据 ──
        sup_created, mat_created = self._upsert_master_data_from_origin()
        stats["suppliers_created"] = sup_created
        stats["materials_created"] = mat_created
        t4 = _local_now()
        logger.info(f"主数据补充完成：供应商+{sup_created}, 物料+{mat_created}，耗时 {(t4-t3).total_seconds():.1f}s")

        # ── 记录同步状态 ──
        self._save_state(stats)
        total_elapsed = (t4 - t0).total_seconds()
        logger.info(f"全量同步完成，总耗时 {total_elapsed:.1f}s: {stats}")
        return stats

    def _bulk_insert_origin(self, hana_rows: list, import_batch_id: str):
        """
        用 raw SQL executemany 批量写入 origin 表。
        比 SQLAlchemy ORM bulk_save_objects 快 3-5 倍，因为绕过了 ORM 层的对象构建。
        HANA 返回大写 key，origin 表用小写列名，全部存为 VARCHAR。
        """
        # HANA 大写列名 → origin 小写列名
        hana_to_origin = {col.upper(): col for col in ORIGIN_COLUMNS}

        # 构建 executemany 的列占位符
        cols = ", ".join(ORIGIN_COLUMNS + ["import_batch_id"])
        placeholders = ", ".join([f"%({c})s" for c in ORIGIN_COLUMNS] + ["%(import_batch_id)s"])
        insert_sql = f"INSERT INTO purchase_records_origin ({cols}) VALUES ({placeholders})"

        # 将 HANA 行转为 origin 格式（全部转 str，None → 空字符串）
        batch_params = []
        for row in hana_rows:
            rec = {"import_batch_id": import_batch_id}
            for hana_key, origin_key in hana_to_origin.items():
                val = row.get(hana_key)
                rec[origin_key] = str(val) if val is not None else ""
            batch_params.append(rec)

        # 使用 SQLAlchemy 的 raw connection 执行 executemany
        raw_conn = self.db.connection().connection
        cursor = raw_conn.cursor()
        try:
            # 分批 executemany，每批 10000 行
            batch_size = 10000
            for i in range(0, len(batch_params), batch_size):
                chunk = batch_params[i:i + batch_size]
                cursor.executemany(insert_sql, chunk)
                logger.info(f"origin 写入 {min(i + batch_size, len(batch_params))}/{len(batch_params)}")
        finally:
            cursor.close()

    def _append_to_origin(self, hana_rows: list, import_batch_id: str):
        """
        追加数据到 origin 表（不 TRUNCATE）。
        用于增量/按月同步场景，保留历史原始数据。
        """
        logger.info(f"开始追加 {len(hana_rows)} 行到 origin 表（batch_id={import_batch_id}）")
        self._bulk_insert_origin(hana_rows, import_batch_id)

    def _cleanse_origin(self, import_batch_id: str) -> Tuple[int, int]:
        """
        从 purchase_records_origin 清洗数据到 purchase_records。
        纯 SQL 操作，在 PG 内完成全部逻辑：
        - 过滤：关联方、空物料代码、空物料凭证
        - 类型转换：VARCHAR → DECIMAL / Date / Integer
        - 汇率匹配：LATERAL JOIN exchange_rates 按交易日匹配
        - CNY 金额计算：order_unit_price × quantity × exchange_rate
        - 去重 upsert：ON CONFLICT (material_doc, line_item) DO UPDATE
        
        注意：此方法处理 origin 表中的所有数据（不限 batch_id）
        """
        logger.info(f"开始 SQL 清洗（全量模式）")

        sql = """
        INSERT INTO purchase_records (
            company_code, company_name,
            fiscal_year, transaction_date,
            supplier_code, supplier_name, supplier_category,
            material_code, material_name, specification, material_category, wgbez,
            base_currency, unit,
            quantity, unit_price, amount,
            order_currency, order_unit_price, order_amount,
            exchange_rate, cny_amount,
            invoice_quantity, invoice_unit_price, invoice_amount,
            invoice_tax, invoice_total, invoice_date,
            estimate_quantity, estimate_total, estimate_amount,
            purchase_purpose, po_number,
            material_doc, line_item,
            accounting_doc, movement_type, movement_type_desc,
            reversal_flag, line_item_category, gr_based_invoice, line_item_text,
            data_source, import_batch_id,
            created_at, updated_at
        )
        SELECT
            o.comp_code,
            o.butxt,
            NULLIF(o.gjahr, '')::integer,
            CASE WHEN o.budat ~ '^[0-9]{8}$' AND o.budat > '19000101' THEN o.budat::date ELSE NULL END,
            COALESCE(NULLIF(o.vendor, ''), NULLIF(o.lifnr, '')),
            o.name1,
            o.vbund,
            COALESCE(NULLIF(o.material, ''), NULLIF(o.matnr, '')),
            o.maktx,
            o.groes,
            o.matl_group,
            o.wgbez,
            COALESCE(NULLIF(o.waers, ''), 'CNY'),
            o.erfme,
            NULLIF(o.menge, '')::numeric(18,4),
            NULLIF(o.price_po, '')::numeric(18,4),
            NULLIF(o.dmbtr, '')::numeric(18,2),
            -- order_currency：如实反映 HANA 原始 ZDDHB，为空时保留 NULL，不再强制填 'CNY'
            NULLIF(o.zddhb, ''),
            NULLIF(o.zdj_ddhb, '')::numeric(18,4),
            NULLIF(o.zje_ddhb, '')::numeric(18,2),
            -- exchange_rate：ZDDHB 为空时无真实订单货币，汇率保留 NULL（不在清洗阶段臆造汇率）；
            -- ZDDHB='CNY' 时汇率 1.0；其他币种查汇率表
            CASE
                WHEN NULLIF(o.zddhb, '') IS NULL THEN NULL
                WHEN o.zddhb = 'CNY' THEN 1.0
                ELSE COALESCE(er.exchange_rate, 0)
            END,
            -- cny_amount：优先 订单单价 ZDJ_DDHB × 订单数量 MENGE × 汇率；
            -- 结果为 0 说明无采购或订单单价为 0：此时若 WAERS(本位币)=CNY 直接取 DMBTR 当金额；
            -- WAERS≠CNY 视为异常（海外子公司无订单单价的记录）记 0，需人工核查。
            CASE
                WHEN COALESCE(NULLIF(o.zdj_ddhb, '')::numeric, 0) > 0
                     AND COALESCE(NULLIF(o.menge, '')::numeric, 0) > 0
                THEN NULLIF(o.zdj_ddhb, '')::numeric
                     * NULLIF(o.menge, '')::numeric
                     * CASE WHEN NULLIF(o.zddhb, '') IS NULL OR o.zddhb = 'CNY'
                            THEN 1.0 ELSE COALESCE(er.exchange_rate, 0) END
                WHEN COALESCE(NULLIF(o.waers, ''), 'CNY') = 'CNY'
                THEN NULLIF(o.dmbtr, '')::numeric
                ELSE 0
            END,
            NULL,
            NULLIF(o.price_iv, '')::numeric(18,4),
            NULLIF(o.wrbtr, '')::numeric(18,2),
            NULLIF(o.wrbtr, '')::numeric(18,2),
            NULLIF(o.wrbtr, '')::numeric(18,2),
            CASE WHEN o.budat_iv ~ '^[0-9]{8}$' AND o.budat_iv > '19000101' THEN o.budat_iv::date ELSE NULL END,
            NULLIF(o.menge_es, '')::numeric(18,4),
            NULLIF(o.zgze, '')::numeric(18,2),
            NULLIF(o.wrbtr_es, '')::numeric(18,2),
            o.purpose,
            o.ebeln,
            o.mblnr,
            o.zeile,
            '' AS accounting_doc,
            o.bwart,
            o.btext,
            o.rev,
            o.pstyp,
            o.webre,
            o.remark,
            'HANA' AS data_source,
            :batch_id AS import_batch_id,
            NOW() AS created_at,
            NOW() AS updated_at
        FROM (
            SELECT DISTINCT ON (mblnr, zeile) *
            FROM purchase_records_origin
            WHERE vbund NOT IN ('关联方', '关联方供应商')
              -- 排除无物料代码的行项目（material 与 matnr 强联动，同时空即资产/科目分配类收货，
              -- 属固定资产采购流程，不计入物料采购分析范畴）
              AND COALESCE(NULLIF(material, ''), NULLIF(matnr, '')) IS NOT NULL
              AND NULLIF(mblnr, '') IS NOT NULL
              -- 排除无采购订单的行项目（EBELN 为空或 '0'，多为无 PO 的收货/移动，不属于采购范畴）
              AND NULLIF(NULLIF(ebeln, ''), '0') IS NOT NULL
            ORDER BY mblnr, zeile, id DESC
        ) o
        LEFT JOIN LATERAL (
            SELECT er.exchange_rate
            FROM exchange_rates er
            WHERE er.from_currency = UPPER(COALESCE(NULLIF(o.zddhb, ''), 'CNY'))
              AND er.effective_date <= CASE WHEN o.budat ~ '^[0-9]{8}$' AND o.budat > '19000101' THEN o.budat::date ELSE NULL END
              AND (er.expiry_date IS NULL OR er.expiry_date >= CASE WHEN o.budat ~ '^[0-9]{8}$' AND o.budat > '19000101' THEN o.budat::date ELSE NULL END)
            ORDER BY er.effective_date DESC
            LIMIT 1
        ) er ON TRUE
        ON CONFLICT (material_doc, line_item) DO UPDATE SET
            company_code = EXCLUDED.company_code,
            company_name = EXCLUDED.company_name,
            fiscal_year = EXCLUDED.fiscal_year,
            transaction_date = EXCLUDED.transaction_date,
            supplier_code = EXCLUDED.supplier_code,
            supplier_name = EXCLUDED.supplier_name,
            supplier_category = EXCLUDED.supplier_category,
            material_code = EXCLUDED.material_code,
            material_name = EXCLUDED.material_name,
            specification = EXCLUDED.specification,
            material_category = EXCLUDED.material_category,
            wgbez = EXCLUDED.wgbez,
            base_currency = EXCLUDED.base_currency,
            unit = EXCLUDED.unit,
            quantity = EXCLUDED.quantity,
            unit_price = EXCLUDED.unit_price,
            amount = EXCLUDED.amount,
            order_currency = EXCLUDED.order_currency,
            order_unit_price = EXCLUDED.order_unit_price,
            order_amount = EXCLUDED.order_amount,
            exchange_rate = EXCLUDED.exchange_rate,
            cny_amount = EXCLUDED.cny_amount,
            invoice_quantity = EXCLUDED.invoice_quantity,
            invoice_unit_price = EXCLUDED.invoice_unit_price,
            invoice_amount = EXCLUDED.invoice_amount,
            invoice_tax = EXCLUDED.invoice_tax,
            invoice_total = EXCLUDED.invoice_total,
            invoice_date = EXCLUDED.invoice_date,
            estimate_quantity = EXCLUDED.estimate_quantity,
            estimate_total = EXCLUDED.estimate_total,
            estimate_amount = EXCLUDED.estimate_amount,
            purchase_purpose = EXCLUDED.purchase_purpose,
            po_number = EXCLUDED.po_number,
            accounting_doc = EXCLUDED.accounting_doc,
            movement_type = EXCLUDED.movement_type,
            movement_type_desc = EXCLUDED.movement_type_desc,
            reversal_flag = EXCLUDED.reversal_flag,
            line_item_category = EXCLUDED.line_item_category,
            gr_based_invoice = EXCLUDED.gr_based_invoice,
            line_item_text = EXCLUDED.line_item_text,
            data_source = EXCLUDED.data_source,
            import_batch_id = EXCLUDED.import_batch_id,
            deleted_at = NULL,
            updated_at = NOW()
        """

        result = self.db.execute(text(sql), {"batch_id": import_batch_id})
        self.db.commit()
        affected = result.rowcount
        logger.info(f"清洗完成：影响 {affected} 行")
        return affected, 0

    def _cleanse_origin_by_batch(self, import_batch_id: str) -> Tuple[int, int]:
        """
        从 purchase_records_origin 清洗指定批次的数据到 purchase_records。
        与 _cleanse_origin 的区别：只处理指定 batch_id 的数据。

        用于增量/按月同步场景，避免重复处理历史数据。

        修复记录（2026-07-27）：
            INSERT 头部漏写 wgbez 列，SELECT 有 46 个表达式而 INSERT 只声明 45 列，
            导致 "INSERT has more expressions than target columns" 报错，
            月度定时同步自 2026-07-02 起一直失败。补齐 wgbez 后 SELECT/INSERT 一致。
        """
        logger.info(f"开始 SQL 清洗（批次模式 batch_id={import_batch_id}）")

        sql = """
        INSERT INTO purchase_records (
            company_code, company_name,
            fiscal_year, transaction_date,
            supplier_code, supplier_name, supplier_category,
            material_code, material_name, specification, material_category, wgbez,
            base_currency, unit,
            quantity, unit_price, amount,
            order_currency, order_unit_price, order_amount,
            exchange_rate, cny_amount,
            invoice_quantity, invoice_unit_price, invoice_amount,
            invoice_tax, invoice_total, invoice_date,
            estimate_quantity, estimate_total, estimate_amount,
            purchase_purpose, po_number,
            material_doc, line_item,
            accounting_doc, movement_type, movement_type_desc,
            reversal_flag, line_item_category, gr_based_invoice, line_item_text,
            data_source, import_batch_id,
            created_at, updated_at
        )
        SELECT
            o.comp_code,
            o.butxt,
            NULLIF(o.gjahr, '')::integer,
            CASE WHEN o.budat ~ '^[0-9]{8}$' AND o.budat > '19000101' THEN o.budat::date ELSE NULL END,
            COALESCE(NULLIF(o.vendor, ''), NULLIF(o.lifnr, '')),
            o.name1,
            o.vbund,
            COALESCE(NULLIF(o.material, ''), NULLIF(o.matnr, '')),
            o.maktx,
            o.groes,
            o.matl_group,
            o.wgbez,
            COALESCE(NULLIF(o.waers, ''), 'CNY'),
            o.erfme,
            NULLIF(o.menge, '')::numeric(18,4),
            NULLIF(o.price_po, '')::numeric(18,4),
            NULLIF(o.dmbtr, '')::numeric(18,2),
            -- order_currency：如实反映 HANA 原始 ZDDHB，为空时保留 NULL，不再强制填 'CNY'
            NULLIF(o.zddhb, ''),
            NULLIF(o.zdj_ddhb, '')::numeric(18,4),
            NULLIF(o.zje_ddhb, '')::numeric(18,2),
            -- exchange_rate：ZDDHB 为空时无真实订单货币，汇率保留 NULL（不在清洗阶段臆造汇率）；
            -- ZDDHB='CNY' 时汇率 1.0；其他币种查汇率表
            CASE
                WHEN NULLIF(o.zddhb, '') IS NULL THEN NULL
                WHEN o.zddhb = 'CNY' THEN 1.0
                ELSE COALESCE(er.exchange_rate, 0)
            END,
            -- cny_amount：优先 订单单价 ZDJ_DDHB × 订单数量 MENGE × 汇率；
            -- 结果为 0 说明无采购或订单单价为 0：此时若 WAERS(本位币)=CNY 直接取 DMBTR 当金额；
            -- WAERS≠CNY 视为异常（海外子公司无订单单价的记录）记 0，需人工核查。
            CASE
                WHEN COALESCE(NULLIF(o.zdj_ddhb, '')::numeric, 0) > 0
                     AND COALESCE(NULLIF(o.menge, '')::numeric, 0) > 0
                THEN NULLIF(o.zdj_ddhb, '')::numeric
                     * NULLIF(o.menge, '')::numeric
                     * CASE WHEN NULLIF(o.zddhb, '') IS NULL OR o.zddhb = 'CNY'
                            THEN 1.0 ELSE COALESCE(er.exchange_rate, 0) END
                WHEN COALESCE(NULLIF(o.waers, ''), 'CNY') = 'CNY'
                THEN NULLIF(o.dmbtr, '')::numeric
                ELSE 0
            END,
            NULL,
            NULLIF(o.price_iv, '')::numeric(18,4),
            NULLIF(o.wrbtr, '')::numeric(18,2),
            NULLIF(o.wrbtr, '')::numeric(18,2),
            NULLIF(o.wrbtr, '')::numeric(18,2),
            CASE WHEN o.budat_iv ~ '^[0-9]{8}$' AND o.budat_iv > '19000101' THEN o.budat_iv::date ELSE NULL END,
            NULLIF(o.menge_es, '')::numeric(18,4),
            NULLIF(o.zgze, '')::numeric(18,2),
            NULLIF(o.wrbtr_es, '')::numeric(18,2),
            o.purpose,
            o.ebeln,
            o.mblnr,
            o.zeile,
            '' AS accounting_doc,
            o.bwart,
            o.btext,
            o.rev,
            o.pstyp,
            o.webre,
            o.remark,
            'HANA' AS data_source,
            :batch_id AS import_batch_id,
            NOW() AS created_at,
            NOW() AS updated_at
        FROM (
            SELECT DISTINCT ON (mblnr, zeile) *
            FROM purchase_records_origin
            WHERE import_batch_id = :batch_id
              AND vbund NOT IN ('关联方', '关联方供应商')
              -- 排除无物料代码的行项目（material 与 matnr 强联动，同时空即资产/科目分配类收货，
              -- 属固定资产采购流程，不计入物料采购分析范畴）
              AND COALESCE(NULLIF(material, ''), NULLIF(matnr, '')) IS NOT NULL
              AND NULLIF(mblnr, '') IS NOT NULL
              -- 排除无采购订单的行项目（EBELN 为空或 '0'，多为无 PO 的收货/移动，不属于采购范畴）
              AND NULLIF(NULLIF(ebeln, ''), '0') IS NOT NULL
            ORDER BY mblnr, zeile, id DESC
        ) o
        LEFT JOIN LATERAL (
            SELECT er.exchange_rate
            FROM exchange_rates er
            WHERE er.from_currency = UPPER(COALESCE(NULLIF(o.zddhb, ''), 'CNY'))
              AND er.effective_date <= CASE WHEN o.budat ~ '^[0-9]{8}$' AND o.budat > '19000101' THEN o.budat::date ELSE NULL END
              AND (er.expiry_date IS NULL OR er.expiry_date >= CASE WHEN o.budat ~ '^[0-9]{8}$' AND o.budat > '19000101' THEN o.budat::date ELSE NULL END)
            ORDER BY er.effective_date DESC
            LIMIT 1
        ) er ON TRUE
        ON CONFLICT (material_doc, line_item) DO UPDATE SET
            company_code = EXCLUDED.company_code,
            company_name = EXCLUDED.company_name,
            fiscal_year = EXCLUDED.fiscal_year,
            transaction_date = EXCLUDED.transaction_date,
            supplier_code = EXCLUDED.supplier_code,
            supplier_name = EXCLUDED.supplier_name,
            supplier_category = EXCLUDED.supplier_category,
            material_code = EXCLUDED.material_code,
            material_name = EXCLUDED.material_name,
            specification = EXCLUDED.specification,
            material_category = EXCLUDED.material_category,
            wgbez = EXCLUDED.wgbez,
            base_currency = EXCLUDED.base_currency,
            unit = EXCLUDED.unit,
            quantity = EXCLUDED.quantity,
            unit_price = EXCLUDED.unit_price,
            amount = EXCLUDED.amount,
            order_currency = EXCLUDED.order_currency,
            order_unit_price = EXCLUDED.order_unit_price,
            order_amount = EXCLUDED.order_amount,
            exchange_rate = EXCLUDED.exchange_rate,
            cny_amount = EXCLUDED.cny_amount,
            invoice_quantity = EXCLUDED.invoice_quantity,
            invoice_unit_price = EXCLUDED.invoice_unit_price,
            invoice_amount = EXCLUDED.invoice_amount,
            invoice_tax = EXCLUDED.invoice_tax,
            invoice_total = EXCLUDED.invoice_total,
            invoice_date = EXCLUDED.invoice_date,
            estimate_quantity = EXCLUDED.estimate_quantity,
            estimate_total = EXCLUDED.estimate_total,
            estimate_amount = EXCLUDED.estimate_amount,
            purchase_purpose = EXCLUDED.purchase_purpose,
            po_number = EXCLUDED.po_number,
            accounting_doc = EXCLUDED.accounting_doc,
            movement_type = EXCLUDED.movement_type,
            movement_type_desc = EXCLUDED.movement_type_desc,
            reversal_flag = EXCLUDED.reversal_flag,
            line_item_category = EXCLUDED.line_item_category,
            gr_based_invoice = EXCLUDED.gr_based_invoice,
            line_item_text = EXCLUDED.line_item_text,
            data_source = EXCLUDED.data_source,
            import_batch_id = EXCLUDED.import_batch_id,
            deleted_at = NULL,
            updated_at = NOW()
        """

        result = self.db.execute(text(sql), {"batch_id": import_batch_id})
        self.db.commit()
        affected = result.rowcount
        logger.info(f"批次清洗完成：影响 {affected} 行")
        return affected, 0

    def _upsert_master_data_from_origin(self) -> Tuple[int, int]:
        """
        从 origin 表中提取并 upsert 供应商/物料主数据（纯 SQL）。
        比 Python 逐行处理快 10 倍以上。
        """
        # ── 供应商 upsert ──
        supplier_sql = """
        INSERT INTO suppliers (supplier_code, supplier_name, created_at, updated_at)
        SELECT
            sc AS supplier_code,
            COALESCE(NULLIF(name1, ''), sc) AS supplier_name,
            NOW(), NOW()
        FROM (
            SELECT DISTINCT ON (COALESCE(NULLIF(vendor, ''), NULLIF(lifnr, '')))
                COALESCE(NULLIF(vendor, ''), NULLIF(lifnr, '')) AS sc,
                name1
            FROM purchase_records_origin
            WHERE COALESCE(NULLIF(vendor, ''), NULLIF(lifnr, '')) IS NOT NULL
        ) sub
        ON CONFLICT (supplier_code) DO UPDATE SET
            supplier_name = CASE
                WHEN suppliers.supplier_name = suppliers.supplier_code
                     AND EXCLUDED.supplier_name <> EXCLUDED.supplier_code
                THEN EXCLUDED.supplier_name
                ELSE suppliers.supplier_name
            END,
            updated_at = NOW()
        """
        result = self.db.execute(text(supplier_sql))
        sup_created = result.rowcount

        # ── 物料 upsert ──
        material_sql = """
        INSERT INTO materials (material_code, material_name, created_at, updated_at)
        SELECT
            mc AS material_code,
            COALESCE(NULLIF(maktx, ''), mc) AS material_name,
            NOW(), NOW()
        FROM (
            SELECT DISTINCT ON (COALESCE(NULLIF(material, ''), NULLIF(matnr, '')))
                COALESCE(NULLIF(material, ''), NULLIF(matnr, '')) AS mc,
                maktx
            FROM purchase_records_origin
            WHERE COALESCE(NULLIF(material, ''), NULLIF(matnr, '')) IS NOT NULL
        ) sub
        ON CONFLICT (material_code) DO UPDATE SET
            material_name = CASE
                WHEN materials.material_name = materials.material_code
                     AND EXCLUDED.material_name <> EXCLUDED.material_code
                THEN EXCLUDED.material_name
                ELSE materials.material_name
            END,
            updated_at = NOW()
        """
        result = self.db.execute(text(material_sql))
        mat_created = result.rowcount
        self.db.commit()

        logger.info(f"主数据 upsert 完成：供应商影响 {sup_created} 行, 物料影响 {mat_created} 行")
        return sup_created, mat_created

    def _upsert_master_data_from_origin_by_batch(self, import_batch_id: str) -> Tuple[int, int]:
        """
        从 origin 表中提取指定批次的数据并 upsert 供应商/物料主数据（纯 SQL）。
        与 _upsert_master_data_from_origin 的区别：只处理指定 batch_id 的数据。
        
        用于增量/按月同步场景，避免重复处理历史数据。
        """
        # ── 供应商 upsert ─
        supplier_sql = """
        INSERT INTO suppliers (supplier_code, supplier_name, created_at, updated_at)
        SELECT
            sc AS supplier_code,
            COALESCE(NULLIF(name1, ''), sc) AS supplier_name,
            NOW(), NOW()
        FROM (
            SELECT DISTINCT ON (COALESCE(NULLIF(vendor, ''), NULLIF(lifnr, '')))
                COALESCE(NULLIF(vendor, ''), NULLIF(lifnr, '')) AS sc,
                name1
            FROM purchase_records_origin
            WHERE import_batch_id = :batch_id
              AND COALESCE(NULLIF(vendor, ''), NULLIF(lifnr, '')) IS NOT NULL
        ) sub
        ON CONFLICT (supplier_code) DO UPDATE SET
            supplier_name = CASE
                WHEN suppliers.supplier_name = suppliers.supplier_code
                     AND EXCLUDED.supplier_name <> EXCLUDED.supplier_code
                THEN EXCLUDED.supplier_name
                ELSE suppliers.supplier_name
            END,
            updated_at = NOW()
        """
        result = self.db.execute(text(supplier_sql), {"batch_id": import_batch_id})
        sup_created = result.rowcount

        # ── 物料 upsert ──
        material_sql = """
        INSERT INTO materials (material_code, material_name, created_at, updated_at)
        SELECT
            mc AS material_code,
            COALESCE(NULLIF(maktx, ''), mc) AS material_name,
            NOW(), NOW()
        FROM (
            SELECT DISTINCT ON (COALESCE(NULLIF(material, ''), NULLIF(matnr, '')))
                COALESCE(NULLIF(material, ''), NULLIF(matnr, '')) AS mc,
                maktx
            FROM purchase_records_origin
            WHERE import_batch_id = :batch_id
              AND COALESCE(NULLIF(material, ''), NULLIF(matnr, '')) IS NOT NULL
        ) sub
        ON CONFLICT (material_code) DO UPDATE SET
            material_name = CASE
                WHEN materials.material_name = materials.material_code
                     AND EXCLUDED.material_name <> EXCLUDED.material_code
                THEN EXCLUDED.material_name
                ELSE materials.material_name
            END,
            updated_at = NOW()
        """
        result = self.db.execute(text(material_sql), {"batch_id": import_batch_id})
        mat_created = result.rowcount
        self.db.commit()

        logger.info(f"批次主数据 upsert 完成：供应商影响 {sup_created} 行, 物料影响 {mat_created} 行")
        return sup_created, mat_created

    # ═══════════════════════════════════════════
    # 增量同步
    # ═══════════════════════════════════════════

    def sync_incremental(self, import_batch_id: Optional[str] = None) -> dict:
        """
        HANA 增量同步。
        1) 读取 HANA 中 RECORDMODE IN ('N','U','D') 的行
        2) 映射后与本地 diff 比对（新增/更新）
        3) RECORDMODE='D' 的行：从本地软删除
        """
        if import_batch_id is None:
            import_batch_id = _local_now().strftime("HANA_INCR_%Y%m%d%H%M%S")

        stats = self._init_stats("incremental", import_batch_id)
        logger.info("=== 开始 HANA 增量同步 ===")

        # 防御性清理 + advisory lock
        self.db.rollback()
        _acquire_sync_lock(self.db)

        # 第1步：读取 HANA 增量数据（仅 RECORDMODE = N/U/D 的行）
        hana_rows = fetch_all_incremental_data()
        stats["total_hana_rows"] = len(hana_rows)
        logger.info(f"HANA 增量读取完成，共 {len(hana_rows)} 行")

        if not hana_rows:
            logger.info("HANA 增量数据为空，无需同步")
            self._save_state(stats)
            return stats

        # 第2步：按 RECORDMODE 分流
        delete_rows = [r for r in hana_rows if _clean_str(r.get("RECORDMODE")) == "D"]
        upsert_rows = [r for r in hana_rows if _clean_str(r.get("RECORDMODE")) in ("N", "U", "")]

        # 第3步：处理待删除行
        if delete_rows:
            delete_keys = []
            for row in delete_rows:
                doc = _clean_str(row.get("MBLNR"))
                item = _clean_str(row.get("ZEILE"))
                if doc:
                    delete_keys.append((doc, item))
            if delete_keys:
                # 构建精确 (doc, item) 键集合
                key_set = set(delete_keys)
                # 分批按 material_doc 查询，Python 侧精确匹配 line_item
                to_delete = []
                docs_set = list({k[0] for k in delete_keys})
                for i in range(0, len(docs_set), 500):
                    chunk = docs_set[i : i + 500]
                    candidates = (
                        self.db.query(PurchaseRecord)
                        .filter(PurchaseRecord.material_doc.in_(chunk))
                        .all()
                    )
                    for rec in candidates:
                        if (rec.material_doc, rec.line_item) in key_set:
                            to_delete.append(rec)
                for rec in to_delete:
                    rec.import_batch_id = import_batch_id
                    rec.data_source = "HANA_DELETED"       # 标记为 HANA 已删除
                    rec.updated_at = _local_now()
                self.db.flush()
                stats["total_deleted"] = len(to_delete)
                logger.info(f"标记删除 {stats['total_deleted']} 条记录")

        # 第4步：映射 upsert 行
        mapped_records, supplier_data, material_data = self._map_batch(
            upsert_rows, stats
        )

        # 第5步：补充主数据
        stats["suppliers_created"], stats["materials_created"] = (
            self._upsert_master_data(supplier_data, material_data)
        )

        # 第6步：diff 比对（只处理 upsert 行）
        self._apply_diff(mapped_records, import_batch_id, stats)

        # 第7步：记录同步状态
        self._save_state(stats)
        logger.info(f"增量同步完成: {stats}")
        return stats

    # ═══════════════════════════════════════════
    # 按月定时同步（当月 + 上月，可覆盖更新）
    # ═══════════════════════════════════════════

    def sync_by_date_range(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        lookback_months: int = DEFAULT_LOOKBACK_MONTHS,
    ) -> dict:
        """
        按日期范围从 HANA 同步数据，覆盖更新（两阶段模式）。
        默认窗口：[上(lookback_months-1)月 1 日 ~ 今天]，即默认覆盖前 2 个月 + 当月。

        设计意图：每日凌晨定时执行，刷新最近 N 个月数据。
        - 阶段0: advisory lock + 清理 origin 表同日期范围旧批次（防无界增长）
        - 阶段1: HANA → origin（追加新批次，不 TRUNCATE）
        - 阶段2: origin → purchase_records（SQL 清洗，只处理新批次）
        - 阶段3: SQL upsert 供应商/物料主数据
        - 阶段4: 反向删除比对——本地有 + 范围内 + HANA 无的记录置 deleted_at
                 （HANA 真删 / 冲销的记录在本地不再"活跃"，但保留审计痕迹）

        更早日期的明细不受影响（防止 ERP 旧单据被人为修改后污染历史数据）。

        Args:
            start_date: 起始日期 YYYY-MM-DD，默认 (上 lookback_months-1 月 1 日)
            end_date:   结束日期 YYYY-MM-DD，默认今天
            lookback_months: 回看月数，默认 2（覆盖上月+当月）
        """
        today = _local_today()
        if end_date is None:
            end_date = today.isoformat()
        if start_date is None:
            # 推导 start_date = 当前月 - (lookback_months - 1) 月的 1 日
            # 例：lookback_months=2 且今天是 7/2 → start = 6/1（覆盖 6 月 + 7 月）
            # 例：lookback_months=2 且今天是 1/15 → start = 去年 12/1（跨年覆盖）
            start_date = self._subtract_months(today, lookback_months - 1).replace(day=1).isoformat()

        # 转换为 HANA BUDAT 比较用的 YYYYMMDD 格式
        start_fmt = start_date.replace("-", "")
        end_fmt = end_date.replace("-", "")

        import_batch_id = _local_now().strftime("HANA_MONTHLY_%Y%m%d%H%M%S")
        stats = self._init_stats("monthly", import_batch_id)
        stats["date_range"] = {"start": start_date, "end": end_date}
        logger.info(f"=== 开始月度定时同步（两阶段模式）: {start_date} ~ {end_date} ===")

        # 防御性清理 + advisory lock
        self.db.rollback()
        _acquire_sync_lock(self.db)

        # ─ 阶段0: 清理 origin 表同日期范围内旧批次（防无界增长）──
        # 多次月度同步会在 origin 累积同日期范围数据，每次清洗都用 DISTINCT ON 去重，
        # 数据正确性不受影响，但表会膨胀（实测 4 周累积 100w+ 行）。
        # 策略：删除 origin 表中 BUDAT 落在本次范围 [start_fmt, end_fmt] 的所有旧行，
        #      再写入本次新批次，保证同日期范围只保留最新一次同步结果。
        self._purge_origin_by_budat_range(start_fmt, end_fmt)

        # ─ 阶段1: HANA 读取 → origin 追加 ──
        t0 = _local_now()
        hana_rows = fetch_data_by_date_range(start_fmt, end_fmt)
        stats["total_hana_rows"] = len(hana_rows)
        t1 = _local_now()
        logger.info(f"HANA 日期范围读取完成，共 {len(hana_rows)} 行，耗时 {(t1-t0).total_seconds():.1f}s")

        if not hana_rows:
            # HANA 该范围无数据但仍要做反向删除比对（可能整段范围数据都被 HANA 删了）
            logger.info("日期范围内 HANA 无数据，仍执行反向删除比对")
            deleted = self._soft_delete_missing_records(set(), start_date, end_date)
            stats["total_deleted"] = deleted
            self._save_state(stats)
            return stats

        # 追加到 origin 表（不 TRUNCATE）
        self._append_to_origin(hana_rows, import_batch_id)
        self.db.commit()
        t2 = _local_now()
        logger.info(f"origin 追加完成：{len(hana_rows)} 行，耗时 {(t2-t1).total_seconds():.1f}s")

        # ─ 阶段2: PG 内纯 SQL 清洗（只处理新批次）──
        inserted, updated = self._cleanse_origin_by_batch(import_batch_id)
        stats["inserted"] = inserted
        stats["updated"] = updated
        t3 = _local_now()
        logger.info(f"清洗完成：inserted={inserted}, updated={updated}，耗时 {(t3-t2).total_seconds():.1f}s")

        # ── 阶段3: SQL 补充供应商/物料主数据 ──
        sup_created, mat_created = self._upsert_master_data_from_origin_by_batch(import_batch_id)
        stats["suppliers_created"] = sup_created
        stats["materials_created"] = mat_created
        t4 = _local_now()
        logger.info(f"主数据补充完成：供应商+{sup_created}, 物料+{mat_created}，耗时 {(t4-t3).total_seconds():.1f}s")

        # ── 阶段4: 反向删除比对 ──
        # 收集本次拉取到的所有 (mblnr, zeile) 键集合
        present_keys = set()
        for row in hana_rows:
            doc = _clean_str(row.get("MBLNR"))
            item = _clean_str(row.get("ZEILE"))
            if doc:
                present_keys.add((doc, item))
        deleted = self._soft_delete_missing_records(present_keys, start_date, end_date)
        stats["total_deleted"] = deleted
        t5 = _local_now()
        logger.info(f"反向删除比对完成：软删除 {deleted} 条，耗时 {(t5-t4).total_seconds():.1f}s")

        # ── 记录同步状态 ──
        self._save_state(stats)
        total_elapsed = (t5 - t0).total_seconds()
        logger.info(f"月度定时同步完成，总耗时 {total_elapsed:.1f}s: {stats}")
        return stats

    @staticmethod
    def _subtract_months(d: date, months: int) -> date:
        """从给定日期减去 N 个自然月（不依赖 dateutil）。
        例：2026-01-15 减 1 个月 → 2025-12-15；
            2026-03-31 减 1 个月 → 2025-02-28（取目标月最后一天）。
        """
        if months <= 0:
            return d
        # 计算目标年月
        idx = d.year * 12 + (d.month - 1) - months
        new_year, new_month = divmod(idx, 12)
        new_month += 1
        # 目标月最后一天截断
        last_day = calendar.monthrange(new_year, new_month)[1]
        return date(new_year, new_month, min(d.day, last_day))

    def _purge_origin_by_budat_range(self, start_fmt: str, end_fmt: str) -> int:
        """清理 origin 表中 BUDAT 在 [start_fmt, end_fmt] 范围内的所有旧行。
        用于月度同步前防止 origin 无界增长。YYYYMMDD 字符串字典序与日期序一致。
        """
        sql = text(
            "DELETE FROM purchase_records_origin "
            "WHERE budat <> '' AND budat >= :s AND budat <= :e"
        )
        result = self.db.execute(sql, {"s": start_fmt, "e": end_fmt})
        self.db.commit()
        deleted = result.rowcount or 0
        if deleted > 0:
            logger.info(
                f"清理 origin 表 BUDAT 范围 [{start_fmt}, {end_fmt}] 旧数据：{deleted} 行"
            )
        return deleted

    def _soft_delete_missing_records(
        self,
        present_keys: set,
        start_date: str,
        end_date: str,
    ) -> int:
        """反向删除比对：本地 purchase_records 中 transaction_date 落在
        [start_date, end_date] 范围、且 (material_doc, line_item) 不在本次
        HANA 拉取键集合中的记录，置 deleted_at = NOW()（软删除）。

        语义：HANA 视图已经把这些记录删/冲销，本地不应再视为有效。
        仅范围比对，不波及历史范围外记录。

        Args:
            present_keys: 本次 HANA 拉取到的 {(material_doc, line_item)} 集合
            start_date / end_date: ISO YYYY-MM-DD 字符串
        Returns:
            被软删除的记录数
        """
        # 范围内本地活跃记录（deleted_at IS NULL 且来自 HANA 的记录）
        rows = (
            self.db.query(PurchaseRecord.id, PurchaseRecord.material_doc, PurchaseRecord.line_item)
            .filter(
                PurchaseRecord.deleted_at.is_(None),
                PurchaseRecord.transaction_date >= start_date,
                PurchaseRecord.transaction_date <= end_date,
                PurchaseRecord.data_source == "HANA",
            )
            .all()
        )
        if not rows:
            return 0

        to_delete_ids = [
            rid for rid, doc, item in rows
            if (doc or "", item or "") not in present_keys
        ]
        if not to_delete_ids:
            return 0

        # 批量 UPDATE 设置 deleted_at；分批避免单次 IN 列表过长
        BATCH = 1000
        soft_deleted = 0
        now = _local_now()
        for i in range(0, len(to_delete_ids), BATCH):
            chunk = to_delete_ids[i : i + BATCH]
            updated = (
                self.db.query(PurchaseRecord)
                .filter(PurchaseRecord.id.in_(chunk))
                .update({PurchaseRecord.deleted_at: now}, synchronize_session=False)
            )
            soft_deleted += updated
        self.db.commit()
        return soft_deleted

    # ═══════════════════════════════════════════
    # 内部辅助方法
    # ═══════════════════════════════════════════

    def _init_stats(self, sync_type: str, batch_id: str) -> dict:
        return {
            "sync_type": sync_type,
            "batch_id": batch_id,
            "total_hana_rows": 0,
            "filtered_related": 0,
            "filtered_empty_material": 0,
            "filtered_empty_doc": 0,
            "mapped": 0,
            "inserted": 0,
            "updated": 0,
            "duplicates_skipped": 0,
            "total_deleted": 0,
            "suppliers_created": 0,
            "materials_created": 0,
            "errors": [],
        }

    def _map_batch(
        self, rows: list, stats: dict
    ) -> Tuple[List[dict], Dict[str, str], Dict[str, str]]:
        """逐行映射 HANA 数据，收集供应商/物料主数据"""
        mapped = []
        supplier_data = {}
        material_data = {}

        # 预收集所有币种和交易日，批量预加载汇率（避免逐行 DB 查询）
        currencies = set()
        dates = set()
        for row in rows:
            cur = _clean_str(row.get("ZDDHB"), "CNY").upper()
            if cur != "CNY":
                currencies.add(cur)
            txn_d = _parse_date(row.get("BUDAT"))
            if txn_d:
                dates.add(txn_d)
        if currencies and dates:
            self._preload_exchange_rates(currencies, dates)

        for row in rows:
            try:
                record_data = self._map_row(row)
                if record_data is None:
                    # 统计过滤原因
                    supplier_cat = _clean_str(row.get("VBUND"))
                    material_code = _clean_str(row.get("MATERIAL") or row.get("MATNR"))
                    material_doc = _clean_str(row.get("MBLNR"))
                    if supplier_cat in RELATED_PARTY_VALUES:
                        stats["filtered_related"] += 1
                    elif not material_code:
                        stats["filtered_empty_material"] += 1
                    elif not material_doc:
                        stats["filtered_empty_doc"] += 1
                    else:
                        stats["filtered_empty_material"] += 1
                    continue

                sc = record_data.get("supplier_code", "")
                mc = record_data.get("material_code", "")
                sn = record_data.get("supplier_name", "")
                mn = record_data.get("material_name", "")

                if sc:
                    supplier_data[sc] = sn
                if mc:
                    material_data[mc] = mn

                mapped.append(record_data)
                stats["mapped"] += 1

            except Exception as e:
                stats["errors"].append({
                    "row": str(row.get("MBLNR", "?")),
                    "error": str(e),
                })

        logger.info(
            f"映射完成：有效 {stats['mapped']} 条，"
            f"关联方 {stats['filtered_related']}，"
            f"空物料 {stats['filtered_empty_material']}，"
            f"空凭证 {stats['filtered_empty_doc']}"
        )
        return mapped, supplier_data, material_data

    def _apply_diff(
        self,
        mapped_records: List[dict],
        import_batch_id: str,
        stats: dict,
    ):
        """diff 比对后执行插入/更新"""
        if not mapped_records:
            return

        diff = self._diff_with_local(mapped_records, import_batch_id)

        # ── 批量插入 ──
        if diff["to_insert"]:
            records = [PurchaseRecord(**rd) for rd in diff["to_insert"]]
            self.db.bulk_save_objects(records)
            stats["inserted"] = len(diff["to_insert"])
            logger.info(f"新增 {stats['inserted']} 条")

        # ── 逐条更新（哈希变化的记录） ──
        if diff["to_update"]:
            update_count = 0
            for rd in diff["to_update"]:
                update_id = rd.pop("_update_id", None)
                if update_id:
                    rec = self.db.query(PurchaseRecord).get(update_id)
                    if rec:
                        # 只更新业务字段
                        for k, v in rd.items():
                            if hasattr(rec, k) and k not in ("id", "_update_id"):
                                setattr(rec, k, v)
                        rec.updated_at = _local_now()
                        update_count += 1
            stats["updated"] = update_count
            logger.info(f"更新 {stats['updated']} 条")
            self.db.flush()

        self.db.commit()

    def _save_state(self, stats: dict):
        """记录本次同步状态到 hana_sync_state 表"""
        state = HanaSyncState(
            sync_type=stats["sync_type"],
            last_sync_at=_local_now(),
            last_batch_id=stats["batch_id"],
            total_hana_rows=stats["total_hana_rows"],
            total_inserted=stats["inserted"],
            total_updated=stats["updated"],
            total_deleted=stats.get("total_deleted", 0),
            status="completed",
            error_message=(
                "; ".join(e["error"] for e in stats["errors"][:5])
                if stats["errors"] else None
            ),
        )
        self.db.add(state)
        self.db.commit()

    # ═══════════════════════════════════════════
    # 同步状态查询
    # ═══════════════════════════════════════════

    @staticmethod
    def get_last_sync_state(db: Session) -> Optional[dict]:
        """获取最近一次同步状态"""
        state = (
            db.query(HanaSyncState)
            .order_by(HanaSyncState.last_sync_at.desc())
            .first()
        )
        if not state:
            return None
        return {
            "id": state.id,
            "sync_type": state.sync_type,
            "last_sync_at": state.last_sync_at.isoformat() if state.last_sync_at else None,
            "last_batch_id": state.last_batch_id,
            "total_hana_rows": state.total_hana_rows,
            "total_inserted": state.total_inserted,
            "total_updated": state.total_updated,
            "total_deleted": state.total_deleted,
            "status": state.status,
            "error_message": state.error_message,
        }

    @staticmethod
    def get_record_count(db: Session) -> int:
        """返回当前 purchase_records 有效记录总数"""
        return db.query(PurchaseRecord).count()
