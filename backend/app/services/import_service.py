"""
数据导入服务
处理Excel文件导入，含汇率转换逻辑
"""
import pandas as pd
from sqlalchemy.orm import Session
from ..models import PurchaseRecord, Supplier, Material, Company, ExchangeRate
from ..services import exchange_rate_service
from datetime import datetime
from decimal import Decimal
import os
import logging

logger = logging.getLogger(__name__)


# 公司本位币配置（与 purchase analysis 项目一致）
BASE_CURRENCY_CONFIG = {
    '1000': 'CNY', '1100': 'CNY', '1200': 'CNY', '1300': 'CNY',
    '1400': 'CNY', '1500': 'CNY', '1600': 'CNY', '1700': 'CNY',
    '1800': 'CNY', '2000': 'CNY', '2100': 'CNY', '2200': 'CNY',
    '2300': 'CNY', '2400': 'CNY', '2500': 'CNY', '2600': 'CNY',
    '3000': 'USD', '3100': 'EUR', '3200': 'HKD', '3300': 'AED',
    '4000': 'CNY', '4100': 'CNY', '4200': 'CNY', '4300': 'CNY',
    '4400': 'CNY', '4500': 'CNY', '4600': 'CNY', '4700': 'CNY',
    '5000': 'CNY', '5100': 'CNY', '5200': 'CNY', '5300': 'CNY',
    '5400': 'CNY', '5500': 'CNY', '5600': 'CNY', '5700': 'CNY',
    '5800': 'CNY', '5900': 'CNY', '6000': 'CNY', '6100': 'CNY',
    '6200': 'CNY', '6300': 'CNY', '6400': 'CNY', '6500': 'CNY',
    '6600': 'CNY', '6700': 'CNY', '6800': 'CNY', '6900': 'CNY',
    '7000': 'CNY', '7100': 'AUD', '7200': 'CNY', '7300': 'CNY',
    '7400': 'CNY', '7500': 'CNY', '7600': 'CNY', '7700': 'CNY',
    '7800': 'CNY', '7900': 'CNY', '8000': 'CNY', '8100': 'CNY',
    '8200': 'CNY', '8300': 'CNY', '8400': 'CNY', '8500': 'CNY',
}


class ImportService:
    """数据导入服务类"""

    def __init__(self, db: Session):
        self.db = db
        self._load_exchange_rates()

    def _load_exchange_rates(self):
        """从数据库加载当前生效的汇率配置（区间有效期模型）"""
        self.exchange_rates = exchange_rate_service.get_active_rates(self.db)

    def _get_base_currency(self, company_code: str) -> str:
        """获取公司本位币"""
        return BASE_CURRENCY_CONFIG.get(company_code, 'CNY')

    def _get_exchange_rate(self, currency: str) -> float:
        """获取汇率（外币 → CNY）"""
        if currency == 'CNY':
            return 1.0
        rate = self.exchange_rates.get(currency)
        if rate is None:
            logger.warning(f"缺少货币 {currency} 的汇率配置")
            return 0.0
        return rate

    def _calc_cny_amount(self, row: dict) -> tuple:
        """
        计算CNY金额（参考 purchase analysis 的 calcPurchaseAmount 逻辑）

        核心公式：CNY金额 = 金额(订单货币) × 订单货币对CNY的汇率
        即：cny_amount = order_amount × exchange_rate(order_currency → CNY)

        特殊处理：
        - 订单货币 == 'CNY'：rate=1.0
        - 订单货币缺失且无金额(订单货币)：尝试用'采购金额'（假设已是CNY）兜底

        Returns: (cny_amount, exchange_rate_used)
        """
        order_currency_raw = row.get('订单货币', None)
        if pd.isna(order_currency_raw) or str(order_currency_raw).strip() == '':
            order_currency = 'CNY'
        else:
            order_currency = str(order_currency_raw).strip()

        order_amount = float(row.get('金额(订单货币)', 0) or 0)

        # 订单货币为CNY → 直接用金额(订单货币)即CNY金额
        if order_currency == 'CNY':
            return round(order_amount, 2), 1.0

        # 订单货币非CNY → 查汇率
        rate = self._get_exchange_rate(order_currency)
        if rate == 0:
            # 汇率缺失：兜底用采购金额（若记账本位币也是CNY则正确）
            base_currency = str(row.get('记账本位币', '')).strip()
            if base_currency == 'CNY':
                return round(float(row.get('采购金额', 0) or 0), 2), 0
            return 0, 0

        cny_amount = order_amount * rate
        return round(cny_amount, 2), rate

    def import_purchase_excel(self, file_path: str, data_source: str) -> dict:
        """
        导入采购台账Excel文件
        
        过滤规则（与 purchase analysis 一致）：
        - 排除供应商类别 === '关联方' 的行
        - 排除物料代码为空的行
        """
        df = pd.read_excel(file_path)

        stats = {
            "total": len(df),
            "success": 0,
            "failed": 0,
            "skipped_related": 0,  # 跳过的关联方记录
            "skipped_empty_material": 0,  # 跳过的空物料记录
            "missing_rates": [],  # 缺少汇率的货币列表
            "errors": []
        }

        # 预扫描货币集合（向量化，比逐行 iterrows 快数倍）
        currency_series = df.get('订单货币')
        if currency_series is not None:
            currency_series = currency_series.dropna().astype(str).str.strip()
            currencies_in_data = set(currency_series[(currency_series != 'CNY') & (currency_series != '')])
        else:
            currencies_in_data = set()

        missing_currencies = [c for c in currencies_in_data if c not in self.exchange_rates]
        stats["missing_rates"] = missing_currencies

        batch_records = []
        import_batch_id = datetime.now().strftime("%Y%m%d%H%M%S")

        # 转 dict 列表后遍历，比 df.iterrows 性能更高，且 row.get 访问方式保持兼容
        records = df.to_dict(orient='records')
        for index, row in enumerate(records):
            try:
                # 过滤关联方
                supplier_category = str(row.get('供应商类别', '')) if pd.notna(row.get('供应商类别')) else ''
                if supplier_category == '关联方':
                    stats["skipped_related"] += 1
                    continue

                # 过滤空物料代码
                raw_material_code = row.get('物料代码', '')
                if pd.isna(raw_material_code) or not str(raw_material_code).strip():
                    stats["skipped_empty_material"] += 1
                    continue
                # 处理浮点数问题：10005587.0 → 10005587
                material_code_val = raw_material_code
                if isinstance(material_code_val, float) and material_code_val == int(material_code_val):
                    material_code_val = int(material_code_val)
                material_code = str(material_code_val)

                # 计算CNY金额
                cny_amount, rate_used = self._calc_cny_amount(row)

                # 获取日期和月份信息
                transaction_date = pd.to_datetime(row.get('日期')).date() if pd.notna(row.get('日期')) else None
                fiscal_year = int(row.get('年度', 0)) if pd.notna(row.get('年度')) else None

                # 处理各字段的浮点数问题
                def clean_str_field(val, default=''):
                    """清洗字符串字段，处理浮点数NaN等问题"""
                    if pd.isna(val) or val is None:
                        return default
                    result = str(val)
                    if result == 'nan' or result.strip() == '':
                        return default
                    return result.strip()

                def clean_numeric_str(val):
                    """清洗数字型字符串字段（如物料代码、供应商编号、公司代码）"""
                    if pd.isna(val) or val is None:
                        return ''
                    if isinstance(val, float):
                        if val == int(val):
                            return str(int(val))
                    return str(val).strip()

                # 优先使用Excel中的"记账本位币"列，回退到公司代码配置
                excel_base_currency = clean_str_field(row.get('记账本位币', ''))
                if excel_base_currency:
                    base_currency = excel_base_currency
                else:
                    base_currency = self._get_base_currency(clean_numeric_str(row.get('公司', '')))

                # 构建采购记录对象
                record = PurchaseRecord(
                    company_code=clean_numeric_str(row.get('公司', '')),
                    company_name=clean_str_field(row.get('公司名称', '')),
                    fiscal_year=fiscal_year,
                    transaction_date=transaction_date,
                    supplier_code=clean_numeric_str(row.get('供应商编号', '')),
                    supplier_name=clean_str_field(row.get('供应商名称', '')),
                    supplier_category=clean_str_field(supplier_category),
                    material_code=material_code,
                    material_name=clean_str_field(row.get('物料名称', '')),
                    specification=clean_str_field(row.get('规格型号', '')),
                    material_category=clean_str_field(row.get('物料类别', '')),
                    base_currency=base_currency,
                    unit=clean_str_field(row.get('采购单位', '')),
                    quantity=float(row.get('采购数量', 0) or 0),
                    unit_price=float(row.get('采购单价', 0) or 0),
                    amount=float(row.get('采购金额', 0) or 0),
                    order_currency=clean_str_field(row.get('订单货币', ''), 'CNY'),
                    order_unit_price=float(row.get('单价(订单货币)', 0) or 0),
                    order_amount=float(row.get('金额(订单货币)', 0) or 0),
                    exchange_rate=rate_used,
                    cny_amount=cny_amount,
                    invoice_quantity=float(row.get('发票数量', 0) or 0),
                    invoice_unit_price=float(row.get('发票单价', 0) or 0),
                    invoice_amount=float(row.get('发票货值', 0) or 0),
                    invoice_tax=float(row.get('发票税额', 0) or 0),
                    invoice_total=float(row.get('发票总额', 0) or 0),
                    invoice_date=pd.to_datetime(row.get('发票过账日期')).date() if pd.notna(row.get('发票过账日期')) else None,
                    estimate_quantity=float(row.get('暂估数量', 0) or 0),
                    estimate_total=float(row.get('暂估总额', 0) or 0),
                    estimate_amount=float(row.get('暂估货值', 0) or 0),
                    purchase_purpose=clean_str_field(row.get('采购用途', '')),
                    po_number=clean_str_field(row.get('采购订单', '')),
                    material_doc=clean_str_field(row.get('物料凭证', '')),
                    line_item=clean_str_field(row.get('行项目', '')),
                    accounting_doc=clean_str_field(row.get('会计凭证号码', '')),
                    movement_type=clean_str_field(row.get('移动类型', '')),
                    movement_type_desc=clean_str_field(row.get('移动类型描述', '')),
                    reversal_flag=clean_str_field(row.get('冲销标识', '')),
                    line_item_category=clean_str_field(row.get('行项目类别', '')),
                    gr_based_invoice=clean_str_field(row.get('标识：基于收货的发票验证', '')),
                    line_item_text=clean_str_field(row.get('行项目文本', '')),
                    data_source=data_source,
                    import_batch_id=import_batch_id,
                    created_at=datetime.now()
                )

                batch_records.append(record)
                stats["success"] += 1

            except Exception as e:
                stats["failed"] += 1
                stats["errors"].append({
                    "row": index + 2,
                    "error": str(e)
                })

        # 批量插入（提升性能）—— 幂等：先按"物料凭证+行项目"去重
        if batch_records:
            # 收集所有业务键
            existing_keys = set()
            if batch_records:
                sample = batch_records[0]
                doc_field = 'material_doc'
                item_field = 'line_item'
                if doc_field and item_field:
                    material_docs = [getattr(r, doc_field) for r in batch_records if getattr(r, doc_field)]
                    line_items = [getattr(r, item_field) for r in batch_records if getattr(r, item_field)]
                    if material_docs:
                        existing = self.db.query(getattr(PurchaseRecord, doc_field), getattr(PurchaseRecord, item_field)).filter(
                            getattr(PurchaseRecord, doc_field).in_(material_docs)
                        ).all()
                        existing_keys = {(d, i) for d, i in existing}

            # 过滤掉已存在的
            new_records = []
            duplicate_count = 0
            for r in batch_records:
                key = (getattr(r, 'material_doc', None), getattr(r, 'line_item', None))
                if key[0] and key in existing_keys:
                    duplicate_count += 1
                else:
                    new_records.append(r)

            stats["duplicates_skipped"] = duplicate_count

            if new_records:
                # add_all：SQLAlchemy 2.0 推荐写法（bulk_save_objects 已不推荐）
                self.db.add_all(new_records)
            self.db.commit()

        # 自动创建供应商和物料主数据
        self._update_master_data(batch_records)

        return stats

    def _update_master_data(self, records: list):
        """从导入数据中自动更新供应商和物料主数据"""
        # 收集所有供应商和物料信息
        supplier_set = {}
        material_set = {}
        for record in records:
            if record.supplier_code and record.supplier_code != 'nan':
                supplier_set[record.supplier_code] = {
                    'name': record.supplier_name,
                    'category': record.supplier_category
                }
            if record.material_code and record.material_code != 'nan':
                material_set[record.material_code] = {
                    'name': record.material_name,
                    'category': record.material_category,
                    'specification': record.specification,
                    'unit': record.unit
                }

        # 更新供应商主数据
        for code, info in supplier_set.items():
            existing = self.db.query(Supplier).filter(Supplier.supplier_code == code).first()
            if not existing:
                supplier = Supplier(
                    supplier_code=code,
                    supplier_name=info['name'],
                    category=info.get('category', '')
                )
                self.db.add(supplier)

        # 更新物料主数据
        for code, info in material_set.items():
            existing = self.db.query(Material).filter(Material.material_code == code).first()
            if not existing:
                material = Material(
                    material_code=code,
                    material_name=info['name'],
                    category=info.get('category', ''),
                    specification=info.get('specification', ''),
                    unit=info.get('unit', '')
                )
                self.db.add(material)

        self.db.commit()