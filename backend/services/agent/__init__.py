"""
AI Agent 模块。

基于 LangGraph 构建的有状态 AI Agent 编排层。
遵循 CLAUDE.md 中的架构设计：
- 意图识别 → 上下文注入 → 工具调用 → 结果整合 → 流式回复
"""

from .graph import create_agent_graph, get_agent_graph
from .nodes import (
    classify_intent,
    generate_response,
    handle_error,
    handle_get_pet_profile,
    handle_log_meal,
    handle_update_pet_profile,
    route_by_intent,
)
from .runner import (
    get_final_state,
    run_agent,
    run_agent_streaming,
)
from .state import AgentState, create_initial_state
from .tools import TOOL_REGISTRY, get_all_tools

__all__ = [
    # 状态
    "AgentState",
    "create_initial_state",
    # 图
    "create_agent_graph",
    "get_agent_graph",
    # 节点
    "classify_intent",
    "route_by_intent",
    "handle_log_meal",
    "handle_get_pet_profile",
    "handle_update_pet_profile",
    "generate_response",
    "handle_error",
    # 运行入口
    "run_agent",
    "run_agent_streaming",
    "get_final_state",
    # 工具
    "get_all_tools",
    "TOOL_REGISTRY",
]
