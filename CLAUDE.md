# CLAUDE.md - PawLife 项目指南

## 项目概述

PawLife 是一个 AI Native 宠物健康管理小程序，定位为「真正懂你宠物的 AI 健康伙伴」。产品核心理念是 AI 作为唯一交互层，所有传统功能模块均作为 AI 的工具集存在。用户无需学习操作逻辑，只需通过自然语言对话即可完成所有健康管理行为。

**目标平台**：微信小程序 / uni-app

## 技术栈

### 前端技术栈
- **跨端框架**：uni-app 3.x (基于 Vue.js 3)
- **前端框架**：Vue 3.4+ (Composition API，TypeScript 支持好)
- **状态管理**：Pinia 2.x (比 Vuex 更轻量，天然支持 TypeScript)
- **数据图表**：uCharts 2.x (小程序兼容最好，体重/营养趋势展示)
- **流式输出**：SSE Client (原生实现，实时展示 AI 打字效果)
- **构建工具**：Vite / Webpack (uni-app 内置)
- **样式预处理器**：SCSS

### 后端技术栈
- **主语言**：Python 3.11+ (AI/ML 生态最完整)
- **Web 框架**：FastAPI 0.110+ (异步支持好，自动生成 API 文档)
- **Agent 编排**：LangGraph 0.1+ (有状态图，支持复杂推理流程)
- **异步任务**：Celery 5.x (定时任务、批量推送、后台分析)
- **主数据库**：PostgreSQL 16+ (成熟稳定，支持 pgvector 扩展)
- **向量存储**：pgvector 0.7+ (长期记忆语义检索)
- **缓存/队列**：Redis 7.x (会话上下文、Celery Broker)
- **ORM**：SQLAlchemy 2.x (异步支持，类型安全)
- **数据库迁移**：Alembic 1.x (版本化管理 Schema 变更)

### AI 能力栈
- **核心 LLM**：Claude 3.5 Sonnet (首选) / GPT-4o (备选) - 长上下文，工具调用稳定
- **食物图像识别**：GPT-4o Vision (首选) / 腾讯云食物识别 (备选) - 通用视觉理解能力更强
- **语音转文字**：腾讯云 ASR (首选) / Whisper API (备选) - 中文识别率高，延迟低
- **文本向量化**：text-embedding-3-small (首选) / 腾讯云向量化 (备选) - 性价比最优
- **向量检索**：pgvector + cosine (集成在 PostgreSQL，降低运维复杂度)
- **联网搜索**：Bing Search API (首选) / Perplexity API (备选) - 电商/内容平台口碑搜索

### 基础设施 (腾讯云全家桶)
- **云服务器**：CVM (CentOS 8+)
- **容器服务**：TKE (Kubernetes 集群)
- **对象存储**：COS (图片、音频文件存储)
- **CDN**：腾讯云 CDN (静态资源加速)
- **监控告警**：Cloud Monitor + 自定义指标
- **日志服务**：CLS (集中日志收集与分析)

### 开发与运维工具
- **代码仓库**：Git (GitHub/GitLab)
- **CI/CD**：GitHub Actions + 腾讯云 TKE 部署
- **API 文档**：FastAPI 自动生成 OpenAPI 文档
- **配置管理**：Consul + Vault (敏感信息管理)
- **容器镜像**：腾讯云容器镜像服务

## 架构原则

### 1. AI Native First
- 任何新功能首先考虑「能否由 AI 主动触发或完成」
- 传统 UI 功能应作为 AI 的工具集存在
- 优先通过对话完成操作，UI 作为辅助而非主体

### 2. 对话即界面
- 主要操作路径通过自然语言完成
- UI 设计遵循「对话优先」原则
- 减少传统导航菜单，功能通过对话触达

### 3. 专业但不冷漠
- AI 人格设定为「亲切的宠物营养师朋友」
- 回复语气亲切专业，避免机械感
- 建立情感连接，增强用户信任

### 4. 安全边界清晰
- AI 明确区分「健康管理建议」与「医疗诊断」
- 医疗问题坚定引导至专业兽医
- 紧急情况使用预置数据库，不依赖 AI 推理

### 5. 家庭协作友好
- 支持多成员共同管理宠物
- 防止重复喂食等安全隐患
- 记录显示操作者，增强协作透明度

## 开发约定

### 代码规范
- **Python 后端**：
  - 遵循 PEP 8 风格指南
  - 使用 Black 进行代码格式化
  - 类型提示 (Type Hints) 必须添加
  - 异步代码使用 `async/await` 模式
- **Vue 前端**：
  - 遵循 Vue 3 风格指南
  - 单文件组件 (SFC) 结构：`<template>`, `<script setup>`, `<style scoped>`
  - 使用 Composition API + `<script setup>` 语法
  - TypeScript 必须用于核心业务逻辑
- **命名约定**：
  - Python：函数/变量 `snake_case`，类 `PascalCase`，常量 `UPPER_SNAKE_CASE`
  - Vue 组件：`PascalCase` (如 `PetProfile.vue`)
  - 文件：`kebab-case` (Python 模块 `.py` 除外)
- **注释要求**：
  - 复杂逻辑必须添加中文注释
  - Python 函数/类必须添加 docstring (Google 格式)
  - Vue 组件必须添加组件描述注释

### Git 工作流
- **分支策略**：Git Flow 简化版
  - `main`：生产环境 (保护分支)
  - `develop`：开发集成 (保护分支)
  - `feature/*`：功能开发 (从 `develop` 切出)
  - `release/*`：发布分支 (从 `develop` 切出)
  - `hotfix/*`：紧急修复 (从 `main` 切出)
- **提交规范**：Conventional Commits
  - `feat:` 新功能
  - `fix:` 修复
  - `docs:` 文档
  - `style:` 样式 (不影响代码逻辑)
  - `refactor:` 重构
  - `test:` 测试
  - `chore:` 构建/工具
  - `perf:` 性能优化
  - `ci:` CI/CD 相关

### 测试策略
- **Python 单元测试**：pytest + pytest-asyncio (覆盖率 > 85%)
- **Vue 单元测试**：Jest + Vue Test Utils (覆盖率 > 80%)
- **集成测试**：
  - API 集成测试：pytest + httpx
  - AI 工具调用测试：模拟 LangGraph 流程
- **E2E 测试**：微信小程序自动化测试 (MiniProgram AutoTest)
- **AI 专项测试**：
  - 意图识别准确率测试 (定期评估)
  - 工具调用成功率监控
  - 响应时间性能测试

#### ⚠️ 单元测试常见陷阱

- **懒导入模块的 mock 目标**：`backend/services/agent/tools.py` 中的第三方依赖（`db`、`settings`、`redis_service` 等）全部**在方法体内按需 `from ... import`**，模块顶层没有这些符号。因此写测试时：
  - ❌ 错误：`patch("services.agent.tools.db")` → 抛 `AttributeError: module has no attribute 'db'`
  - ✅ 正确：`patch("services.database.db")` / `patch("core.config.settings")` / `patch("services.redis.redis_service")`
  - 规律：**patch 原始定义位置，而不是使用点**。仅当被测模块用 `from X import Y` 在**顶层**导入 Y 时，才可以 patch `<被测模块>.Y`。
- **工具类方法名与签名以源码为准**：写测试前先 `grep -n "async def _arun" backend/services/agent/tools.py`，不要凭 CLAUDE.md 或历史记忆推断参数名（如 `weight_kg` 不是 `weight`、`duration_minutes` 不是 `duration`、`goals: List[str]` 不是 `goal: str`）。
- **数据库直连必须 mock**：`GenerateHealthReportTool`、`CalculateNutritionTool` 等在 `_arun` 内部会调用 `db.get_session()`，测试环境无 PostgreSQL 时必须 mock，否则会看到 `Connect call failed ('127.0.0.1', 5432)` 而非真正的业务错误。
- **架构专属 wheel**：Apple Silicon 上跑 `pip install tiktoken` 有时会拉到 x86_64 wheel 导致 `dlopen incompatible architecture`，解决办法：`pip3 install --force-reinstall --no-cache-dir --no-deps tiktoken`。

### 部署流程
1. **开发环境**：
   - 代码推送到 `develop` 分支自动触发 CI
   - 自动部署到腾讯云 TKE 测试集群
   - 自动运行测试套件
2. **预发布环境**：
   - 从 `develop` 创建 `release/*` 分支
   - 手动触发完整功能测试
   - AI 专项测试 + 性能测试
3. **生产环境**：
   - `release/*` 合并到 `main` 分支
   - 代码审核 + 安全扫描通过
   - 蓝绿部署到腾讯云 TKE 生产集群
4. **回滚机制**：
   - TKE 版本回滚 (15分钟保留历史版本)
   - 数据库迁移支持前向/后向兼容

### 文档要求
- **代码文档**：
  - Python：自动生成 API 文档 (FastAPI OpenAPI)
  - Vue：组件 Props/Emits 必须文档化
- **API 文档**：FastAPI 自动生成 OpenAPI 文档 (Swagger UI)
- **架构文档**：系统架构图及时更新 (使用 diagrams.net)
- **运维文档**：
  - 部署流程详细记录
  - 监控告警配置说明
  - 故障处理应急预案
- **产品文档**：功能变更及时更新产品文档 (`docs/` 目录)

## 核心模块架构

### AI Native 系统架构概览
```
┌─────────────────────────────────────────────────────────────┐
│                    微信小程序（uni-app）                       │
│  ┌─────────────────────┐    ┌──────────────────────────┐   │
│  │   AI 对话主界面       │    │    今日状态卡片（动态）    │   │
│  │   文字 / 语音 / 拍照  │    │    AI 生成，每日更新      │   │
│  └─────────────────────┘    └──────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
                             ↕ HTTPS / SSE
┌──────────────────────────────────────────────────────────────┐
│                  AI Agent 编排层（核心）                       │
│                                                               │
│    意图识别 → 上下文注入 → 工具调用 → 结果整合 → 流式回复      │
│                                                               │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│   │  记忆管理器   │  │  情境感知器   │  │   主动推送调度器  │  │
│   │  (三级记忆)   │  │  (健康趋势)   │  │   (晨报/预警)    │  │
│   └──────────────┘  └──────────────┘  └──────────────────┘  │
└──────────────────────────────────────────────────────────────┘
          ↕ 工具调用                    ↕ 数据读写
┌──────────────────────┐    ┌──────────────────────────────────┐
│      工具集合          │    │           数据存储层              │
│  - 档案读写            │    │  PostgreSQL（结构化数据）          │
│  - 营养计算引擎        │    │  pgvector（长期记忆向量）          │
│  - 食物图像识别        │    │  Redis（会话上下文 + 队列）         │
│  - 语音转文字          │    │  腾讯云 COS（图片/语音/PDF）        │
│  - 地图/医院查询       │    └──────────────────────────────────┘
│  - 电商/内容搜索       │
│  - 提醒调度           │
│  - 紧急数据库         │
│  - 报告生成           │
└──────────────────────┘
```

### AI Agent 编排层 (LangGraph)
- **技术选型**：LangGraph - 有状态图支持多步推理，适合营养分析等复杂工具链
- **条件分支**：不同意图可走完全不同的工具调用路径
- **人工确认节点**：AI 给出食谱调整建议前，插入用户确认步骤
- **持久化状态**：天然支持对话中断/恢复

### 完整工具集
| 工具名称 | 功能描述 | 依赖服务 |
|---------|---------|---------|
| `get_pet_profile` | 读取宠物档案（支持多宠物） | PostgreSQL |
| `update_pet_profile` | 更新宠物档案字段 | PostgreSQL |
| `switch_active_pet` | 切换当前活跃宠物上下文 | Redis |
| `log_meal` | 记录饮食（含重复喂食检测） | PostgreSQL + Redis |
| `log_activity` | 记录运动活动 | PostgreSQL |
| `log_weight` | 记录体重 | PostgreSQL |
| `calculate_nutrition` | 精确计算食物营养成分 | 营养数据库 |
| `evaluate_diet_vs_needs` | 对比 AAFCO 标准评估摄入 | 规则引擎 |
| `generate_recipe` | 生成/调整个性化食谱 | 规则引擎 + LLM |
| `recognize_food_image` | 识别照片中的食物 | GPT-4o Vision |
| `transcribe_voice` | 语音转文字 | 腾讯云 ASR |
| `search_nearby_hospital` | 查询附近宠物医院 | 地图 API |

### 数据存储层设计
- **结构化数据**：PostgreSQL 16+ (主数据库，存储用户、宠物、记录等核心数据)
- **向量存储**：pgvector 扩展 (长期记忆语义检索，支持相似问题匹配)
- **缓存与会话**：Redis 7.x (会话上下文管理、Celery Broker、重复检测)
- **文件存储**：腾讯云 COS (图片、语音、PDF 报告等二进制文件)
- **紧急数据库**：本地 JSON 数据库 (关键词预检在前端本地执行，不依赖网络)

### 安全与隐私架构
- **数据加密**：敏感数据端到端加密 (AES-256-GCM)
- **权限控制**：基于角色的细粒度权限 (RBAC + ABAC 混合模型)
- **合规要求**：严格遵循《个人信息保护法》，数据本地化存储
- **审计日志**：所有数据操作完整记录，支持溯源与合规审计
- **安全边界**：AI 明确区分「健康管理建议」与「医疗诊断」，后者坚定引导至兽医

---

*最后更新：2026-04-16*
*参考文档：`docs/PawLife_开发文档_v1.0.docx`*