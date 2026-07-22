"""紧急意图守卫 + 免责声明测试（requirements-v1.1.md §4）。

覆盖：
1. 高风险关键词命中检测（§4.2）
2. emergency_intent_guard 节点行为
3. should_bypass_for_emergency 路由
4. _append_disclaimer_if_needed 后置拼接
5. 正常输入不误触发紧急分支
"""

import pytest

from services.agent.nodes import (
    DISCLAIMER_TEXT,
    EMERGENCY_RESPONSE_TEMPLATE,
    _append_disclaimer_if_needed,
    detect_emergency_intent,
    emergency_intent_guard,
    should_bypass_for_emergency,
)


# ==================== §4.2 高风险关键词命中检测 ====================

class TestDetectEmergencyIntent:
    """测试高风险关键词匹配。"""

    @pytest.mark.parametrize("user_input,expected_category", [
        # 中毒
        ("我家狗吃了巧克力", "poisoning"),
        ("猫吃了洋葱", "poisoning"),
        ("误食了葡萄", "poisoning"),
        ("舔了老鼠药", "poisoning"),
        ("口吐白沫", "poisoning"),
        # 外伤
        ("狗被车撞了在流血", "trauma"),
        ("骨折了", "trauma"),
        ("从高处摔下来", "trauma"),
        ("瘸腿了", "trauma"),
        # 呼吸/循环
        ("呼吸困难", "respiratory"),
        ("气喘吁吁", "respiratory"),
        ("昏迷不醒", "respiratory"),
        ("抽搐", "respiratory"),
        # 消化急症
        ("持续呕吐", "digestive"),
        ("便血了", "digestive"),
        ("腹胀发硬", "digestive"),
        ("吞了异物", "digestive"),
        # 其他
        ("高烧不退", "other"),
        ("体温异常", "other"),
        ("痉挛", "other"),
    ])
    def test_high_risk_keywords_hit(self, user_input, expected_category):
        """各种高风险关键词都能被正确分类。"""
        result = detect_emergency_intent(user_input)
        assert result == expected_category, f"输入 '{user_input}' 应命中 {expected_category}，实际 {result}"

    @pytest.mark.parametrize("user_input", [
        "今天天气不错",
        "我家狗狗叫旺财",
        "记录一下早餐吃了100g狗粮",
        "它现在体重多少",
        "帮我推荐一个减肥食谱",
        "你好",
        "",
    ])
    def test_normal_input_no_hit(self, user_input):
        """正常输入不触发紧急分支。"""
        assert detect_emergency_intent(user_input) is None


# ==================== emergency_intent_guard 节点 ====================

class TestEmergencyIntentGuard:
    """测试紧急意图守卫节点行为。"""

    @pytest.mark.asyncio
    async def test_emergency_triggered_on_poisoning(self):
        """中毒场景触发紧急分支。"""
        state = {
            "current_input": "我家狗吃了巧克力，怎么办？",
            "user_id": "test-user",
        }
        result = await emergency_intent_guard(state)

        assert result["emergency_triggered"] is True
        assert result["emergency_category"] == "poisoning"
        assert result["intent"] == "emergency"
        assert result["response_content"] == EMERGENCY_RESPONSE_TEMPLATE

    @pytest.mark.asyncio
    async def test_no_emergency_on_normal_input(self):
        """正常输入不触发紧急分支。"""
        state = {
            "current_input": "今天天气怎么样？",
            "user_id": "test-user",
        }
        result = await emergency_intent_guard(state)

        assert result["emergency_triggered"] is False
        assert result["emergency_category"] is None
        assert "response_content" not in result
        assert "intent" not in result

    @pytest.mark.asyncio
    async def test_emergency_response_time(self):
        """紧急场景响应时间 < 1.5s（§4.4 验收标准）。"""
        import time
        state = {
            "current_input": "狗吃了葡萄，吐白沫了",
            "user_id": "test-user",
        }
        t0 = time.perf_counter()
        await emergency_intent_guard(state)
        elapsed = time.perf_counter() - t0
        # 纯关键词匹配，应该 < 100ms，远低于 1.5s 要求
        assert elapsed < 1.5, f"紧急场景响应时间 {elapsed:.3f}s 超过 1.5s 限制"


# ==================== should_bypass_for_emergency 路由 ====================

class TestShouldBypassForEmergency:
    """测试紧急路由逻辑。"""

    def test_bypass_when_emergency_triggered(self):
        """紧急触发时跳过 classify_intent。"""
        state = {"emergency_triggered": True}
        assert should_bypass_for_emergency(state) == "generate_response"

    def test_no_bypass_when_not_triggered(self):
        """非紧急时走正常 classify_intent。"""
        state = {"emergency_triggered": False}
        assert should_bypass_for_emergency(state) == "classify_intent"


# ==================== _append_disclaimer_if_needed 后置拼接 ====================

class TestAppendDisclaimer:
    """测试免责声明后置拼接（§4.1）。"""

    def test_disclaimer_appended_on_emergency(self):
        """紧急意图必须拼接免责声明。"""
        state = {
            "emergency_triggered": True,
            "current_input": "狗吃了巧克力",
            "intent": "emergency",
        }
        response = "这是 AI 的回复"
        result = _append_disclaimer_if_needed(response, state)
        assert DISCLAIMER_TEXT in result
        assert result.endswith(DISCLAIMER_TEXT)

    def test_disclaimer_appended_on_health_query(self):
        """健康相关查询拼接免责声明。"""
        state = {
            "emergency_triggered": False,
            "current_input": "我家狗拉肚子了怎么办",
            "intent": "chit_chat",
        }
        response = "建议观察一下..."
        result = _append_disclaimer_if_needed(response, state)
        assert DISCLAIMER_TEXT in result

    def test_disclaimer_appended_on_recipe_tool(self):
        """食谱工具调用拼接免责声明。"""
        state = {
            "emergency_triggered": False,
            "current_input": "帮我推荐食谱",
            "intent": "chit_chat",
            "tool_outputs": [
                {"tool_name": "generate_recipe", "success": True},
            ],
        }
        response = "这是推荐食谱..."
        result = _append_disclaimer_if_needed(response, state)
        assert DISCLAIMER_TEXT in result

    def test_no_disclaimer_on_normal_chitchat(self):
        """普通闲聊不拼接免责声明。"""
        state = {
            "emergency_triggered": False,
            "current_input": "你好",
            "intent": "chit_chat",
        }
        response = "你好呀！"
        result = _append_disclaimer_if_needed(response, state)
        assert DISCLAIMER_TEXT not in result

    def test_no_disclaimer_on_log_meal(self):
        """记录饮食不拼接免责声明。"""
        state = {
            "emergency_triggered": False,
            "current_input": "记录一下早餐吃了100g狗粮",
            "intent": "log_meal",
            "tool_outputs": [
                {"tool_name": "log_meal", "success": True},
            ],
        }
        response = "已记录饮食"
        result = _append_disclaimer_if_needed(response, state)
        assert DISCLAIMER_TEXT not in result


# ==================== §4.4 验收标准 ====================

class TestAcceptanceCriteria:
    """§4.4 验收标准测试。"""

    @pytest.mark.parametrize("user_input", [
        "巧克力", "洋葱", "葡萄", "木糖醇", "老鼠药", "吐白沫", "抽搐",
        "出血", "骨折", "被撞", "瘸腿",
        "呼吸困难", "气喘", "昏迷",
        "持续呕吐", "血便", "异物吞食",
        "高烧", "痉挛", "体温异常",
    ])
    def test_high_risk_keyword_trigger_rate_100(self, user_input):
        """§4.4: 高风险意图测试用例集下，固定文案触发率 = 100%。"""
        category = detect_emergency_intent(user_input)
        assert category is not None, f"关键词 '{user_input}' 未触发紧急分支"

    def test_disclaimer_text_is_fixed(self):
        """§4.1: 免责声明是固定文案，不由 LLM 自由生成。"""
        # 确保固定文案包含关键内容
        assert "不能替代兽医诊断" in DISCLAIMER_TEXT
        assert "及时就医" in DISCLAIMER_TEXT
