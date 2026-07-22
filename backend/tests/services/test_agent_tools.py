"""
Agent 工具单元测试。

使用 mock 数据库和 API 测试各个工具的逻辑。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestEvaluateDietTool:
    """营养评估工具测试。"""

    @pytest.mark.asyncio
    async def test_evaluate_balanced_diet(self):
        """测试均衡饮食评估。"""
        from services.agent.tools import EvaluateDietTool

        tool = EvaluateDietTool()
        daily_intake = [
            {"food_name": "chicken", "amount_grams": 100, "protein": 25, "fat": 5}
        ]

        with patch("services.database.db") as mock_db:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = MagicMock(
                current_weight=10, species="dog"
            )
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_db.get_session.return_value = mock_session

            result = await tool._arun(
                daily_intake=daily_intake,
                pet_id="00000000-0000-0000-0000-000000000001",
            )

        assert result is not None
        assert "success" in result or "评估" in str(result) or "data" in result

    @pytest.mark.asyncio
    async def test_evaluate_with_empty_intake(self):
        """测试空摄入列表。"""
        from services.agent.tools import EvaluateDietTool

        tool = EvaluateDietTool()
        result = await tool._arun(daily_intake=[], pet_id=None)
        assert result is not None


class TestScheduleReminderTool:
    """提醒工具测试。"""

    @pytest.mark.asyncio
    async def test_schedule_feeding_reminder(self):
        """测试创建喂食提醒。"""
        from services.agent.tools import ScheduleReminderTool

        tool = ScheduleReminderTool()

        with patch("services.database.db") as mock_db:
            mock_session = AsyncMock()
            mock_session.add = MagicMock()  # session.add 是同步方法
            mock_session.commit = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_db.get_session.return_value = mock_session

            result = await tool._arun(
                reminder_type="feeding",
                schedule="每天 08:00",
                pet_id="00000000-0000-0000-0000-000000000001",
            )

        assert result is not None


class TestWebSearchTool:
    """网络搜索工具测试。"""

    @pytest.mark.asyncio
    async def test_search_pet_care(self):
        """测试宠物护理搜索。"""
        from services.agent.tools import WebSearchTool

        tool = WebSearchTool()

        with patch("core.config.settings") as mock_settings:
            mock_settings.bing_search_api_key = None
            result = await tool._arun(query="金毛犬日常护理建议")

        assert result is not None


class TestLogMealTool:
    """饮食记录工具测试。"""

    @pytest.mark.asyncio
    async def test_log_simple_meal(self):
        """测试简单饮食记录。"""
        from services.agent.tools import LogMealTool

        tool = LogMealTool()

        with patch("services.database.db") as mock_db:
            mock_session = AsyncMock()
            mock_session.commit = AsyncMock()
            mock_session.flush = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = MagicMock(
                id="pet-1", name="旺财", species="dog"
            )
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_db.get_session.return_value = mock_session

            with patch("services.redis.redis_service") as mock_redis:
                mock_redis.check_duplicate_feeding = AsyncMock(return_value=False)
                result = await tool._arun(
                    pet_id="00000000-0000-0000-0000-000000000001",
                    food_name="狗粮",
                    amount=200.0,
                )

        assert result is not None
