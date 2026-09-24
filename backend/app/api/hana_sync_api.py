"""
HANA 数据同步 API
- POST /sync            全量/增量/月度同步（mode=full|incremental|monthly）
- POST /sync/monthly    月度定时同步（当日+上月，可覆盖更新）
- GET  /status          连接配置信息
- GET  /state           最近一次同步状态

鉴权策略：JWT admin 或 X-Cron-Token / Bearer Cron Token（CRON_API_TOKEN）
"""
import logging
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..auth import require_admin, require_admin_or_cron
from ..models import User
from ..services.hana_sync_service import HanaSyncService
from ..hana_client import HANA_HOST, HANA_PORT, HANA_USER, HANA_VIEW_NAME

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/sync")
def trigger_hana_sync(
    mode: str = Query("full", pattern="^(full|incremental|monthly)$"),
    db: Session = Depends(get_db),
    _ = Depends(require_admin_or_cron),
):
    """
    触发 HANA 数据同步
    - mode=full         全量同步（拉取全部 HANA 数据，diff 后写入）
    - mode=incremental  增量同步（仅拉取 RECORDMODE IN ('N','U','D') 的行）
    - mode=monthly      月度定时同步（当月+上月数据，可覆盖更新）
    """
    logger.info(f"收到 HANA {mode} 同步请求")
    try:
        svc = HanaSyncService(db)
        if mode == "incremental":
            stats = svc.sync_incremental()
        elif mode == "monthly":
            stats = svc.sync_by_date_range()
        else:
            stats = svc.sync_full()

        logger.info(f"HANA {mode} 同步完成: 新增{stats['inserted']}, 更新{stats['updated']}")
        return {
            "code": 200,
            "message": f"HANA {mode} 同步完成",
            "data": stats,
        }
    except Exception as e:
        logger.error(f"HANA 同步失败: {e}", exc_info=True)
        return {
            "code": 500,
            "message": f"HANA 同步失败: {str(e)}",
            "data": None,
        }


@router.post("/sync/monthly")
def trigger_monthly_sync(
    db: Session = Depends(get_db),
    _ = Depends(require_admin_or_cron),
):
    """
    月度定时同步（供 cron 每日凌晨 2 点调用）。
    同步当月+上月数据，可覆盖更新已有记录，不触及更早日期的明细。
    """
    logger.info("收到月度定时同步请求")
    try:
        svc = HanaSyncService(db)
        stats = svc.sync_by_date_range()
        logger.info(f"月度定时同步完成: 新增{stats['inserted']}, 更新{stats['updated']}")
        return {
            "code": 200,
            "message": "月度定时同步完成",
            "data": stats,
        }
    except Exception as e:
        logger.error(f"月度定时同步失败: {e}", exc_info=True)
        return {
            "code": 500,
            "message": f"月度定时同步失败: {str(e)}",
            "data": None,
        }


@router.get("/status")
def hana_sync_status(_ = Depends(require_admin_or_cron)):
    """查看 HANA 连接配置信息（不含密码）"""
    return {
        "code": 200,
        "message": "ok",
        "data": {
            "hana_host": HANA_HOST,
            "hana_port": HANA_PORT,
            "hana_user": HANA_USER,
            "hana_view": HANA_VIEW_NAME,
        },
    }


@router.get("/state")
def hana_sync_last_state(
    db: Session = Depends(get_db),
    _ = Depends(require_admin_or_cron),
):
    """查看最近一次 HANA 同步状态"""
    state = HanaSyncService.get_last_sync_state(db)
    record_count = HanaSyncService.get_record_count(db)
    return {
        "code": 200,
        "message": "ok",
        "data": {
            "last_sync": state,
            "local_record_count": record_count,
        },
    }
