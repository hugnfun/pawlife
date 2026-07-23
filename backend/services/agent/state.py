"""
Agent 状态定义。

定义 LangGraph 工作流中使用的状态类型。
遵循 LangGraph 最佳实践，使用 TypedDict 定义状态结构。
"""

from typing import Any, Dict, List, Optional, TypedDict
from uuid import UUID

from schemas.ai import AIMessage


# 新用户引导步骤枚举
class OnboardingStep:
    """新用户档案建立引导步骤。"""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COLLECTING_NAME = "collecting_name"
    COLLECTING_SPECIES = "collecting_species"
    COLLECTING_BREED = "collecting_breed"
    COLLECTING_BIRTHDATE = "collecting_birthdate"
    COLLECTING_WEIGHT = "collecting_weight"
    COLLECTING_GENDER = "collecting_gender"
    COLLECTING_NEUTERED = "collecting_neutered"
    COMPLETED = "completed"


class AgentState(TypedDict):
    """
    AI Agent 核心状态。

    包含对话上下文、用户信息、宠物信息、工具调用结果等所有在工作流节点间传递的状态。
    """

    # 用户 ID
    user_id: UUID
    # 当前活跃宠物 ID（可选）
    pet_id: Optional[UUID]
    # 会话 ID
    session_id: str
    # 消息历史
    messages: List[AIMessage]
    # 当前用户输入
    current_input: str
    # 输入类型 (text/voice/image)
    input_type: str
    # 语音/图片 URL（如果输入类型不是 text）
    input_url: Optional[str]

    # 意图分类结果
    intent: Optional[str]
    # 置信度
    intent_confidence: Optional[float]
    # 是否需要工具调用
    needs_tool_call: bool
    # 工具调用列表（支持多工具调用）
    tool_calls: Optional[List[Dict[str, Any]]]
    # 工具调用执行结果
    tool_outputs: Optional[List[Dict[str, Any]]]

    # 最终回复内容
    response_content: Optional[str]
    # 建议的后续问题
    suggestions: Optional[List[str]]

    # 流式输出回调（用于 SSE 流式推送）
    stream_callback: Optional[Any]

    # 错误信息
    error: Optional[str]

    # 新用户引导状态（新增档案建立流程）
    onboarding_step: Optional[str]  # OnboardingStep 枚举值
    # 引导过程中收集的宠物数据
    onboarding_data: Optional[Dict[str, Any]]  # 已收集的字段

    # 待用户确认的操作（比如重复喂食确认）
    pending_confirmation: Optional[str]  # 待确认的操作类型
    # 待确认操作暂存的数据
    pending_data: Optional[Dict[str, Any]]  # 暂存的数据

    # 紧急意图检测（requirements-v1.1.md §4）
    # 是否命中高风险关键词
    emergency_triggered: bool
    # 命中的风险分类（poisoning / trauma / respiratory / digestive / other / None）
    emergency_category: Optional[str]


async def create_initial_state(
    user_id: UUID,
    session_id: str,
    current_input: str,
    pet_id: Optional[UUID] = None,
    input_type: str = "text",
    input_url: Optional[str] = None,
    messages: Optional[List[AIMessage]] = None,
    stream_callback: Optional[Any] = None,
    onboarding_step: Optional[str] = None,
    onboarding_data: Optional[Dict[str, Any]] = None,
    pending_confirmation: Optional[str] = None,
    pending_data: Optional[Dict[str, Any]] = None,
) -> AgentState:
    """
    创建初始 Agent 状态。

    从 Redis 加载 L1 工作记忆（会话历史），然后追加当前用户输入。

    Args:
        user_id: 用户 ID
        session_id: 会话 ID
        current_input: 当前用户输入
        pet_id: 当前活跃宠物 ID
        input_type: 输入类型
        input_url: 输入文件 URL
        messages: 已有消息历史（如果提供，优先使用这个，不从 Redis 加载）
        stream_callback: 流式输出回调函数
        onboarding_step: 引导步骤（如果正在引导中）
        onboarding_data: 已收集的引导数据
        pending_confirmation: 待确认的操作类型
        pending_data: 待确认操作暂存的数据

    Returns:
        初始化的 AgentState
    """
    from services.redis import redis_service

    # 从 Redis 加载历史，如果 messages 没有提供
    if messages is None:
        # 加载 L1 历史
        history_data = await redis_service.get_session_history(session_id, max_messages=20)
        current_messages = [
            AIMessage(role=msg["role"], content=msg["content"])  # type: ignore[call-arg]
            for msg in history_data
        ]
    else:
        # 使用提供的历史
        current_messages = messages.copy()

    # 将当前用户输入添加到消息历史
    current_messages.append(
        AIMessage(
            role="user",
            content=current_input,
        )  # type: ignore[call-arg]
    )

    return AgentState(
        user_id=user_id,
        pet_id=pet_id,
        session_id=session_id,
        messages=current_messages,
        current_input=current_input,
        input_type=input_type,
        input_url=input_url,
        intent=None,
        intent_confidence=None,
        needs_tool_call=False,
        tool_calls=None,
        tool_outputs=None,
        response_content=None,
        suggestions=None,
        stream_callback=stream_callback,
        error=None,
        onboarding_step=onboarding_step or OnboardingStep.NOT_STARTED,
        onboarding_data=onboarding_data or {},
        pending_confirmation=pending_confirmation,
        pending_data=pending_data,
        emergency_triggered=False,
        emergency_category=None,
    )
