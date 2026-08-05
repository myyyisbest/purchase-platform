"""
AI 助手 API - 代理大语言模型服务（兼容 OpenAI 接口格式）

鉴权策略：所有登录用户可访问（消耗 MaaS 额度，但不改业务数据）
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List, Optional
import requests
import os

from ..auth import get_current_user
from ..models import User

router = APIRouter()

# 大模型 API 配置（密钥必须通过环境变量注入，不内嵌默认值）
MAAS_BASE_URL = os.getenv("MAAS_BASE_URL", "")
MAAS_API_KEY = os.getenv("MAAS_API_KEY")
if not MAAS_API_KEY:
    raise RuntimeError("MAAS_API_KEY 未配置，请在 .env 中设置后重启")
MAAS_MODEL = os.getenv("MAAS_MODEL", "glm-5.2")


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    stream: bool = False


class ChatResponse(BaseModel):
    code: int = 200
    message: str = "成功"
    data: Optional[dict] = None


@router.post("/chat")
def chat(
    req: ChatRequest,
    current_user: User = Depends(get_current_user),
):
    """调用 GLM 大模型聊天"""
    try:
        resp = requests.post(
            f"{MAAS_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {MAAS_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": MAAS_MODEL,
                "messages": [m.dict() for m in req.messages],
                "stream": False
            },
            timeout=120
        )
        resp.raise_for_status()
        return {
            "code": 200,
            "message": "成功",
            "data": resp.json()
        }
    except requests.exceptions.Timeout:
        return {"code": 500, "message": "模型响应超时", "data": None}
    except requests.exceptions.RequestException as e:
        return {"code": 500, "message": f"模型调用失败: {str(e)}", "data": None}


@router.get("/test")
def test_connection(_: User = Depends(get_current_user)):
    """测试模型连通性"""
    try:
        resp = requests.post(
            f"{MAAS_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {MAAS_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": MAAS_MODEL,
                "messages": [
                    {"role": "user", "content": "你好，请简单回复'连接成功'"}
                ],
                "stream": False
            },
            timeout=30
        )
        resp.raise_for_status()
        data = resp.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return {
            "code": 200,
            "message": "模型连接测试成功",
            "data": {
                "model": MAAS_MODEL,
                "reply": content,
                "usage": data.get("usage", {})
            }
        }
    except requests.exceptions.Timeout:
        return {"code": 500, "message": "连接超时，模型不可达", "data": None}
    except requests.exceptions.RequestException as e:
        return {"code": 500, "message": f"连接失败: {str(e)}", "data": None}
