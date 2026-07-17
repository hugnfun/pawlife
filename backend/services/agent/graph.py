"""
LangGraph 工作流组装（包含新用户建档引导）。

完整工作流结构：
入口 → check_onboarding_status → (判断) → classify_intent → ...
                     ↓
               (无宠物) → start_onboarding_prompt → END (输出第一个问题)
用户回答 → 进入流程 → process_onboarding_step → (循环收集) → finalize_onboarding → END

完成后走正常对话流程：
用户输入 → classify_intent → (意图判断) → generate_response → END
                     ↓
              handle_log_meal → generate_response → END
"""

from langgraph.graph import END, StateGraph

from .nodes import (
    check_onboarding_completed,
    check_onboarding_status,
    check_pending_confirmation,
    classify_intent,
    finalize_onboarding,
    generate_response,
    handle_error,
    handle_get_pet_profile,
    handle_log_meal,
    handle_update_pet_profile,
    process_onboarding_step,
    process_pending_confirmation,
    route_by_intent,
    should_process_pending,
    should_start_onboarding,
    start_onboarding_prompt,
)
from .state import AgentState

# 全局缓存编译好的图
_agent_graph: StateGraph = None


def create_agent_graph() -> StateGraph:
    """
    创建 Agent 工作流图（包含新用户建档引导）。

    工作流结构：
    1. check_onboarding_status: 检查用户是否需要建档引导
    2. 条件路由:
       - 需要引导 → 根据引导状态进入对应节点
       - 不需要 → classify_intent 正常意图分类
    3. 建档引导多轮状态机：
       start_onboarding_prompt → (用户回答) → process_onboarding_step → 循环直到所有字段收集完成 → finalize_onboarding → END
    4. 正常对话流程：
       classify_intent: 对用户输入进行意图分类（chit_chat / log_meal）
       条件路由 → 根据意图选择下一个节点 → generate_response → END

    Returns:
        编译好的 StateGraph 实例
    """
    # 创建图，使用 AgentState 作为状态类型
    workflow = StateGraph(AgentState)

    # 添加所有节点
    # Onboarding 引导节点
    workflow.add_node("check_onboarding_status", check_onboarding_status)
    workflow.add_node("check_pending_confirmation", check_pending_confirmation)
    workflow.add_node("process_pending_confirmation", process_pending_confirmation)
    workflow.add_node("start_onboarding_prompt", start_onboarding_prompt)
    workflow.add_node("process_onboarding_step", process_onboarding_step)
    workflow.add_node("finalize_onboarding", finalize_onboarding)
    # 正常对话节点
    workflow.add_node("classify_intent", classify_intent)
    workflow.add_node("handle_log_meal", handle_log_meal)
    workflow.add_node("handle_get_pet_profile", handle_get_pet_profile)
    workflow.add_node("handle_update_pet_profile", handle_update_pet_profile)
    workflow.add_node("generate_response", generate_response)
    workflow.add_node("handle_error", handle_error)

    # 设置入口点 - 从检查建档状态开始
    workflow.set_entry_point("check_onboarding_status")

    # 第一步：检查建档状态后，检查是否有待确认操作
    workflow.add_conditional_edges(
        "check_onboarding_status",
        should_start_onboarding,
        {
            "start_onboarding": "start_onboarding_prompt",
            "process_onboarding": "process_onboarding_step",
            "classify_intent": "check_pending_confirmation",
            "handle_error": "handle_error",
        }
    )

    # 第二步：检查是否有需要用户确认的操作
    workflow.add_conditional_edges(
        "check_pending_confirmation",
        should_process_pending,
        {
            "process_pending": "process_pending_confirmation",
            "classify_intent": "classify_intent",
        }
    )

    # 开始引导 - 输出第一个问题后直接结束（等待用户下一次输入）
    workflow.add_edge("start_onboarding_prompt", END)

    # 处理引导步骤后检查是否完成
    workflow.add_conditional_edges(
        "process_onboarding_step",
        check_onboarding_completed,
        {
            "finalize_onboarding": "finalize_onboarding",
            "continue": "process_onboarding_step",
            "classify_intent": "classify_intent",
            "handle_error": "handle_error",
        }
    )

    # 完成建档后结束
    workflow.add_edge("finalize_onboarding", END)

    # 处理待确认完成后到 generate_response
    workflow.add_edge("process_pending_confirmation", "generate_response")

    # ========== 正常对话流程 ==========
    # 添加条件边：根据意图选择下一个节点
    workflow.add_conditional_edges(
        "classify_intent",
        route_by_intent,
        {
            "chit_chat": "generate_response",
            "log_meal": "handle_log_meal",
            "get_pet_profile": "handle_get_pet_profile",
            "update_pet_profile": "handle_update_pet_profile",
            "handle_error": "handle_error",
        }
    )

    # 处理完成后都到 generate_response 生成最终回复
    workflow.add_edge("handle_log_meal", "generate_response")
    workflow.add_edge("handle_get_pet_profile", "generate_response")
    workflow.add_edge("handle_update_pet_profile", "generate_response")

    # handle_error 完成后到 END
    workflow.add_edge("handle_error", END)

    # generate_response 完成后到 END
    workflow.add_edge("generate_response", END)

    # 编译图
    return workflow.compile()


def get_agent_graph() -> StateGraph:
    """
    获取单例的 Agent 工作流图。

    全局缓存，避免重复创建。

    Returns:
        编译好的 Agent 图
    """
    global _agent_graph
    if _agent_graph is None:
        _agent_graph = create_agent_graph()
    return _agent_graph
