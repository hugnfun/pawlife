"""
LangGraph 工作流节点实现（最简版本）。

工作流结构：
1. classify_intent - 意图分类节点（只区分闲聊/记录饮食）
2. handle_log_meal - 记录饮食处理节点
3. generate_response - 响应生成节点（支持流式输出）
4. handle_error - 错误处理节点
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, SystemMessage
from sqlalchemy import func, select

from core.config import settings
from models.log import ActivityLog, MealLog, WeightLog
from models.pet import Pet
from services.database import db
from services.memory import memory_service

from .state import AgentState, OnboardingStep

logger = logging.getLogger(__name__)


# 基础系统提示词 - AI 角色定义和行为规则（固定文本）
BASE_SYSTEM_PROMPT = """你是 PawLife，一只宠物的亲切专业 AI 营养师朋友。

你的定位是：**真正懂你宠物的 AI 健康伙伴**

核心原则：
1. 亲切友好：使用朋友般的语气，不要太机械官方
2. 专业可靠：基于数据给出建议，不确定就直说
3. 安全边界：明确区分「健康管理建议」和「医疗诊断」，严重医疗问题一定要引导去正规宠物医院。**如果用户询问医疗问题，请坚定引导用户去正规宠物医院就诊，不要尝试给出诊断。**
4. 宠物优先：永远以宠物健康为首要考量

当前用户正在和你通过自然语言对话，你需要根据上下文信息和分类后的意图给出相应的回复。
"""


# ==================== 紧急意图识别 + 免责声明（requirements-v1.1.md §4） ====================

# 免责声明固定文案（不放入 prompt，在最终输出后置拼接）
DISCLAIMER_TEXT = "\n\n---\n⚠️ 以上建议基于您提供的信息生成，不能替代兽医诊断，如症状持续请及时就医。"

# 高风险关键词清单（命中任一即触发紧急分支，跳过食谱/营养分析）
EMERGENCY_KEYWORDS: Dict[str, List[str]] = {
    "poisoning": [
        "巧克力", "洋葱", "葡萄", "木糖醇", "老鼠药", "吐白沫", "中毒",
        "误食", "舔了", "吃错", "有毒",
    ],
    "trauma": [
        "出血", "流血", "骨折", "被撞", "坠落", "摔", "瘸腿", "外伤", "受伤",
    ],
    "respiratory": [
        "呼吸困难", "气喘", "发绀", "昏迷", "抽搐", "休克", "喘不上气",
        "倒地不起",
    ],
    "digestive": [
        "持续呕吐", "血便", "便血", "腹胀发硬", "异物吞食", "吞了异物",
        "吐血", "剧烈呕吐",
    ],
    "other": [
        "高烧", "痉挛", "体温异常", "体温过高", "体温过低", "失温",
    ],
}

# 紧急分支固定回复模板（不调用 LLM 自由生成）
EMERGENCY_RESPONSE_TEMPLATE = (
    "⚠️ **紧急提醒**\n\n"
    "根据您描述的症状，这可能是紧急医疗情况，建议您**立即联系附近的宠物医院**就诊，"
    "不要等待或尝试自行处理。\n\n"
    "我可以帮您搜索附近的宠物医院，请告诉我您所在的城市或区域。\n\n"
    "请记住：**时间就是生命**，紧急情况请优先就医，不要依赖在线建议。"
)


def detect_emergency_intent(user_input: str) -> Optional[str]:
    """检测用户输入是否命中高风险关键词（requirements-v1.1.md §4.2）。

    纯关键词匹配，不调用 LLM，保证 < 1.5s 响应时间。

    Args:
        user_input: 用户当前输入文本

    Returns:
        命中的风险分类（poisoning / trauma / respiratory / digestive / other），
        未命中返回 None
    """
    text = user_input.lower()
    for category, keywords in EMERGENCY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text:
                return category
    return None


async def emergency_intent_guard(state: AgentState) -> Dict[str, Any]:
    """紧急意图前置守卫节点（requirements-v1.1.md §4）。

    在 classify_intent 之前执行纯关键词匹配，一旦命中高风险关键词：
    - 标记 emergency_triggered=True
    - 设置紧急回复内容（固定文案，不调用 LLM）
    - 直接跳转到 generate_response（跳过 classify_intent 和工具调用链路）

    保证紧急场景响应时间 < 1.5s（纯字符串匹配，无 LLM 调用）。

    Args:
        state: 当前 Agent 状态

    Returns:
        更新后的状态字典
    """
    user_input = state.get("current_input", "")

    category = detect_emergency_intent(user_input)

    if category:
        logger.warning(
            f"紧急意图命中: category={category}, input={user_input[:80]}"
        )
        return {
            "emergency_triggered": True,
            "emergency_category": category,
            "response_content": EMERGENCY_RESPONSE_TEMPLATE,
            "intent": "emergency",
        }

    return {
        "emergency_triggered": False,
        "emergency_category": None,
    }


def should_bypass_for_emergency(state: AgentState) -> str:
    """条件路由：紧急意图是否需要跳过常规流程。

    Returns:
        "generate_response"（紧急分支直接输出固定文案）
        "classify_intent"（正常流程）
    """
    if state.get("emergency_triggered"):
        return "generate_response"
    return "classify_intent"


def _append_disclaimer_if_needed(response: str, state: AgentState) -> str:
    """后置拼接免责声明（requirements-v1.1.md §4.1）。

    当 AI 回复涉及疾病判断倾向、用药建议、食谱推荐时，
    在最终输出末尾拼接固定文案。不由 LLM 自由生成。

    判定条件（满足任一）：
    - intent 为 chit_chat 且用户输入包含健康/疾病相关词
    - 紧急意图已触发
    - 工具调用涉及食谱生成或营养分析

    Args:
        response: LLM 生成的原始回复
        state: 当前 Agent 状态

    Returns:
        拼接了免责声明的回复（如不需要拼接则原样返回）
    """
    # 紧急意图必须拼接
    if state.get("emergency_triggered"):
        return response + DISCLAIMER_TEXT

    # 检查是否涉及疾病/用药/食谱
    intent = state.get("intent", "")
    user_input = state.get("current_input", "")

    # 涉及疾病/用药/食谱的关键词
    health_related_keywords = [
        "生病", "病了", "不吃", "拉肚子", "呕吐", "腹泻", "过敏",
        "用药", "吃药", "药", "诊断", "治疗", "症状",
        "食谱", "营养", "喂什么", "能吃", "不能吃",
    ]
    is_health_related = any(kw in user_input for kw in health_related_keywords)

    # 食谱/营养分析工具调用
    tool_outputs = state.get("tool_outputs") or []
    has_recipe_tool = any(
        t.get("tool_name") in ("generate_recipe", "evaluate_diet_vs_needs")
        for t in tool_outputs
    )

    if is_health_related or has_recipe_tool or intent == "emergency":
        return response + DISCLAIMER_TEXT

    return response


async def build_system_prompt(
    pet_id: Optional[UUID] = None,
    query: str = "",
    limit_memories: int = 3,
) -> str:
    """构建完整的系统提示词，整合角色定义、宠物档案、近期健康摘要和相关记忆。

    整合四个部分：
    1. AI 角色定义和行为规则（固定文本，包含医疗免责规则）
    2. 宠物基本档案（从数据库读取宠物信息）
    3. 近 7 天健康摘要（聚合最近 7 天的体重、饮食、活动数据）
    4. 相关历史记忆（向量检索语义相关的长期记忆）

    Args:
        pet_id: 宠物ID，如果为 None 则不添加宠物相关信息
        query: 用户当前查询文本，用于语义检索相关记忆
        limit_memories: 返回相关记忆的最大数量，默认为 3

    Returns:
        完整拼装好的系统提示词字符串

    Raises:
        不会抛出异常，任何数据库/检索错误都会被记录日志并跳过，不阻断流程
    """
    # 第一部分：基础角色定义
    prompt_parts = [BASE_SYSTEM_PROMPT, ""]

    if pet_id is None:
        return "\n".join(prompt_parts)

    context_parts: List[str] = []

    # 第二部分：宠物基本档案
    try:
        async with db.get_session() as session:
            stmt = select(Pet).where(Pet.id == pet_id, Pet.is_active == True)
            result = await session.execute(stmt)
            pet = result.scalar_one_or_none()

            if pet is not None:
                profile_parts = ["**宠物基本档案**"]
                profile_parts.append(f"- 名字：{pet.name}")
                profile_parts.append(f"- 物种：{pet.species.value if pet.species else '未知'}")
                if pet.breed:
                    profile_parts.append(f"- 品种：{pet.breed}")
                if pet.gender:
                    gender_label = {
                        "male": "公",
                        "female": "母",
                        "unknown": "未知",
                    }.get(pet.gender.value, pet.gender.value)
                    profile_parts.append(f"- 性别：{gender_label}")
                if pet.neutered_status:
                    neutered_label = {
                        "neutered": "已绝育",
                        "intact": "未绝育",
                        "unknown": "未知",
                    }.get(pet.neutered_status.value, pet.neutered_status.value)
                    profile_parts.append(f"- 绝育状态：{neutered_label}")
                if pet.current_weight is not None:
                    profile_parts.append(f"- 当前体重：{float(pet.current_weight):.2f} kg")
                if pet.ideal_weight is not None:
                    profile_parts.append(f"- 理想体重：{float(pet.ideal_weight):.2f} kg")
                if pet.allergy_blacklist:
                    profile_parts.append(f"- 过敏黑名单：{pet.allergy_blacklist}")
                if pet.known_diseases:
                    profile_parts.append(f"- 已知疾病：{pet.known_diseases}")
                if pet.main_food_brand:
                    profile_parts.append(f"- 主粮品牌：{pet.main_food_brand}")

                context_parts.extend(profile_parts)
                context_parts.append("")  # 空行分隔

    except Exception as e:
        logger.warning(f"读取宠物档案失败，跳过: {e}")

    # 第三部分：近 7 天健康摘要（L2 短期记忆）
    try:
        seven_days_ago = datetime.now() - timedelta(days=7)

        async with db.get_session() as session:
            # 1. 近 7 天体重记录平均体重
            weight_stmt = select(func.avg(WeightLog.weight))\
                .where(WeightLog.pet_id == pet_id)\
                .where(WeightLog.measurement_time >= seven_days_ago)\
                .where(WeightLog.is_corrected == False)  # noqa: E712
            avg_weight_result = await session.execute(weight_stmt)
            avg_weight = avg_weight_result.scalar_one_or_none()

            # 2. 今日饮食统计
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            meal_stmt = select(func.count(MealLog.id), func.sum(MealLog.amount))\
                .where(MealLog.pet_id == pet_id)\
                .where(MealLog.meal_time >= today_start)\
                .where(MealLog.is_corrected == False)  # noqa: E712
            meal_result = await session.execute(meal_stmt)
            meal_count, total_amount_g = meal_result.one()

            # 3. 近 7 天活动次数
            activity_stmt = select(func.count(ActivityLog.id))\
                .where(ActivityLog.pet_id == pet_id)\
                .where(ActivityLog.activity_time >= seven_days_ago)\
                .where(ActivityLog.is_corrected == False)  # noqa: E712
            activity_result = await session.execute(activity_stmt)
            activity_count = activity_result.scalar_one_or_none()

        # 构建摘要文本
        l2_parts = []
        if avg_weight is not None:
            l2_parts.append(f"- 近 7 天平均体重: {float(avg_weight):.2f} kg")
        if meal_count and meal_count > 0:
            l2_parts.append(f"- 今日饮食记录: {meal_count} 餐，总计 {float(total_amount_g):.0f} g")
        if activity_count is not None and activity_count > 0:
            l2_parts.append(f"- 近 7 天活动记录: {activity_count} 次")

        if l2_parts:
            context_parts.append("**近期状态摘要（L2 短期记忆）**")
            context_parts.extend(l2_parts)
            context_parts.append("")

    except Exception as e:
        logger.warning(f"聚合近 7 天健康摘要失败，跳过: {e}")

    # 第四部分：相关历史记忆（L3 长期记忆，语义检索）
    if query and query.strip():
        try:
            memories = await memory_service.search_relevant_memories(
                pet_id=pet_id,
                query=query,
                limit=limit_memories,
            )
            if memories:
                context_parts.append("**相关长期记忆（L3 长期记忆）**")
                for i, mem in enumerate(memories, 1):
                    context_parts.append(f"{i}. {mem['content']}")
                context_parts.append("")

        except Exception as e:
            logger.warning(f"检索相关长期记忆失败，跳过: {e}")

    # 将所有上下文拼接到提示词中
    if context_parts:
        prompt_parts.extend(context_parts)

    return "\n".join(prompt_parts)

INTENT_CLASSIFICATION_PROMPT = """
请对用户的输入进行意图分类，区分以下五种：

1. **chit_chat** - 一般性闲聊、问候、宠物健康知识问答，可以直接回答，不需要读写数据
   示例："你好"、"狗狗拉肚子该怎么办"、"猫咪需要补钙吗"、"介绍一下这个 app"

2. **log_meal** - 用户想要记录宠物今天/刚才吃了什么食物，需要记录饮食数据
   示例："我的狗狗刚才吃了一杯狗粮"、"猫咪吃了三文鱼"、"记录一下旺财今天的早餐"、"它今天吃了两个罐头"

3. **get_pet_profile** - 用户想要查询宠物档案信息，比如询问体重、品种、年龄等
   示例："豆豆现在多重？"、"告诉我拉拉的品种"、"狗狗今年几岁了？"、"查看豆豆的档案"

4. **update_pet_profile** - 用户想要更新宠物档案信息，比如修改体重、绝育状态等
   示例："豆豆刚称了体重，32kg"、"豆豆昨天绝育了"、"把拉拉的年龄改成3岁"、"更新猫咪的体重"

5. **correct_log** - 用户想要纠正之前记录的错误数据（饮食/活动/体重）
   示例："刚才记错了，吃的是40g不是50g"、"上次体重记错了，应该是5.2kg"、"记错了，散步是30分钟不是20分钟"

请以 JSON 格式返回：
{{
  "intent": "chit_chat" / "log_meal" / "get_pet_profile" / "update_pet_profile" / "correct_log",
  "confidence": 0.0-1.0,
  "reasoning": "一句话说明判断理由"
}}
"""


def get_llm() -> BaseChatModel:
    """
    获取 LLM 实例。

    优先级：Anthropic Claude > DeepSeek > OpenAI GPT-4o-mini
    通过环境变量配置对应的 API 密钥。
    """
    if settings.anthropic_api_key:
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model="claude-3-5-sonnet-20241022",  # type: ignore[call-arg]
            temperature=0.7,
            api_key=settings.anthropic_api_key,  # type: ignore[arg-type]
            streaming=True,
        )

    if settings.deepseek_api_key:
        # DeepSeek 通过 OpenAI 兼容接口接入
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=settings.deepseek_model,
            temperature=0.7,
            api_key=settings.deepseek_api_key,  # type: ignore[arg-type]
            base_url=settings.deepseek_base_url,
            streaming=True,
        )

    if settings.openai_api_key:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.7,
            api_key=settings.openai_api_key,  # type: ignore[arg-type]
            streaming=True,
        )

    raise RuntimeError(
        "未配置 LLM API 密钥。请在 .env 中设置 DEEPSEEK_API_KEY、ANTHROPIC_API_KEY 或 OPENAI_API_KEY"
    )


async def classify_intent(state: AgentState) -> Dict[str, Any]:
    """
    意图分类节点（最简版本）。

    只区分两种意图：chit_chat / log_meal

    Args:
        state: 当前 Agent 状态

    Returns:
        更新后的状态字典
    """
    llm = get_llm()

    # 使用统一的 build_system_prompt 构建完整系统提示词
    # 包含角色定义、宠物档案、近期摘要和相关记忆
    built_system_prompt = await build_system_prompt(
        pet_id=state.get("pet_id"),
        query=state["current_input"],
        limit_memories=3,
    )

    # 构建消息
    messages = [
        SystemMessage(content=built_system_prompt),
        SystemMessage(content=INTENT_CLASSIFICATION_PROMPT),
        SystemMessage(content=f"用户输入: {state['current_input']}"),
    ]

    try:
        # 调用 LLM 进行意图分类
        response = await llm.ainvoke(messages)

        # 解析 JSON 响应
        import json
        content = str(response.content).strip()
        # 尝试提取 JSON
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        result = json.loads(content)

        logger.info(
            f"意图分类完成: intent={result['intent']}, confidence={result['confidence']}"
        )

        return {
            "intent": result["intent"],
            "intent_confidence": result["confidence"],
            "error": None,
        }

    except Exception as e:
        logger.error(f"意图分类失败: {e}", exc_info=True)
        # 默认归为闲聊
        return {
            "intent": "chit_chat",
            "intent_confidence": 1.0,
            "error": f"意图分类失败: {str(e)}",
        }


def route_by_intent(state: AgentState) -> str:
    """
    条件路由：根据意图选择下一个节点。

    Args:
        state: 当前 Agent 状态

    Returns:
        下一个节点名称
    """
    if state.get("error"):
        return "handle_error"

    intent = state.get("intent", "chit_chat")

    if intent == "log_meal":
        return "handle_log_meal"
    elif intent == "get_pet_profile":
        return "handle_get_pet_profile"
    elif intent == "update_pet_profile":
        return "handle_update_pet_profile"
    elif intent == "correct_log":
        return "handle_correct_log"
    else:
        return "generate_response"


async def handle_log_meal(state: AgentState) -> Dict[str, Any]:
    """
    处理记录饮食意图。

    从用户输入提取结构化食物信息，调用 log_meal 工具写入数据库。

    Args:
        state: 当前 Agent 状态

    Returns:
        更新后的状态字典
    """
    pet_id = state.get("pet_id")
    user_id = state["user_id"]
    user_input = state["current_input"]

    logger.info(f"处理记录饮食: user_id={user_id}, pet_id={pet_id}, input={user_input[:50]}")

    if not pet_id:
        return {
            "tool_outputs": [{
                "tool_name": "log_meal",
                "success": False,
                "error": "未选择当前宠物，请先选择要记录的宠物",
                "data": None,
            }],
            "error": "No active pet selected",
        }

    try:
        from langchain_core.messages import SystemMessage

        from .tools import TOOL_REGISTRY

        # 让 LLM 提取结构化食物信息（支持多个食物）
        llm = get_llm()
        extract_prompt = """
请从用户的输入中提取要记录的饮食信息。用户会描述宠物吃了什么，可能同时吃了多种食物。
你需要提取出**所有食物**，放到 foods 数组中。

每个食物需要：
- food_name: 食物名称（字符串）
- amount_g: 分量（数字，单位克。估算参考："一杯狗粮" ≈ 100g，"一个罐头" ≈ 180g，"一个鸡蛋黄" ≈ 18g，"一小块鸡胸肉" ≈ 100g）

用户输入：{user_input}

请以 JSON 格式返回：
{{
  "foods": [
    {{"food_name": "鸡胸肉", "amount_g": 200}},
    {{"food_name": "鸡蛋黄", "amount_g": 18}}
  ],
  "notes": "这里放额外的整体备注信息，如果没有就写 null"
}}

只返回 JSON，不要其他文字。
"""
        messages = [
            SystemMessage(content=extract_prompt.format(user_input=user_input))
        ]
        response = await llm.ainvoke(messages)

        # 解析 JSON
        import json
        content = str(response.content).strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        data = json.loads(content)
        foods = data.get("foods", [])
        if not foods:
            # 兼容单食物输出，如果 LLM 输出的是旧格式
            if "food_name" in data and "amount" in data:
                foods = [{"food_name": data["food_name"], "amount_g": data["amount"]}]
            elif "food_name" in data and "amount_g" in data:
                foods = [{"food_name": data["food_name"], "amount_g": data["amount_g"]}]

        logger.info(f"提取饮食信息: {len(foods)} 种食物")
        for food in foods:
            logger.info(f"  - {food['food_name']}: {food['amount_g']}g")

        # 重复喂食检测（Redis 缓存）
        import time

        from services.redis import redis_service
        pet_id_str = str(pet_id)
        current_ts = int(time.time())
        is_duplicate = await redis_service.check_duplicate_feeding(pet_id_str, current_ts)

        if is_duplicate:
            # 获取宠物名字生成提示
            pet_name = "它"
            try:
                get_profile_tool = TOOL_REGISTRY["get_pet_profile"]
                profile_result = await get_profile_tool._arun(
                    pet_id=UUID(pet_id) if isinstance(pet_id, str) else pet_id
                )
                if profile_result["success"] and profile_result["data"]:
                    pet_name = profile_result["data"].get("name", pet_name)
            except Exception:
                pass

            # 计算时间差（约数）
            last_feeding_ts = await redis_service.get(f"feeding:{pet_id_str}")
            if last_feeding_ts:
                minutes_ago = int((current_ts - last_feeding_ts) / 60)
                time_text = f"{minutes_ago} 分钟" if minutes_ago > 0 else "不到 1 小时"
            else:
                time_text = "2 小时内"

            # 检测到重复，需要用户确认，不写入数据库
            prompt = f"{pet_name} {time_text}前已经吃过东西了，确定要再记录一次吗？"
            logger.info(f"检测到重复喂食，等待用户确认: pet_id={pet_id}")

            # 暂存提取好的食物信息到状态，用户确认后再写入
            return {
                "response_content": prompt,
                "pending_confirmation": "log_meal",
                "pending_data": {
                    "foods": foods,
                    "notes": data.get("notes"),
                },
                "tool_outputs": [],
                "error": None,
            }

        # 没有重复，逐个调用工具写入数据库
        tool = TOOL_REGISTRY["log_meal"]
        results = []
        all_success = True
        pet_uuid = UUID(pet_id) if isinstance(pet_id, str) else pet_id

        for food in foods:
            result = await tool._arun(
                pet_id=pet_uuid,
                user_id=user_id,
                food_name=food["food_name"],
                amount=food["amount_g"],
                notes=data.get("notes"),
                image_url=None,
            )
            results.append({
                "food": food,
                "result": result,
            })
            if not result["success"]:
                all_success = False

        # 收集成功记录用于回复
        successful_records = [
            {"food_name": r["food"]["food_name"], "amount_g": r["food"]["amount_g"], "meal_log_id": r["result"]["data"]["meal_log_id"]}
            for r in results if r["result"]["success"]
        ]

        logger.info(f"批量记录完成: 总计 {len(foods)}, 成功 {len(successful_records)}")

        return {
            "tool_outputs": [{
                "tool_name": "log_meal",
                "success": all_success,
                "error": None if all_success else "Some records failed",
                "data": {
                    "total_count": len(foods),
                    "success_count": len(successful_records),
                    "records": successful_records,
                },
                "extracted_foods": foods,
            }],
            "error": None if all_success else "Some records failed to save",
        }

    except Exception as e:
        logger.error(f"记录饮食失败: {e}", exc_info=True)
        return {
            "tool_outputs": [{
                "tool_name": "log_meal",
                "success": False,
                "error": str(e),
                "data": None,
            }],
            "error": f"记录失败: {str(e)}",
        }


async def generate_response(state: AgentState) -> Dict[str, Any]:
    """
    响应生成节点。

    整合所有信息生成最终回复给用户。
    支持流式输出，通过 LangGraph astream_events 实现流式透传。

    紧急分支（§4）：如果 emergency_triggered 且已有 response_content（固定文案），
    跳过 LLM 调用，直接拼接免责声明后返回。

    Args:
        state: 当前 Agent 状态

    Returns:
        更新后的状态字典
    """
    # 紧急分支：已有固定回复，跳过 LLM 调用
    response_content = state.get("response_content")
    if state.get("emergency_triggered") and response_content:
        response = _append_disclaimer_if_needed(response_content, state)
        logger.info("紧急分支直接输出固定文案，跳过 LLM（§4）")
        return {
            "response_content": response,
            "error": None,
        }

    llm = get_llm()

    # 使用统一的 build_system_prompt 构建完整系统提示词
    built_system_prompt = await build_system_prompt(
        pet_id=state["pet_id"],
        query=state["current_input"],
        limit_memories=3,
    )

    # 构建完整消息列表
    messages: list[BaseMessage] = [
        SystemMessage(content=built_system_prompt),
    ]

    # 添加额外上下文信息（意图和工具处理结果）
    extra_context_parts = []

    if state["intent"]:
        extra_context_parts.append(f"- 用户意图: {state['intent']}")

    # 添加处理结果（如果是记录饮食）
    tool_outputs = state.get("tool_outputs") or []
    if tool_outputs:
        for output in tool_outputs:
            extra_context_parts.append(f"- 已完成: {output['tool_name']}")
            if output["data"]:
                import json
                try:
                    data_str = json.dumps(output["data"], ensure_ascii=False)
                except Exception:
                    data_str = str(output["data"])
                extra_context_parts.append(f"  信息: {data_str}")

    if extra_context_parts:
        messages.append(SystemMessage(content="附加上下文信息:\n" + "\n".join(extra_context_parts)))

    # 添加对话历史
    from langchain_core.messages import AIMessage, HumanMessage
    for msg in state["messages"]:
        if msg.role == "user":
            messages.append(HumanMessage(content=msg.content))
        elif msg.role == "assistant":
            messages.append(AIMessage(content=msg.content))

    try:
        full_response = ""

        # 注意：流式输出由 LangGraph 的 astream_events 在顶层处理
        # 这里节点内部不需要额外处理回调，LangChain 的 astream 会自动触发事件
        llm_response = await llm.ainvoke(messages)
        full_response = str(llm_response.content)

        logger.info(f"响应生成完成，长度: {len(full_response)}")

        # 保存用户输入和 AI 回复到 L1 工作记忆（Redis）
        from services.redis import redis_service
        session_id = state["session_id"]
        # 用户输入已经在 create_initial_state 追加了，这里只需要追加 AI 回复
        await redis_service.append_session_history(
            session_id=session_id,
            role="assistant",
            content=full_response,
            ttl_seconds=7200,  # 2小时
        )

        # L3 长期记忆写入：将关键操作结果持久化到 pgvector
        pet_id = state.get("pet_id")
        if pet_id:
            await _extract_and_save_memory(state, pet_id)

        # 后置拼接免责声明（§4.1）：涉及疾病/用药/食谱时拼接固定文案
        full_response = _append_disclaimer_if_needed(full_response, state)

        return {
            "response_content": full_response,
            "error": None,
        }

    except Exception as e:
        logger.error(f"响应生成失败: {e}", exc_info=True)
        return {
            "response_content": None,
            "error": f"响应生成失败: {str(e)}",
        }


async def handle_correct_log(state: AgentState) -> Dict[str, Any]:
    """处理数据纠错意图（requirements-v1.1.md §3）。

    用 LLM 从用户输入中提取纠错信息（日志类型、修改字段、原因），
    然后调用 correct_last_log 工具创建纠正版本。

    Args:
        state: 当前 Agent 状态

    Returns:
        更新后的状态字典
    """
    pet_id = state.get("pet_id")
    user_input = state["current_input"]

    logger.info(f"处理数据纠错: pet_id={pet_id}, input={user_input[:80]}")

    if not pet_id:
        return {
            "tool_outputs": [{
                "tool_name": "correct_last_log",
                "success": False,
                "error": "未选择当前宠物，请先选择宠物",
                "data": None,
            }],
            "error": "No active pet selected",
        }

    try:
        llm = get_llm()
        extract_prompt = """
请从用户的输入中提取数据纠错信息。用户想要纠正之前记录的错误数据。

需要提取：
1. log_type: 要纠正的日志类型（meal=饮食 / activity=活动 / weight=体重）
2. corrections: 要修改的字段和值（JSON 对象）
3. reason: 纠正原因（一句话）

常见字段对应：
- 饮食(meal): food_name, amount, unit, meal_time, notes
- 活动(activity): activity_type, duration_minutes, intensity, activity_time, notes
- 体重(weight): weight, measurement_time, notes

用户输入：{user_input}

请以 JSON 格式返回：
{{
  "log_type": "meal",
  "corrections": {{"amount": 40}},
  "reason": "用户说吃的是40g不是50g"
}}

只返回 JSON，不要其他文字。
"""
        messages = [SystemMessage(content=extract_prompt.format(user_input=user_input))]
        response = await llm.ainvoke(messages)

        import json
        content = str(response.content).strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        correction_data = json.loads(content)
        log_type = correction_data.get("log_type", "meal")
        corrections = correction_data.get("corrections", {})
        reason = correction_data.get("reason", "")

        logger.info(f"纠错提取: log_type={log_type}, corrections={corrections}")

        from .tools import TOOL_REGISTRY
        tool = TOOL_REGISTRY["correct_last_log"]
        result = await tool._arun(
            pet_id=str(pet_id),
            log_type=log_type,
            corrections=corrections,
            reason=reason,
        )

        return {
            "tool_outputs": [{
                "tool_name": "correct_last_log",
                "success": result["success"],
                "error": result["error"],
                "data": result["data"],
            }],
            "error": result["error"],
        }

    except Exception as e:
        logger.error(f"数据纠错失败: {e}", exc_info=True)
        return {
            "tool_outputs": [{
                "tool_name": "correct_last_log",
                "success": False,
                "error": str(e),
                "data": None,
            }],
            "error": f"纠错失败: {str(e)}",
        }


async def handle_error(state: AgentState) -> Dict[str, Any]:
    """
    错误处理节点。

    当前面节点出错时，生成友好的错误提示回复。
    """
    error_msg = state.get("error", "未知错误")
    logger.error(f"Agent 工作流错误: {error_msg}")

    # 生成友好的错误回复
    error_response = (
        f"抱歉，处理你的请求时遇到了问题。错误信息: {error_msg}\n\n"
        "请稍后重试，或者换个方式提问。如果是紧急医疗问题，请立即联系附近的宠物医院。"
    )

    return {
        "response_content": error_response,
    }


# ========== 新用户建档引导（Onboarding）节点 ==========

async def check_onboarding_status(state: AgentState) -> Dict[str, Any]:
    """
    检查用户是否需要开始建档引导。

    如果用户还没有任何宠物档案，触发引导流程，开始一步步收集信息。

    Args:
        state: 当前 Agent 状态

    Returns:
        更新后的状态
    """
    from sqlalchemy import select

    from models.pet import Pet
    from services.database import db

    user_id = state["user_id"]

    # 查询用户是否已有宠物
    try:
        async with db.get_session() as session:
            stmt = select(Pet).where(Pet.owner_id == user_id, Pet.is_active == True)
            result = await session.execute(stmt)
            pet_count = len(result.all())

        if pet_count == 0:
            # 没有宠物，开始引导
            logger.info(f"用户无宠物档案，开始新用户建档引导: user_id={user_id}")
            return {
                "onboarding_step": OnboardingStep.COLLECTING_NAME,
                "onboarding_data": {},
                "error": None,
            }
        else:
            # 已有宠物，正常走意图分类
            return {
                "onboarding_step": OnboardingStep.COMPLETED,
                "onboarding_data": {},
                "error": None,
            }

    except Exception as e:
        logger.error(f"检查建档状态失败: {e}", exc_info=True)
        # 检查失败，不阻断流程，继续正常处理
        return {
            "onboarding_step": OnboardingStep.COMPLETED,
            "onboarding_data": {},
            "error": None,
        }


def should_start_onboarding(state: AgentState) -> str:
    """
    条件判断：是否需要开始建档引导。

    Returns:
        下一个节点名称
    """
    if state.get("error"):
        return "handle_error"

    onboarding_step = state.get("onboarding_step", OnboardingStep.NOT_STARTED)

    if onboarding_step == OnboardingStep.COLLECTING_NAME and not state.get("onboarding_data"):
        return "start_onboarding"
    elif onboarding_step != OnboardingStep.NOT_STARTED and onboarding_step != OnboardingStep.COMPLETED:
        # 引导已在进行中，继续处理当前步骤
        return "process_onboarding"
    else:
        # 已完成，走正常流程
        return "classify_intent"


async def start_onboarding_prompt(state: AgentState) -> Dict[str, Any]:
    """
    开始建档引导，输出第一个问题：询问宠物名字。

    AI 主动发起：「你好！我是 PawLife，先告诉我你的狗狗叫什么名字吧」

    Args:
        state: 当前 Agent 状态

    Returns:
        更新后的状态
    """
    # 直接生成引导提问，不需要调用 LLM
    prompt = "你好！我是 PawLife，你的专属宠物健康伙伴。看起来你还没有创建宠物档案，我们先来一起建立一份吧～\n\n先告诉我你的宠物叫什么名字呢？"

    return {
        "response_content": prompt,
        "onboarding_step": OnboardingStep.COLLECTING_NAME,
        "error": None,
    }


async def process_onboarding_step(state: AgentState) -> Dict[str, Any]:
    """
    处理建档引导的当前步骤，提取用户回答，存储数据，准备下一步。

    逐步收集：名字 → 物种 → 品种 → 年龄/生日 → 体重 → 性别 → 绝育状态

    Args:
        state: 当前 Agent 状态

    Returns:
        更新后的状态
    """
    current_step = state.get("onboarding_step", OnboardingStep.NOT_STARTED)
    collected_data = (state.get("onboarding_data") or {}).copy()
    user_input = state["current_input"]

    logger.info(f"处理建档步骤: step={current_step}, input={user_input[:30]}")

    # 提取当前字段
    if current_step == OnboardingStep.COLLECTING_NAME:
        collected_data["name"] = user_input.strip()
        next_step = OnboardingStep.COLLECTING_SPECIES
        next_question = "好名字！它是狗狗还是猫咪呢？"

    elif current_step == OnboardingStep.COLLECTING_SPECIES:
        # 解析物种
        input_lower = user_input.lower()
        if "狗" in input_lower or "犬" in input_lower:
            collected_data["species"] = "dog"
        elif "猫" in input_lower or "咪" in input_lower:
            collected_data["species"] = "cat"
        elif "鸟" in input_lower:
            collected_data["species"] = "bird"
        elif "兔" in input_lower:
            collected_data["species"] = "rabbit"
        else:
            collected_data["species"] = "other"
        next_step = OnboardingStep.COLLECTING_BREED
        next_question = "那它是什么品种呢？"

    elif current_step == OnboardingStep.COLLECTING_BREED:
        collected_data["breed"] = user_input.strip()
        next_step = OnboardingStep.COLLECTING_BIRTHDATE
        next_question = "太棒了！它今年几岁了呢？如果知道出生日期也可以告诉我哦～"

    elif current_step == OnboardingStep.COLLECTING_BIRTHDATE:
        collected_data["birth_input"] = user_input.strip()
        # 这里简化处理，先保存文本，后续可以解析成日期
        next_step = OnboardingStep.COLLECTING_WEIGHT
        next_question = "好的，它现在体重是多少公斤呢？"

    elif current_step == OnboardingStep.COLLECTING_WEIGHT:
        # 尝试提取数字
        import re
        matches = re.findall(r"\d+\.?\d*", user_input)
        if matches:
            collected_data["current_weight"] = float(matches[0])
        next_step = OnboardingStep.COLLECTING_GENDER
        next_question = "它是男生还是女生呢？"

    elif current_step == OnboardingStep.COLLECTING_GENDER:
        input_lower = user_input.lower()
        if "公" in input_lower or "男" in input_lower or "雄" in input_lower:
            collected_data["gender"] = "male"
        elif "母" in input_lower or "女" in input_lower or "雌" in input_lower:
            collected_data["gender"] = "female"
        else:
            collected_data["gender"] = "unknown"
        next_step = OnboardingStep.COLLECTING_NEUTERED
        next_question = "它已经绝育了吗？"

    elif current_step == OnboardingStep.COLLECTING_NEUTERED:
        input_lower = user_input.lower()
        if any(word in input_lower for word in ["已", "做了", "是", "对", "yes"]):
            collected_data["neutered_status"] = "neutered"
        elif any(word in input_lower for word in ["没", "没有", "不", "no"]):
            collected_data["neutered_status"] = "intact"
        else:
            collected_data["neutered_status"] = "unknown"
        next_step = OnboardingStep.COMPLETED
        next_question = None

    else:
        # 未知步骤，完成
        next_step = OnboardingStep.COMPLETED
        next_question = None

    # 更新状态
    updates = {
        "onboarding_step": next_step,
        "onboarding_data": collected_data,
        "error": None,
    }

    if next_question:
        # 还有下一步，输出问题
        updates["response_content"] = next_question
    else:
        # 所有字段收集完成，等待 finalize
        updates["response_content"] = None

    return updates


def check_onboarding_completed(state: AgentState) -> str:
    """
    条件判断：建档是否完成，是否需要最终确认。

    Returns:
        下一个节点名称
    """
    if state.get("error"):
        return "handle_error"

    current_step = state.get("onboarding_step", OnboardingStep.NOT_STARTED)

    if current_step == OnboardingStep.COMPLETED:
        return "finalize_onboarding"
    elif current_step != OnboardingStep.NOT_STARTED and current_step != OnboardingStep.COMPLETED:
        # 继续收集当前步骤
        return "process_onboarding"
    else:
        # 未开始，走正常流程
        return "classify_intent"


async def finalize_onboarding(state: AgentState) -> Dict[str, Any]:
    """
    完成建档：创建宠物档案写入数据库，生成确认卡片。

    Args:
        state: 当前 Agent 状态

    Returns:
        最终状态
    """
    user_id = state["user_id"]
    collected_data = state.get("onboarding_data") or {}

    logger.info(f"完成建档，开始写入数据库: user_id={user_id}, fields={list(collected_data.keys())}")

    try:
        # 调用 create_pet_profile 工具创建档案
        from .tools import TOOL_REGISTRY
        create_tool = TOOL_REGISTRY["create_pet_profile"]
        result = await create_tool._arun(user_id=user_id, name=collected_data["name"])

        if not result["success"]:
            return {
                "response_content": f"创建档案失败: {result['error']}",
                "error": result["error"],
            }

        pet_id = result["data"]["pet_id"]

        # 转换字段并更新
        from uuid import UUID

        from models.pet import NeuteredStatus, PetGender, PetSpecies

        from .tools import TOOL_REGISTRY
        update_tool = TOOL_REGISTRY["update_pet_profile"]

        # 映射收集的数据到模型枚举字段
        updates: Dict[str, Any] = {}

        if "species" in collected_data:
            species_map = {
                "dog": PetSpecies.DOG,
                "cat": PetSpecies.CAT,
                "bird": PetSpecies.BIRD,
                "rabbit": PetSpecies.RABBIT,
                "other": PetSpecies.OTHER,
            }
            updates["species"] = species_map.get(collected_data["species"], PetSpecies.OTHER)

        if "breed" in collected_data:
            updates["breed"] = collected_data["breed"]

        if "current_weight" in collected_data:
            updates["current_weight"] = collected_data["current_weight"]

        if "gender" in collected_data:
            gender_map = {
                "male": PetGender.MALE,
                "female": PetGender.FEMALE,
                "unknown": PetGender.UNKNOWN,
            }
            updates["gender"] = gender_map.get(collected_data["gender"], PetGender.UNKNOWN)

        if "neutered_status" in collected_data:
            neutered_map = {
                "neutered": NeuteredStatus.NEUTERED,
                "intact": NeuteredStatus.INTACT,
                "unknown": NeuteredStatus.UNKNOWN,
            }
            updates["neutered_status"] = neutered_map.get(collected_data["neutered_status"], NeuteredStatus.UNKNOWN)

        # 更新其他字段到数据库
        if updates:
            await update_tool._arun(pet_id=UUID(pet_id), updates=updates)

        # 生成确认卡片文本
        name = collected_data.get("name", "宠物")
        breed = collected_data.get("breed", "")
        gender = collected_data.get("gender", "")
        weight = collected_data.get("current_weight", "")

        gender_text = {"male": "男生", "female": "女生", "unknown": "保密"}.get(gender, gender)
        confirm_text = (
            f"🎉 太棒了！{name} 的档案已经建立完成！\n\n"
            f"**基本信息**\n"
            f"名字：{name}\n"
            f"品种：{breed}\n"
            + (f"性别：{gender_text}\n" if gender else "")
            + (f"体重：{weight} kg\n" if weight else "")
            + "\n"
            "现在你可以记录它的饮食、查看健康分析了。有任何问题随时问我哦！"
        )

        logger.info(f"新用户建档完成: user_id={user_id}, pet_id={pet_id}")

        return {
            "response_content": confirm_text,
            "pet_id": UUID(pet_id),
            "onboarding_step": OnboardingStep.COMPLETED,
            "error": None,
        }

    except Exception as e:
        logger.error(f"完成建档失败: {e}", exc_info=True)
        return {
            "response_content": f"建档失败: {str(e)}\n\n请稍后重试，或者重新开始。",
            "error": str(e),
        }


async def handle_get_pet_profile(state: AgentState) -> Dict[str, Any]:
    """
    处理查询宠物档案意图。

    调用 get_pet_profile 工具读取数据库，结果存入上下文供回复生成。

    Args:
        state: 当前 Agent 状态

    Returns:
        更新后的状态字典
    """
    pet_id = state.get("pet_id")
    user_input = state["current_input"]

    logger.info(f"处理查询宠物档案: pet_id={pet_id}, input={user_input[:50]}")

    if not pet_id:
        return {
            "tool_outputs": [{
                "tool_name": "get_pet_profile",
                "success": False,
                "error": "未选择当前宠物，请先选择要查询的宠物",
                "data": None,
            }],
            "error": "No active pet selected",
        }

    try:
        from .tools import TOOL_REGISTRY
        tool = TOOL_REGISTRY["get_pet_profile"]
        result = await tool._arun(pet_id=pet_id)

        if result["success"]:
            logger.info(f"查询宠物档案成功: pet_id={pet_id}")

        return {
            "tool_outputs": [{
                "tool_name": "get_pet_profile",
                "success": result["success"],
                "error": result["error"],
                "data": result["data"],
            }],
            "error": result["error"],
        }

    except Exception as e:
        logger.error(f"查询宠物档案失败: {e}", exc_info=True)
        return {
            "tool_outputs": [{
                "tool_name": "get_pet_profile",
                "success": False,
                "error": str(e),
                "data": None,
            }],
            "error": f"查询失败: {str(e)}",
        }


async def handle_update_pet_profile(state: AgentState) -> Dict[str, Any]:
    """
    处理更新宠物档案意图。

    从用户输入中提取要更新的字段和值，调用 update_pet_profile 工具写入数据库。

    Args:
        state: 当前 Agent 状态

    Returns:
        更新后的状态字典
    """
    pet_id = state.get("pet_id")
    user_input = state["current_input"]

    logger.info(f"处理更新宠物档案: pet_id={pet_id}, input={user_input[:50]}")

    if not pet_id:
        return {
            "tool_outputs": [{
                "tool_name": "update_pet_profile",
                "success": False,
                "error": "未选择当前宠物，请先选择要更新的宠物",
                "data": None,
            }],
            "error": "No active pet selected",
        }

    try:
        from langchain_core.messages import SystemMessage

        from .tools import TOOL_REGISTRY

        # 先让 LLM 提取要更新的字段和值
        llm = get_llm()
        extract_prompt = """
请从用户的输入中提取要更新的宠物档案字段和对应的值。
支持更新的字段：
- name: 名字 (字符串)
- breed: 品种 (字符串)
- current_weight: 当前体重 (浮点数，单位公斤)
- neutered_status: 绝育状态 ("neutered" / "intact" / "unknown")
- known_diseases: 已知疾病 (字符串)
- main_food_brand: 主粮品牌 (字符串)

用户输入：{user_input}

请以 JSON 格式返回，只包含要更新的字段：
{{
  "current_weight": 32.0,
  "neutered_status": "neutered"
}}
"""
        messages = [
            SystemMessage(content=extract_prompt.format(user_input=user_input))
        ]
        response = await llm.ainvoke(messages)

        # 解析 JSON
        import json
        content = str(response.content).strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        updates = json.loads(content)

        # 如果提取出 neutered_status 文本，转换为标准值
        if "neutered_status" in updates and isinstance(updates["neutered_status"], str):
            text = updates["neutered_status"].lower()
            if any(word in text for word in ["已", "做了", "绝育", "neuter"]):
                updates["neutered_status"] = "neutered"
            elif any(word in text for word in ["没", "没有", "未"]):
                updates["neutered_status"] = "intact"

        logger.info(f"提取更新字段: {list(updates.keys())}")

        # 调用工具更新
        tool = TOOL_REGISTRY["update_pet_profile"]
        result = await tool._arun(pet_id=pet_id, updates=updates)

        if result["success"]:
            logger.info(f"更新宠物档案成功: pet_id={pet_id}, updated_fields={list(updates.keys())}")

        return {
            "tool_outputs": [{
                "tool_name": "update_pet_profile",
                "success": result["success"],
                "error": result["error"],
                "data": result["data"],
                "extracted_updates": updates,
            }],
            "error": result["error"],
        }

    except Exception as e:
        logger.error(f"更新宠物档案失败: {e}", exc_info=True)
        return {
            "tool_outputs": [{
                "tool_name": "update_pet_profile",
                "success": False,
                "error": str(e),
                "data": None,
            }],
            "error": f"更新失败: {str(e)}",
        }


# ========== 待确认操作处理（重复喂食确认等） ==========

def check_pending_confirmation(state: AgentState) -> Dict[str, Any]:
    """
    检查是否存在待用户确认的操作。

    如果有，直接进入处理流程，不需要重新意图分类。

    Args:
        state: 当前 Agent 状态

    Returns:
        更新后的状态
    """
    pending = state.get("pending_confirmation")
    if pending:
        logger.info(f"存在待确认操作: {pending}")
    return {
        # 不改变状态，只做检查
    }


def should_process_pending(state: AgentState) -> str:
    """
    条件判断：是否需要处理待确认操作。

    Returns:
        下一个节点名称
    """
    if state.get("error"):
        return "handle_error"

    pending = state.get("pending_confirmation")
    if pending:
        return "process_pending"
    else:
        return "classify_intent"


async def process_pending_confirmation(state: AgentState) -> Dict[str, Any]:
    """
    处理待确认操作：根据用户回答确认或取消。

    目前支持：log_meal（重复喂食确认）

    Args:
        state: 当前 Agent 状态

    Returns:
        更新后的状态
    """
    from uuid import UUID
    pending_type = state.get("pending_confirmation")
    pending_data = state.get("pending_data") or {}
    user_input = state["current_input"].lower()
    pet_id = state.get("pet_id")
    user_id = state["user_id"]

    logger.info(f"处理待确认操作: type={pending_type}, input={user_input[:30]}")

    # 目前只支持 log_meal
    if pending_type != "log_meal":
        # 未知类型，清除状态，走正常流程
        return {
            "pending_confirmation": None,
            "pending_data": None,
        }

    # 判断用户是否确认
    confirm_words = ["是", "对", "是的", "确定", "确认", "要", "好", "y", "yes"]
    cancel_words = ["不", "不是", "不用", "取消", "算了", "n", "no"]

    # 目前只对"取消"做严格匹配，其他非取消输入默认视为继续记录；
    # 若未来需要严格双向确认，可启用下面的 is_confirmed 判断
    _is_confirmed = any(word in user_input for word in confirm_words)  # noqa: F841 保留用于将来更严格的确认逻辑
    is_canceled = any(word in user_input for word in cancel_words)

    if is_canceled:
        # 用户取消操作，清除状态
        logger.info("用户取消了重复喂食记录")
        pet_name = "它"
        try:
            from .tools import TOOL_REGISTRY
            get_profile_tool = TOOL_REGISTRY["get_pet_profile"]
            profile_result = await get_profile_tool._arun(pet_id=pet_id)
            if profile_result["success"] and profile_result["data"]:
                pet_name = profile_result["data"].get("name", pet_name)
        except Exception:
            pass

        return {
            "response_content": f"好的，{pet_name} 的这次喂食不记录了😊",
            "pending_confirmation": None,
            "pending_data": None,
            "error": None,
        }

    # 用户确认，继续写入数据库
    foods = pending_data.get("foods", [])
    notes = pending_data.get("notes")

    if not foods:
        return {
            "response_content": "没有待记录的食物信息，操作已取消",
            "pending_confirmation": None,
            "pending_data": None,
            "error": "No foods in pending data",
        }

    if not pet_id:
        return {
            "response_content": "未选择当前宠物，无法记录",
            "pending_confirmation": None,
            "pending_data": None,
            "error": "No active pet selected",
        }

    try:
        import time

        from services.redis import redis_service

        from .tools import TOOL_REGISTRY

        # 需要手动清除 Redis 标记，因为之前检测重复时已经标记了存在
        # 这里用户确认了，允许写入，所以清除标记让它可以写入
        pet_id_str = str(pet_id)

        # 逐个写入数据库
        tool = TOOL_REGISTRY["log_meal"]
        results = []
        all_success = True
        pet_uuid = UUID(pet_id) if isinstance(pet_id, str) else pet_id

        for food in foods:
            result = await tool._arun(
                pet_id=pet_uuid,
                user_id=user_id,
                food_name=food["food_name"],
                amount=food["amount_g"],
                notes=notes,
                image_url=None,
            )
            results.append({
                "food": food,
                "result": result,
            })
            if not result["success"]:
                all_success = False

        # 更新 Redis 最后喂食时间戳
        current_ts = int(time.time())
        await redis_service.set(f"feeding:{pet_id_str}", current_ts, expire=7200)

        # 收集成功记录
        successful_records = [
            {"food_name": r["food"]["food_name"], "amount_g": r["food"]["amount_g"], "meal_log_id": r["result"]["data"]["meal_log_id"]}
            for r in results if r["result"]["success"]
        ]

        logger.info(f"重复喂食确认后记录完成: 总计 {len(foods)}, 成功 {len(successful_records)}")

        return {
            "tool_outputs": [{
                "tool_name": "log_meal",
                "success": all_success,
                "error": None if all_success else "Some records failed",
                "data": {
                    "total_count": len(foods),
                    "success_count": len(successful_records),
                    "records": successful_records,
                },
                "extracted_foods": foods,
            }],
            "pending_confirmation": None,
            "pending_data": None,
            "error": None if all_success else "Some records failed to save",
        }

    except Exception as e:
        logger.error(f"处理确认记录失败: {e}", exc_info=True)
        return {
            "response_content": f"记录失败: {str(e)}",
            "pending_confirmation": None,
            "pending_data": None,
            "error": str(e),
        }


# ========== L3 长期记忆写入 ==========

async def _extract_and_save_memory(state: AgentState, pet_id) -> None:
    """从 Agent 状态中提取值得长期记忆的信息并写入 L3。

    写入条件（满足任一即写入）：
    1. 有成功的工具调用（记录饮食、活动、体重等操作结果）
    2. 用户更新了宠物档案（体重变更、绝育状态等）

    记忆内容会精炼为简洁的事实描述，避免写入冗长的对话文本。

    Args:
        state: 当前 Agent 状态
        pet_id: 宠物ID
    """

    try:
        tool_outputs = state.get("tool_outputs", [])
        if not tool_outputs:
            return

        memory_content_parts = []

        for output in tool_outputs:
            if not output.get("success"):
                continue

            tool_name = output.get("tool_name", "")
            data = output.get("data")

            if not data:
                continue

            if tool_name == "log_meal":
                records = data.get("records", [])
                for r in records:
                    memory_content_parts.append(
                        f"喂食记录：{r.get('food_name', '')} {r.get('amount_g', 0)}g"
                    )

            elif tool_name == "log_activity":
                memory_content_parts.append(
                    f"活动记录：{data.get('activity_type', '')} {data.get('duration_minutes', 0)}分钟"
                )

            elif tool_name == "log_weight":
                memory_content_parts.append(
                    f"体重记录：{data.get('weight_kg', 0)}kg"
                )

            elif tool_name == "update_pet_profile":
                extracted = output.get("extracted_updates", {})
                if extracted:
                    update_desc = "、".join(f"{k}={v}" for k, v in extracted.items())
                    memory_content_parts.append(f"档案更新：{update_desc}")

            elif tool_name == "schedule_reminder":
                memory_content_parts.append(
                    f"设置提醒：{data.get('title', '')}（{data.get('reminder_type', '')}）"
                )

        # 将所有提取的片段合并为一条记忆
        if memory_content_parts:
            memory_text = "；".join(memory_content_parts)
            # 附加时间戳上下文
            from datetime import datetime
            time_str = datetime.now().strftime("%Y-%m-%d %H:%M")
            memory_text = f"[{time_str}] {memory_text}"

            result = await memory_service.add_memory(
                pet_id=pet_id,
                content=memory_text,
                source="conversation",
                importance=3,
            )

            if result.get("success"):
                logger.info(f"L3 记忆写入成功: pet_id={pet_id}, content={memory_text[:80]}")
            else:
                logger.warning(f"L3 记忆写入失败: {result.get('error')}")

    except Exception as e:
        # 记忆写入失败不影响主流程
        logger.warning(f"L3 记忆写入异常，已跳过: {e}")
