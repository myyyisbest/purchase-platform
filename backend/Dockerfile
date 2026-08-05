# 采购分析平台后端 Dockerfile
# 基于 Python 3.11 slim，兼容 CloudBase CloudRun 容器模式
FROM python:3.11-slim

WORKDIR /app

# 使用阿里云 PyPI 镜像加速安装（可按需替换为其他镜像源）
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/

# 安装系统编译依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 监听 CloudRun 注入的 PORT 环境变量
EXPOSE 8000

# 启动：绑定 0.0.0.0:PORT
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
