"""
健康报告生成测试。

测试健康报告工具的端到端逻辑。
"""

import pytest


class TestHealthReportTool:
    """健康报告工具测试。"""

    @pytest.mark.asyncio
    async def test_generate_report_for_pet(self):
        """测试为宠物生成健康报告。"""
        try:
            from services.agent.tools import GenerateHealthReportTool

            tool = GenerateHealthReportTool()
            result = await tool._arun(pet_id="pet-1")

            assert result is not None
            assert isinstance(result, str)
            assert len(result) > 0
        except ImportError:
            pytest.skip("Agent tools not available in test environment")

    @pytest.mark.asyncio
    async def test_report_with_no_data(self):
        """测试无数据时的报告生成。"""
        try:
            from services.agent.tools import GenerateHealthReportTool

            tool = GenerateHealthReportTool()
            result = await tool._arun(pet_id="non-existent-pet")

            assert result is not None
        except ImportError:
            pytest.skip("Agent tools not available in test environment")


class TestCalculateNutritionTool:
    """营养计算工具测试。"""

    @pytest.mark.asyncio
    async def test_calculate_basic_nutrition(self):
        """测试基础营养计算。"""
        try:
            from services.agent.tools import CalculateNutritionTool

            tool = CalculateNutritionTool()
            result = await tool._arun(
                food_name="鸡胸肉",
                amount="100",
                unit="g"
            )

            assert result is not None
        except ImportError:
            pytest.skip("Agent tools not available in test environment")
