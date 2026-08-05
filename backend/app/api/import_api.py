"""
数据导入API路由

鉴权策略：admin only（导入会改动核心业务数据）
"""
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
import os
import shutil
from datetime import datetime

from ..database import get_db
from ..auth import require_admin
from ..models import User
from ..services.import_service import ImportService

router = APIRouter()


@router.post("/upload")
async def upload_and_import(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """
    上传Excel文件并导入数据

    Args:
        file: 上传的Excel文件
        db: 数据库会话

    Returns:
        导入结果统计
    """
    # 检查文件类型（大小写不敏感）
    filename_lower = file.filename.lower()
    if not filename_lower.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="只支持Excel文件(.xlsx, .xls)")

    # 创建临时文件目录
    temp_dir = "/tmp/purchase_import"
    os.makedirs(temp_dir, exist_ok=True)

    # 生成临时文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_filename = f"{timestamp}_{file.filename}"
    temp_file_path = os.path.join(temp_dir, temp_filename)

    try:
        # 保存上传的文件
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 导入数据
        import_service = ImportService(db)
        stats = import_service.import_purchase_excel(temp_file_path, file.filename)

        # 返回统计结果
        return {
            "code": 200,
            "message": "导入完成",
            "data": stats
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")

    finally:
        # 清理临时文件
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
