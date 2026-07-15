# PawLife 需求修改文档 v1.1 —— AI 交互与数据可信度补充规范

> **版本**：v1.1（在 [PawLife_开发文档_v1.0.docx](./PawLife_开发文档_v1.0.docx) 基础上的增量修正）
> **生效范围**：所有后续 PR 的需求依据，优先级高于原 v1.0 中相冲突的条款
> **相关文档**：[change-audit.md](./change-audit.md)（52 处未提交变更核查表）、[REDIS_CACHE_OPTIMIZATION_REPORT.md](../REDIS_CACHE_OPTIMIZATION_REPORT.md)（性能优化 Round 1）
> **最后更新**：2026-07-14

---

## 1. 背景与问题陈述

原需求定义"AI 作为唯一交互层"，用户通过自然语言完成包括健康数据记录（喂食、体重、活动）在内的所有操作。这一设计在情感化产品体验上有优势，但存在两个尚未在需求层面明确的风险：

1. **数据准确性风险**：语音转文字（腾讯云 ASR）或大模型意图识别存在错误率，错误结果一旦被写入数据库并进入"三级记忆"和"健康趋势"分析模块，会造成数据污染且难以事后清洗。
2. **合规边界风险**：健康建议、食谱生成、异常预警等 AI 输出内容，用户可能将其误解为专业诊断意见，产品在责任边界上缺乏明确约束。
3. **数据出境风险**：Claude 3.5 Sonnet / GPT-4o 均为境外服务，原始对话文本可能包含 PII，需要在架构层面做数据分类。

本文档针对以上问题给出具体的需求修改条款，作为 v1.0 需求文档的增量补丁。

---

## 2. 交互模式修改：双通道输入原则（P1 迭代 1）

### 2.1 需求条款

原需求中"用户通过自然语言对话完成所有健康管理操作"应修改为：

> **AI 对话为默认与首选交互方式，但高频结构化数据（喂食记录、体重打点、用药提醒）必须同时提供表单式录入通道作为对话的平行入口，而非仅作为对话失败后的兜底。**

### 2.2 落地要求

- **统一数据校验**：[log_meal](../backend/services/agent/tools.py)、[log_weight](../backend/services/agent/tools.py)、[log_activity](../backend/services/agent/tools.py) 等写入接口在返回给前端时，走同一套数据校验和存储逻辑，不区分数据来源是对话解析还是表单直填。
- **两阶段写入**：前端在对话界面中每次由 AI 提取出结构化数据后，展示一张可编辑的**"确认卡片"**：
  > 例：`检测到：三花 今天 12:30 吃了 50g 鸡胸肉，确认记录吗？`
- 用户点击「确认」或「修改后确认」才真正写入数据库；点击「取消」丢弃提取结果。
- **禁止静默入库**：AI 解析完直接调用 `log_meal` 落库的路径必须废弃。

### 2.3 影响的代码位置

| 位置 | 变更 |
|------|------|
| [backend/services/agent/graph.py](../backend/services/agent/graph.py) | 新增 `structured_extraction` 节点，与 `tool_execution` 解耦 |
| [backend/services/agent/nodes.py](../backend/services/agent/nodes.py) | `log_meal` 等写入节点改为返回"待确认结构体"，不直接调用工具 |
| [backend/schemas/logs.py](../backend/schemas/logs.py) | 新增 `PendingLogConfirmation` 响应体（含 draft_id、TTL） |
| [frontend/src/pages/chat/index.vue](../frontend/src/pages/chat/index.vue) | SSE 消息解析支持 `confirmation_card` 事件类型 |
| [frontend/src/stores/chat.ts](../frontend/src/stores/chat.ts) | 新增 `pendingConfirmations` 状态 |

### 2.4 验收标准（P1）

- 用户从对话到确认入库的完整链路在真实设备（微信小程序）响应时间 **< 3s（P95）**
- 交互步骤数 **≤ 2 步**（AI 返回卡片 → 用户点击确认）
- 静默入库路径的单元测试全部下线，被 `test_confirmation_card_required` 替换

---

## 3. 数据纠错闭环需求（P1 迭代 2）

### 3.1 需求条款

用户必须能够通过对话直接纠正已记录的错误数据，且纠错操作本身要被审计和追踪。

> 例：用户说「刚才记错了，三花吃的是 40g 不是 50g」，Agent 需要能够定位到最近一条相关记录并触发修改确认，而不是新增一条重复记录。

### 3.2 落地要求

- **新增工具函数**：在 [backend/services/agent/tools.py](../backend/services/agent/tools.py) 增加 `correct_last_log(pet_id, log_type, field, new_value)`。
- **数据模型扩展**：[backend/models/log.py](../backend/models/log.py) 的 `MealLog` / `ActivityLog` / `WeightLog` 三类模型新增字段：
  - `corrected_from_id: UUID | None` —— 指向被纠正的原始记录
  - `correction_reason: str | None` —— 纠正原因摘要
  - `is_corrected: bool` —— 是否为纠正版本
- **Alembic 迁移**：新增迁移文件 `002_add_correction_fields.py`。
- **记忆一致性**：[backend/services/memory.py](../backend/services/memory.py) 的记忆写入逻辑，读取历史数据时必须过滤 `is_corrected=True` 优先，避免旧值被纳入趋势计算。

### 3.3 验收标准

- 评测集中「二次纠正」场景（连续两次纠正同一条记录）的成功率 ≥ 90%
- 纠正后的记录在 [get_pet_profile](../backend/services/agent/tools.py) 读取时永远返回最新版本

---

## 4. AI 建议内容的边界与免责声明需求（P2）

### 4.1 需求条款

所有涉及**疾病判断倾向、用药建议、食谱推荐**的 AI 输出，必须在内容中包含明确的边界表述：

> 「以上建议基于您提供的信息生成，不能替代兽医诊断，如症状持续请及时就医。」

**这条表述不能由 LLM 自由生成**，而应该是系统在特定意图分类下**强制拼接的固定文案**，避免模型在某次回复中遗漏或弱化免责声明。

### 4.2 高风险意图清单

一旦命中以下任一关键词或语义分类，Agent 的首要任务是引导用户立即联系兽医或使用 [search_nearby_hospital](../backend/services/agent/tools.py) 工具查找最近医院，**而不是继续生成食谱或营养分析**：

| 分类 | 关键词/语义 |
|------|-------------|
| 中毒 | 巧克力、洋葱、葡萄、木糖醇、老鼠药、吐白沫、抽搐 |
| 外伤 | 出血、骨折、被撞、坠落、瘸腿 |
| 呼吸/循环 | 呼吸困难、气喘、发绀、昏迷、抽搐 |
| 消化急症 | 持续呕吐、血便、腹胀发硬、异物吞食 |
| 其他 | 高烧、痉挛、体温异常 |

### 4.3 落地要求

- **LangGraph 图结构调整**：[backend/services/agent/graph.py](../backend/services/agent/graph.py) 新增前置节点 `emergency_intent_guard`，优先级高于常规工具调用链路。
- **免责声明拼接位置**：[backend/services/agent/nodes.py](../backend/services/agent/nodes.py) 的最终输出节点，在检测到相关意图后**后置拼接**固定文案，不放入 prompt。
- **意图分类持久化**：每条 AI 回复的分类结果写入 [backend/models/audit.py](../backend/models/audit.py)，便于事后审计与评测。

### 4.4 验收标准

- 高风险意图测试用例集下，固定文案触发率 **= 100%**
- 紧急场景分支响应时间（从意图识别到弹出医院搜索）**< 1.5s**
- LLM 自由生成中出现「诊断」「确诊」「必须服用」等禁用词的比例 = 0（通过后置正则校验）

---

## 5. 数据合规与出境处理需求（占位，详细条款延后到 P3）

### 5.1 需求条款（框架）

在 P3 阶段产出独立文档 `docs/data-classification.md`，将用户数据分为三类：

| 类别 | 定义 | 处理方式 |
|------|------|----------|
| **一类（低敏感）** | 宠物物种、品种、健康趋势统计摘要 | 可直接发送给境外 LLM |
| **二类（PII 风险）** | 用户自然语言原始输入（可能含地址、联系方式） | 发送前必须做 PII 检测与脱敏 |
| **三类（境内处理）** | 宠物照片（含拍摄地点元数据）、语音原始文件 | 使用腾讯云 ASR / 境内视觉模型识别，仅将结构化文本传给境外 LLM |

### 5.2 P3 阶段任务清单

- 编写完整的 [data-classification.md](./data-classification.md)
- 审计 [backend/services/agent/tools.py](../backend/services/agent/tools.py) 中每个工具的数据流向
- 引入 PII 检测中间件（正则 + 命名实体识别）
- 明确影像/语音的境内识别链路

### 5.3 验收标准（P3）

- 现有 [tools.py](../backend/services/agent/tools.py) 中每个工具函数在实际调用时经过的数据流向 100% 符合分类要求
- PII 检测中间件对身份证号、手机号、详细地址的召回率 ≥ 95%

---

## 6. 验收标准汇总

| 需求条款 | 所在阶段 | 关键指标 |
|----------|----------|----------|
| §2 确认卡片 | P1 迭代 1 | 响应时间 < 3s / 步骤 ≤ 2 |
| §3 纠错闭环 | P1 迭代 2 | 二次纠正成功率 ≥ 90% |
| §4 免责声明 | P2 | 固定文案触发率 = 100% |
| §4 紧急场景分支 | P2 | 响应时间 < 1.5s |
| §5 数据分类 | P3 | 工具数据流向合规率 = 100% |

以上验收标准附加在 P3 阶段的评测计划里，作为 AI 能力增强阶段的**强制性通过条件**，而不是可选项。

---

## 7. 版本追溯

| 版本 | 日期 | 变更摘要 |
|------|------|----------|
| v1.0 | 见 [PawLife_开发文档_v1.0.docx](./PawLife_开发文档_v1.0.docx) | 初版需求 |
| v1.1 | 2026-07-14 | 新增双通道输入、数据纠错、免责声明、数据分类四类补充需求 |
