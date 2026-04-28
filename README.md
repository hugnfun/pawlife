# PawLife

AI Native 宠物健康管理平台 —「真正懂你宠物的 AI 健康伙伴」

PawLife 是一款基于微信小程序的宠物健康管理应用，核心理念是 **AI 作为唯一交互层**，用户通过自然语言对话完成所有健康管理操作，无需学习复杂的 UI 操作逻辑。

## 技术栈

### 前端
- **跨端框架**：uni-app 3.x (Vue.js 3)
- **状态管理**：Pinia 2.x
- **数据图表**：uCharts 2.x
- **构建工具**：Vite

### 后端
- **Web 框架**：FastAPI 0.110+
- **Agent 编排**：LangGraph 0.1+
- **异步任务**：Celery 5.x
- **ORM**：SQLAlchemy 2.x (async)
- **数据库迁移**：Alembic 1.x

### 数据存储
- **主数据库**：PostgreSQL 16+ (pgvector 扩展)
- **缓存/队列**：Redis 7.x
- **文件存储**：腾讯云 COS

### AI 能力
- **核心 LLM**：Claude 3.5 Sonnet / GPT-4o
- **图像识别**：GPT-4o Vision
- **语音转文字**：腾讯云 ASR
- **向量化**：text-embedding-3-small

### 基础设施
- **云服务**：腾讯云 (CVM / TKE / COS / CDN / CLS)
- **CI/CD**：GitHub Actions + TKE 部署

## 架构概览

```
微信小程序 (uni-app)
  ↕ HTTPS / SSE
AI Agent 编排层 (LangGraph)
  ├── 意图识别 → 上下文注入 → 工具调用 → 结果整合 → 流式回复
  ├── 记忆管理器 (三级记忆)
  ├── 情境感知器 (健康趋势)
  └── 主动推送调度器 (晨报/预警)
  ↕
工具集合 + 数据存储层 (PostgreSQL / pgvector / Redis / COS)
```

## 快速开始

### 环境要求
- Python 3.11+
- Node.js 22+
- Docker & Docker Compose

### 本地开发

```bash
# 启动依赖服务
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d postgres redis

# 安装后端依赖
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 运行数据库迁移
alembic -c alembic.ini upgrade head

# 启动后端服务
uvicorn main:app --reload --port 8000

# 安装前端依赖
cd ../frontend
npm install

# 启动前端开发服务器
npm run dev
```

### Docker 完整部署

```bash
docker compose up -d
```

## 项目结构

```
pawlife/
├── backend/                # FastAPI 后端
│   ├── alembic/           # 数据库迁移
│   ├── core/              # 核心配置与依赖注入
│   ├── middleware/        # 中间件
│   ├── models/            # SQLAlchemy 数据模型
│   ├── routers/           # API 路由
│   ├── schemas/           # Pydantic 请求/响应模型
│   ├── scripts/           # 工具脚本
│   ├── services/          # 业务服务层
│   │   └── agent/         # LangGraph Agent 编排
│   └── tests/             # 测试
├── frontend/              # uni-app 前端
│   ├── pages/             # 页面组件
│   ├── src/               # 核心源码
│   └── tests/             # 测试
├── docker-compose.yml     # 生产环境编排
├── docker-compose.dev.yml # 开发环境覆盖
├── nginx.conf             # Nginx 反向代理配置
└── Dockerfile             # 应用镜像
```

## 核心工具集

| 工具 | 功能 | 依赖 |
|-----|------|------|
| `get_pet_profile` | 读取宠物档案 | PostgreSQL |
| `log_meal` | 记录饮食 (含重复喂食检测) | PostgreSQL + Redis |
| `calculate_nutrition` | 计算食物营养成分 | 营养数据库 |
| `recognize_food_image` | 识别照片中的食物 | GPT-4o Vision |
| `generate_recipe` | 生成个性化食谱 | 规则引擎 + LLM |
| `search_nearby_hospital` | 查询附近宠物医院 | 地图 API |

## 开发约定

- **Python**：PEP 8，Black 格式化，Type Hints 必须，async/await 异步模式
- **Vue**：Composition API + `<script setup>`，TypeScript 核心逻辑
- **Git**：Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:` 等)
- **分支**：`main` (生产) / `develop` (开发) / `feature/*` / `release/*` / `hotfix/*`

## 许可证

Copyright © 2026 PawLife. All rights reserved.
