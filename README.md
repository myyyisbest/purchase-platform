# 采购数据分析平台

> 基于 FastAPI + Vue 3 的企业采购数据分析与可视化平台，支持采购同期对比、供应商分析、物料单价趋势、AI 智能助手等功能。

---

## 目录

- [简介](#简介)
- [功能特性](#功能特性)
- [技术栈](#技术栈)
- [安装](#安装)
- [配置](#配置)
- [使用](#使用)
- [部署](#部署)
- [FAQ](#faq)
- [许可证](#许可证)

---

## 简介

采购数据分析平台是一个面向企业采购业务的全栈数据分析系统，涵盖采购同期对比（YoY）、供应商画像、物料单价趋势分析、汇率换算、AI 问答助手等核心模块。后端基于 FastAPI 构建 RESTful API，前端使用 Vue 3 + ECharts 呈现可视化看板。

平台支持从 SAP HANA 数据库同步采购明细，也支持通过 CSV 模板批量导入数据，适配多种数据来源场景。

---

## 功能特性

| 模块 | 说明 |
|---|---|
| 采购同期对比（YoY） | 按年度/季度/月份对比采购金额、数量，自动计算同比增幅 |
| 采购分析面板 | 汇总采购总额、TOP 供应商、TOP 物料、趋势走势 |
| 供应商分析 | 供应商采购额排名、集中度分析、交易明细追溯 |
| 物料单价趋势 | 物料历史单价走势、价格波动预警 |
| 组织架构管理 | 公司/事业部层级管理，基于角色的数据权限控制 |
| 汇率管理 | 多币种汇率维护，支持采购金额本币换算 |
| AI 智能助手 | 自然语言查询采购数据，自动生成分析结论 |
| 数据导入 | 支持 CSV 批量导入，提供标准化数据模板 |
| HANA 数据同步 | 支持从 SAP HANA 视图自动拉取采购明细（可选） |
| 用户与权限 | JWT 认证、角色管理（admin/user）、公司级数据隔离 |

---

## 技术栈

**后端**
- Python 3.11+
- FastAPI（异步 Web 框架）
- SQLAlchemy ORM + PostgreSQL
- PyJWT + bcrypt（认证与密码哈希）
- hdbcli（SAP HANA 客户端，可选）
- Uvicorn / Gunicorn（ASGI 服务器）

**前端**
- Vue 3 + Composition API
- Vite（构建工具）
- Element Plus（UI 组件库）
- ECharts（数据可视化）
- Axios（HTTP 客户端）
- Pinia（状态管理）

**基础设施**
- PostgreSQL 15+
- Docker / Docker Compose（容器化部署）
- Nginx（反向代理，可选）

---

## 安装

### 前置条件

- Python 3.11+
- Node.js 18+
- PostgreSQL 15+
- Docker 24+（可选，用于容器化部署）

### 1. 克隆仓库

```bash
git clone <your-repo-url>
cd purchase_platform
```

### 2. 后端安装

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. 前端安装

```bash
cd frontend
npm install
```

### 4. 数据库准备

确保 PostgreSQL 已启动，创建数据库和用户：

```bash
# 连接 PostgreSQL
sudo -u postgres psql

# 创建数据库和用户（请替换为你的实际密码）
CREATE DATABASE purchase_platform;
CREATE USER pp_user WITH PASSWORD '<your-db-password>';
GRANT ALL PRIVILEGES ON DATABASE purchase_platform TO pp_user;
\q
```

---

## 配置

### 后端环境变量

复制示例配置文件并填写实际值：

```bash
cp backend/.env.example backend/.env
```

编辑 `backend/.env`，配置以下变量：

```ini
# ========== 数据库 ==========
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=purchase_platform
DB_USER=pp_user
DB_PASSWORD=<your-db-password>

# ========== JWT 认证 ==========
# 必须设置随机长字符串（至少16位），否则后端启动失败
JWT_SECRET=<your-random-secret-at-least-16-chars>
JWT_EXPIRE_MINUTES=1440

# ========== 初始账户密码 ==========
# 首次启动时自动创建 admin 账户，建议首次登录后立即修改
DEFAULT_ADMIN_PASSWORD=<your-admin-password>
DEFAULT_USER_PASSWORD=<your-user-password>

# ========== CORS ==========
# 允许的前端来源（逗号分隔）
CORS_ALLOW_ORIGINS=http://localhost:3001,http://localhost:3000

# ========== SAP HANA（可选） ==========
# 仅在使用 HANA 数据同步功能时需要配置
HANA_HOST=<your-hana-host>
HANA_PORT=<your-hana-port>
HANA_USER=<your-hana-user>
HANA_PASSWORD=<your-hana-password>
# HANA 采购明细视图的完整路径名，请替换为你的实际视图
HANA_VIEW=<your-hana-view-path>

# ========== AI 助手（可选） ==========
# 大模型 API 配置（支持兼容 OpenAI 接口的服务）
MAAS_API_KEY=<your-ai-api-key>
MAAS_BASE_URL=<your-ai-base-url>
MAAS_MODEL=<your-ai-model-name>

# ========== 日志目录 ==========
LOG_DIR=./logs
```

> **安全提示**：切勿将包含真实密钥的 `.env` 文件提交到版本库。`.env` 已被 `.gitignore` 忽略。

### 前端配置

前端默认连接 `http://127.0.0.1:8000` 后端 API。如需修改，编辑 `frontend/src/api/http.js` 中的 `baseURL`，或通过环境变量 `VITE_API_BASE_URL` 配置。

---

## 使用

### 1. 初始化数据库

首次运行时，后端会自动创建数据表并初始化 admin 账户。如需预置示例数据，可执行 SQL 脚本：

```bash
psql -U pp_user -d purchase_platform -f init_db.sql
```

`init_db.sql` 包含表结构定义和示例公司、示例用户数据，可根据实际业务修改。

### 2. 启动后端

```bash
cd backend
source venv/bin/activate
python -m app.main
# 或使用 uvicorn（开发模式，支持热重载）
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

后端启动后访问 API 文档：`http://localhost:8000/docs`

### 3. 启动前端

```bash
cd frontend
npm run dev
```

前端开发服务器默认运行在 `http://localhost:3001`

### 4. 登录系统

使用 `.env` 中配置的 `DEFAULT_ADMIN_PASSWORD` 对应的密码登录 admin 账户。

### 5. 数据导入

进入「数据导入」页面，下载 `data_templates/` 中的 CSV 模板，填写数据后上传。支持以下数据表：

| 模板 | 说明 |
|---|---|
| 01_组织架构_公司表 | 公司/事业部基础信息 |
| 02_供应商主数据 | 供应商名称、编码、国家 |
| 03_物料主数据 | 物料编码、名称、单位 |
| 04_汇率表 | 多币种汇率 |
| 05_物料大类维护表 | 物料分类映射 |
| 06_采购记录表_核心 | 采购明细（核心数据） |

### 6. HANA 数据同步（可选）

若已配置 SAP HANA 连接信息，可在后台执行同步脚本将采购明细拉取到本地数据库。配置方法见上方「SAP HANA」章节。

---

## 部署

### Docker Compose 部署

项目提供 `docker-compose.yml`，一键启动后端 + 数据库：

```bash
docker-compose up -d
```

### 生产环境部署

**后端（Gunicorn + Uvicorn Worker）**

```bash
cd backend
source venv/bin/activate
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
```

**前端构建**

```bash
cd frontend
npm run build
# 构建产物在 dist/ 目录，部署到 Nginx 静态目录
```

**Nginx 反向代理示例**

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # 前端静态资源
    location / {
        root /path/to/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # 后端 API
    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        client_max_body_size 50m;
    }
}
```

---

## FAQ

**Q: 启动报错 `JWT_SECRET 未配置` 怎么办？**

A: 在 `backend/.env` 中设置 `JWT_SECRET` 为一段随机长字符串（至少 16 位），例如：`JWT_SECRET=my-super-secret-key-2024`。可用 `python -c "import secrets; print(secrets.token_urlsafe(32))"` 生成。

**Q: 忘记 admin 密码怎么办？**

A: 连接数据库，将 admin 用户的密码重置为新密码的 bcrypt 哈希值；或删除 admin 用户记录后重启服务，系统会根据 `.env` 中的 `DEFAULT_ADMIN_PASSWORD` 重新创建。

**Q: HANA 数据同步失败？**

A: 检查 `.env` 中的 HANA 连接参数是否正确，确认网络可达、视图名无误、用户有查询权限。可在后端日志中查看详细错误信息。

**Q: 前端构建后页面白屏？**

A: 若部署在子路径下，需在 `frontend/vite.config.js` 中配置 `base: '/your-subpath/'`，并在 Nginx 中正确配置 `try_files` 回退。

**Q: 如何切换 AI 大模型服务？**

A: 在 `.env` 中修改 `MAAS_API_KEY`、`MAAS_BASE_URL`、`MAAS_MODEL` 为目标服务的配置。平台兼容 OpenAI API 格式。

**Q: 支持哪些数据库？**

A: 当前基于 PostgreSQL 开发与测试。SQLAlchemy ORM 理论上支持切换到其他数据库，但需自行适配 SQL 方言差异。

---

## 许可证

本项目基于 [MIT License](LICENSE) 开源。

```
MIT License

Copyright (c) 2024 Purchase Platform Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
