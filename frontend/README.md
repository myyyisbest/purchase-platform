# 采购分析平台 - 前端

Vue 3 + Vite + Element Plus 构建的采购分析前端应用。

## 技术栈

- **框架**: Vue 3 + TypeScript
- **UI 组件**: Element Plus
- **图表**: ECharts
- **构建工具**: Vite

## 端口

| 服务 | 端口 |
|------|------|
| 前端开发服务器 | **3001** |
| 后端 API | **8081** |

## 开发启动

```bash
cd frontend
npm install
npm run dev
```

访问：`http://localhost:3001`

## 后端代理

开发模式下 Vite 自动将 `/api` 请求转发到 `http://127.0.0.1:8081`（配置在 `vite.config.js`）。

## 构建部署

```bash
npm run build
```

产物输出到 `dist/` 目录。

## 相关文档

- [Vite 文档](https://vitejs.dev/)
- [Vue 3 文档](https://vuejs.org/)
- [Element Plus 文档](https://element-plus.org/)
