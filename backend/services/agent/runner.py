"""
Agent 运行入口。

提供同步和流式两种运行方式，供上层 API 路由调用。
使用 LangGraph 的 astream_events 原生支持流式输出。
"""

import logging
from typing import Any, AsyncGenerator, Dict, List, Optional
from uuid import UUID

from langchain_core.messages import BaseMessage

from schemas.ai import AIConversationResponse, AIMessage

from .graph import get_agent_graph
from .state import AgentState, create_initial_state

logger = logging.getLogger(__name__)
agent_graph = get_agent_graph()


async def run_agent(
    user_id: UUID,
    session_id: str,
    message: str,
    pet_id: Optional[UUID] = None,
    message_type: str = "text",
    input_url: Optional[str] = None,
    history: Optional[List[AIMessage]] = None,
) -> AIConversationResponse:
    """
    运行 Agent 非流式推理。

    Args:
        user_id: 用户 ID
        session_id: 会话 ID
        message: 用户消息
        pet_id: 当前活跃宠物 ID
        message_type: 消息类型 (text/voice/image)
        input_url: 输入文件 URL
        history: 历史消息

    Returns:
        完整的对话响应
    """
    # 创建初始状态（从 Redis 加载 L1 历史）
    initial_state = await create_initial_state(
        user_id=user_id,
        session_id=session_id,
        current_input=message,
        pet_id=pet_id,
        input_type=message_type,
        input_url=input_url,
        messages=history,
        stream_callback=None,
    )

    # 运行图
    final_state = await agent_graph.ainvoke(initial_state)  # type: ignore[attr-defined]

    # 检查错误
    if final_state.get("error") and not final_state.get("response_content"):
        return AIConversationResponse(  # type: ignore[call-arg]
            response=f"处理失败: {final_state['error']}",
            session_id=session_id,
            pet_id=pet_id,
        )

    # 构造响应
    return AIConversationResponse(
        response=final_state.get("response_content") or "处理完成",
        session_id=session_id,
        tool_calls=final_state.get("tool_outputs"),
        pet_id=pet_id,
        suggestions=final_state.get("suggestions"),
    )


async def run_agent_streaming(
    user_id: UUID,
    session_id: str,
    message: str,
    pet_id: Optional[UUID] = None,
    message_type: str = "text",
    input_url: Optional[str] = None,
    history: Optional[List[AIMessage]] = None,
    onboarding_step: Optional[str] = None,
    onboarding_data: Optional[Dict[str, Any]] = None,
) -> AsyncGenerator[Any, None]:
    """
    运行 Agent 流式推理，使用 LangGraph astream_events 原生流式支持。

    监听 `on_chat_model_stream` 事件，直接将 Claude 的 token chunk 透传输出。
    如果节点已经预先生成了完整回复（比如 onboarding 引导提问），直接分段输出。

    另外：如果本轮工具调用产生了需要用户确认的草稿（requires_confirmation=True），
    在流末尾追加 yield 一个 dict 事件 `{"type": "confirmation_card", "data": {...}}`
    供 SSE 路由包装为特殊事件类型转发给前端。

    Args:
        user_id: 用户 ID
        session_id: 会话 ID
        message: 用户消息
        pet_id: 当前活跃宠物 ID
        message_type: 消息类型
        input_url: 输入文件 URL
        history: 历史消息
        onboarding_step: 当前引导步骤（如果正在建档中）
        onboarding_data: 已收集的建档数据

    Yields:
        - str：Claude 流式 token 或预生成回复段落
        - dict：结构化事件（当前支持 `type: confirmation_card`），
                供 chat 路由映射为专属 SSE event。
    """
    # 创建初始状态，保留 onboarding 上下文（从 Redis 加载 L1 历史）
    initial_state = await create_initial_state(
        user_id=user_id,
        session_id=session_id,
        current_input=message,
        pet_id=pet_id,
        input_type=message_type,
        input_url=input_url,
        messages=history,
        stream_callback=None,
        onboarding_step=onboarding_step,
        onboarding_data=onboarding_data,
    )

    # 保存最终状态引用，我们需要在流式事件结束后检查它
    final_state = None

    # 使用 astream_events 进行流式推理，获取每个事件
    has_llm_stream = False
    pregenerated_response = None

    async for event in agent_graph.astream_events(initial_state, version="v1"):  # type: ignore[attr-defined]
        kind = event["event"]

        # 监听 LLM 流式输出事件，这是 Claude token 流的出口
        if kind == "on_chat_model_stream":
            has_llm_stream = True
            chunk: BaseMessage = event["data"]["chunk"]
            if chunk.content:
                # 提取 token 内容直接透传
                # content 格式可能是列表，但对于 Claude 通常是字符串
                if isinstance(chunk.content, str):
                    yield chunk.content
                elif isinstance(chunk.content, list) and len(chunk.content) > 0:
                    # 处理多模态情况，简单取第一个文本块
                    for part in chunk.content:
                        if isinstance(part, dict) and part.get("type") == "text":
                            yield part.get("text", "")

        # 流式结束后获取最终状态
        # 注意：不同版本的 LangGraph tags 标识不同，宽松匹配根节点
        if kind == "on_chain_end":
            output = event.get("data", {}).get("output")
            # 顶层 chain end 的 output 是完整的 AgentState (含 response_content)
            if isinstance(output, dict) and "response_content" in output:
                final_state = output

    # 处理情况：如果节点已经预先生成了完整回复（onboarding 引导步骤）
    # 我们需要把这个回复输出，因为它没有经过 LLM 流式
    if final_state and not has_llm_stream:
        pregenerated_response = final_state.get("response_content")
        if pregenerated_response:
            # 简单按段落分割输出，模拟流式效果
            import re
            paragraphs = re.split(r'(\n+)', pregenerated_response)
            for segment in paragraphs:
                if segment:
                    yield segment

    # 双通道输入：扫描 tool_outputs，若有 requires_confirmation 项则追加 confirmation_card 事件
    # 这样前端在文本流结束后可以立即渲染确认卡片，用户点击后走 /confirmations/*/confirm 端点
    if final_state:
        tool_outputs = final_state.get("tool_outputs") or []
        for tool_output in tool_outputs:
            if not isinstance(tool_output, dict):
                continue
            if tool_output.get("requires_confirmation") and tool_output.get("data"):
                yield {
                    "type": "confirmation_card",
                    "data": tool_output["data"],
                }

    logger.info(f"流式推理完成: session_id={session_id}")


async def get_final_state(
    user_id: UUID,
    session_id: str,
    message: str,
    pet_id: Optional[UUID] = None,
    message_type: str = "text",
    input_url: Optional[str] = None,
    history: Optional[List[AIMessage]] = None,
) -> AgentState:
    """
    获取完整的最终状态，用于调试或自定义处理。

    Args:
        同 run_agent

    Returns:
        最终 AgentState
    """
    initial_state = await create_initial_state(
        user_id=user_id,
        session_id=session_id,
        current_input=message,
        pet_id=pet_id,
        input_type=message_type,
        input_url=input_url,
        messages=history,
        stream_callback=None,
    )

    final_state = await agent_graph.ainvoke(initial_state)  # type: ignore[attr-defined]
    return final_state
