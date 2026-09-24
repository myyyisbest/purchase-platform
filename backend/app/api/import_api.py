"""
数据导入API路由

鉴权策略：admin only（导入会改动核心业务数据）
"""
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import os
import shutil
from datetime import datetime
from pathlib import Path

from ..database import get_db
from ..auth import require_admin, get_current_user
from ..models import User
from ..services.import_service import ImportService

router = APIRouter()

# 仓库根目录下的 data_templates（backend/app/api -> ../../../data_templates）
_TEMPLATES_DIR = Path(__file__).resolve().parents[3] / "data_templates"
_PURCHASE_TEMPLATE = "06_采购记录表_核心.csv"


@router.get("/template")
def download_purchase_template(_: User = Depends(get_current_user)):
    """下载采购记录导入模板（CSV，列名与导入服务一致）"""
    path = _TEMPLATES_DIR / _PURCHASE_TEMPLATE
    if not path.is_file():
        raise HTTPException(status_code=404, detail="导入模板文件不存在")
    return FileResponse(
        path=str(path),
        media_type="text/csv",
        filename=_PURCHASE_TEMPLATE,
    )


@router.post("/upload")
async def upload_and_import(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """
    上传 Excel/CSV 文件并导入采购数据

    Args:
        file: 上传的 .xlsx / .xls / .csv 文件
        db: 数据库会话

    Returns:
        导入结果统计
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="未提供文件名")

    filename_lower = file.filename.lower()
    if not filename_lower.endswith(('.xlsx', '.xls', '.csv')):
        raise HTTPException(status_code=400, detail="只支持 Excel(.xlsx/.xls) 或 CSV(.csv) 文件")

    temp_dir = "/tmp/purchase_import"
    os.makedirs(temp_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_filename = f"{timestamp}_{file.filename}"
    temp_file_path = os.path.join(temp_dir, temp_filename)

    try:
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        import_service = ImportService(db)
        stats = import_service.import_purchase_excel(temp_file_path, file.filename)

        return {
            "code": 200,
            "message": "导入完成",
            "data": stats
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")

    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
