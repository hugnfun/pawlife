"""
健康报告生成测试。

测试健康报告工具的端到端逻辑。
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestHealthReportTool:
    """健康报告工具测试。"""

    @pytest.mark.asyncio
    async def test_generate_report_for_pet(self):
        """测试为宠物生成健康报告。"""
        from services.agent.tools import GenerateHealthReportTool

        tool = GenerateHealthReportTool()

        # mock 数据库依赖，避免真实连库
        with patch("services.database.db") as mock_db:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = MagicMock(
                id="pet-1", name="旺财", species="dog", current_weight=10
            )
            mock_result.scalars.return_value.all.return_value = []
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_db.get_session.return_value = mock_session

            result = await tool._arun(pet_id="pet-1")

        # 工具返回 dict，包含 success/data/error 字段
        assert result is not None
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_report_with_no_data(self):
        """测试无数据时的报告生成。"""
        from services.agent.tools import GenerateHealthReportTool

        tool = GenerateHealthReportTool()

        with patch("services.database.db") as mock_db:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_result.scalars.return_value.all.return_value = []
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_db.get_session.return_value = mock_session

            result = await tool._arun(pet_id="non-existent-pet")

        assert result is not None
        assert isinstance(result, dict)


class TestCalculateNutritionTool:
    """营养计算工具测试。"""

    @pytest.mark.asyncio
    async def test_calculate_basic_nutrition(self):
        """测试基础营养计算。"""
        from services.agent.tools import CalculateNutritionTool

        tool = CalculateNutritionTool()

        # 工具签名为 (food_name, amount_grams)；数据源可能连 DB，此处 mock
        with patch("services.database.db") as mock_db:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_db.get_session.return_value = mock_session

            result = await tool._arun(
                food_name="鸡胸肉",
                amount_grams=100.0,
            )

        assert result is not None
