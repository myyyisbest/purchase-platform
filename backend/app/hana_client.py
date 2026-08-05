"""
HANA 数据库连接客户端
通过 hdbcli 连接 SAP HANA，读取采购台账视图数据
支持全量读取、按 RECORDMODE 过滤的增量读取、按日期范围读取
"""
import logging
import multiprocessing
import os
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from typing import List, Optional, Tuple

from dotenv import load_dotenv
from hdbcli import dbapi

load_dotenv()  # 加载 .env 环境变量

logger = logging.getLogger(__name__)

# HANA 连接配置（凭据必须通过环境变量注入；缺失则同步功能不可用，但不阻塞主服务启动）
HANA_HOST = os.getenv("HANA_HOST", "")
HANA_PORT = int(os.getenv("HANA_PORT", "0"))
HANA_USER = os.getenv("HANA_USER", "")
HANA_PASSWORD = os.getenv("HANA_PASSWORD", "")
# 视图名必须通过环境变量 HANA_VIEW_NAME 配置，无安全默认值
HANA_VIEW_NAME = os.getenv("HANA_VIEW_NAME", "")


def _check_hana_config() -> None:
    """HANA 凭据完整性校验：缺失任一关键项即抛错，避免用空串静默连接失败难定位"""
    missing = [k for k, v in {
        "HANA_HOST": HANA_HOST, "HANA_USER": HANA_USER, "HANA_PASSWORD": HANA_PASSWORD,
    }.items() if not v]
    if missing:
        raise RuntimeError(f"HANA 连接配置缺失：{missing}，请在 .env 中补齐后重试同步")


def get_connection():
    """创建 HANA 数据库连接（连接前校验凭据完整性）"""
    _check_hana_config()
    return dbapi.connect(
        address=HANA_HOST,
        port=HANA_PORT,
        user=HANA_USER,
        password=HANA_PASSWORD,
    )


@contextmanager
def hana_cursor():
    """HANA 连接上下文管理器，自动关闭游标和连接"""
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        yield cursor
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def _rows_to_dicts(cursor) -> List[dict]:
    """将游标结果转为字典列表"""
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


# ── HANA 视图列：运行时动态获取全部字段，与 `SELECT *` 完全一致 ──
# 设计原因：曾用写死的字段清单，导致漏取订单数量 MENGE 等 18 个字段，
#           进而使金额计算错误。改为动态获取，视图加列自动生效，绝不裁剪。
_VIEW_COLUMNS_CACHE: Optional[List[str]] = None


def get_view_columns(refresh: bool = False) -> List[str]:
    """动态获取 HANA 视图全部字段名（保持视图原序，大写）。

    首次查询后缓存；refresh=True 强制重新拉取。
    与 `SELECT * FROM 视图` 的字段、顺序完全一致，不做任何裁剪。
    """
    global _VIEW_COLUMNS_CACHE
    if _VIEW_COLUMNS_CACHE and not refresh:
        return _VIEW_COLUMNS_CACHE
    with hana_cursor() as cursor:
        cursor.execute(f'SELECT * FROM {HANA_VIEW_NAME} LIMIT 1')
        cols = [d[0] for d in cursor.description]
    _VIEW_COLUMNS_CACHE = cols
    logger.info(f"HANA 视图共 {len(cols)} 列: {cols}")
    return cols


def _columns_sql() -> str:
    """构造 SELECT 字段片段（带双引号），覆盖视图全部字段。"""
    return ", ".join(f'"{c}"' for c in get_view_columns())


def fetch_view_data(batch_size: int = 5000, offset: int = 0) -> list[dict]:
    """
    分页读取 HANA 视图全量数据（仅拉取映射需要的列）

    Args:
        batch_size: 每批读取行数
        offset: 起始偏移量

    Returns:
        字典列表，每行一个 dict，key 为大写 HANA 字段名
    """
    sql = f'SELECT {_columns_sql()} FROM {HANA_VIEW_NAME} LIMIT {batch_size} OFFSET {offset}'
    logger.info(f"执行 HANA 全量查询: LIMIT {batch_size} OFFSET {offset}")
    with hana_cursor() as cursor:
        cursor.execute(sql)
        result = _rows_to_dicts(cursor)
        logger.info(f"HANA 返回 {len(result)} 行（offset={offset}）")
        return result


def fetch_all_data(batch_size: int = 5000) -> list[dict]:
    """
    分批读取 HANA 视图全量数据，避免内存溢出
    """
    all_rows = []
    offset = 0
    while True:
        batch = fetch_view_data(batch_size=batch_size, offset=offset)
        if not batch:
            break
        all_rows.extend(batch)
        offset += batch_size
    logger.info(f"HANA 全量读取完成，共 {len(all_rows)} 行")
    return all_rows


def fetch_incremental_data(
    batch_size: int = 5000,
    offset: int = 0,
) -> list[dict]:
    """
    分页读取增量数据（RECORDMODE IN ('N','U','D')）
    """
    sql = (
        f'SELECT {_columns_sql()} FROM {HANA_VIEW_NAME} '
        f"WHERE \"RECORDMODE\" IN ('N','U','D') "
        f"ORDER BY \"BUDAT\" "
        f"LIMIT {batch_size} OFFSET {offset}"
    )
    logger.info(f"执行 HANA 增量查询: LIMIT {batch_size} OFFSET {offset}")
    with hana_cursor() as cursor:
        cursor.execute(sql)
        result = _rows_to_dicts(cursor)
        logger.info(f"HANA 增量返回 {len(result)} 行（offset={offset}）")
        return result


def fetch_all_incremental_data(batch_size: int = 5000) -> list[dict]:
    """
    分批读取全部增量数据（所有 RECORDMODE IN ('N','U','D') 的行）
    """
    all_rows = []
    offset = 0
    while True:
        batch = fetch_incremental_data(batch_size=batch_size, offset=offset)
        if not batch:
            break
        all_rows.extend(batch)
        offset += batch_size
    logger.info(f"HANA 增量读取完成，共 {len(all_rows)} 行")
    return all_rows


def fetch_data_by_date_range(
    start_date: str,
    end_date: str,
    batch_size: int = 5000,
) -> list[dict]:
    """
    按 BUDAT（过账日期）范围分批读取 HANA 视图数据。
    用于每日定时同步当月+上月数据，不触及更早的旧单据。

    HANA 视图中 BUDAT 可能是 VARCHAR(8) 也可能是 DATE 类型，
    为保证两边兼容，统一用 TO_DATE(:start, 'YYYYMMDD') 显式转换比较，
    避免 HANA 隐式类型转换在不同视图定义下行为不一致。

    Args:
        start_date: 起始日期，格式 YYYYMMDD，如 '20260601'
        end_date:   结束日期，格式 YYYYMMDD，如 '20260701'
        batch_size: 每批读取行数

    Returns:
        字典列表，BUDAT 在 [start_date, end_date] 范围内的所有行
    """
    # 使用参数绑定 + TO_DATE 转换，比字符串字面量比较更稳健
    sql = (
        f'SELECT {_columns_sql()} FROM {HANA_VIEW_NAME} '
        f"WHERE \"BUDAT\" >= TO_DATE(?, 'YYYYMMDD') "
        f"  AND \"BUDAT\" <= TO_DATE(?, 'YYYYMMDD') "
        f"ORDER BY \"BUDAT\" "
        f"LIMIT {batch_size} OFFSET {{}}"
    )
    logger.info(f"按日期范围查询 HANA: {start_date} ~ {end_date}")
    all_rows = []
    offset = 0
    with hana_cursor() as cursor:
        while True:
            # hdbcli 的 execute 支持 positional bind variables
            cursor.execute(sql.format(offset), (start_date, end_date))
            batch = _rows_to_dicts(cursor)
            if not batch:
                break
            all_rows.extend(batch)
            offset += batch_size
    logger.info(f"日期范围查询完成，共 {len(all_rows)} 行（{start_date}~{end_date}）")
    return all_rows


def _to_yyyymmdd(value) -> str:
    """将 HANA 返回的 BUDAT 转为 YYYYMMDD 字符串"""
    if value is None:
        return "19000101"
    if isinstance(value, (date, datetime)):
        return value.strftime("%Y%m%d")
    s = str(value).strip()
    if len(s) == 8 and s.isdigit():
        return s
    # 尝试解析 ISO 日期
    try:
        return datetime.fromisoformat(s[:10]).strftime("%Y%m%d")
    except (ValueError, TypeError):
        return "19000101"


def get_min_max_budat() -> Tuple[str, str]:
    """查询 HANA 视图中最小和最大 BUDAT"""
    sql = f'SELECT MIN("BUDAT"), MAX("BUDAT") FROM {HANA_VIEW_NAME}'
    with hana_cursor() as cursor:
        cursor.execute(sql)
        row = cursor.fetchone()
        if row and row[0] is not None and row[1] is not None:
            return _to_yyyymmdd(row[0]), _to_yyyymmdd(row[1])
        return "19000101", "20991231"


def _fetch_date_range_worker(args: Tuple[str, str]) -> list[dict]:
    """多进程 worker：读取指定 BUDAT 范围的 HANA 数据"""
    start_date, end_date = args
    return fetch_data_by_date_range(start_date, end_date, batch_size=5000)


def split_date_range(start_date: str, end_date: str, chunks: int) -> List[Tuple[str, str]]:
    """将 [start_date, end_date] 均分为 chunks 个子区间"""
    start = datetime.strptime(start_date, "%Y%m%d").date()
    end = datetime.strptime(end_date, "%Y%m%d").date()
    if chunks <= 1 or start >= end:
        return [(start_date, end_date)]

    total_days = (end - start).days + 1
    step = max(1, total_days // chunks)
    ranges = []
    current = start
    for i in range(chunks):
        if i == chunks - 1:
            next_end = end
        else:
            next_end = min(current + timedelta(days=step - 1), end)
        ranges.append((current.strftime("%Y%m%d"), next_end.strftime("%Y%m%d")))
        if next_end >= end:
            break
        current = next_end + timedelta(days=1)
    return ranges


def fetch_all_data_parallel(workers: int = 5) -> list[dict]:
    """
    多进程按 BUDAT 范围并行读取 HANA 全量数据。
    每个 worker 独立连接 HANA，读取自己的日期分片，总耗时显著低于单线程 LIMIT/OFFSET。

    Args:
        workers: 并行 worker 数，默认 5（HANA/DB 负载安全区间）

    Returns:
        字典列表，所有 HANA 行
    """
    min_date, max_date = get_min_max_budat()
    logger.info(f"HANA 数据 BUDAT 范围: {min_date} ~ {max_date}，启动 {workers} 个 worker 并行读取")

    ranges = split_date_range(min_date, max_date, workers)
    logger.info(f"日期分片: {ranges}")

    with multiprocessing.Pool(processes=min(workers, len(ranges))) as pool:
        results = pool.map(_fetch_date_range_worker, ranges)

    all_rows = []
    for rows in results:
        all_rows.extend(rows)
    logger.info(f"HANA 并行读取完成，共 {len(all_rows)} 行")
    return all_rows
