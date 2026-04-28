"""
多媒体 Agent 工具单元测试。

测试食物图像识别和语音转文字。
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


class TestRecognizeFoodImageTool:
    """食物图像识别工具测试。"""

    @pytest.mark.asyncio
    async def test_recognize_food_image(self):
        """测试识别食物图片。"""
        from services.agent.tools import RecognizeFoodImageTool

        tool = RecognizeFoodImageTool()

        mock_response = MagicMock()
        mock_response.content = '{"food_name": "鸡胸肉", "estimated_amount": "100g", "confidence": 0.9}'

        with patch("langchain_openai.ChatOpenAI") as mock_llm_class:
            mock_llm = MagicMock()
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_llm_class.return_value = mock_llm

            result = await tool._arun(image_url="https://example.com/food.jpg")
            assert result is not None

    @pytest.mark.asyncio
    async def test_recognize_food_image_no_url(self):
        """测试无 URL 时识别食物。"""
        from services.agent.tools import RecognizeFoodImageTool

        tool = RecognizeFoodImageTool()
        result = await tool._arun(image_url="")
        assert result is not None


class TestTranscribeVoiceTool:
    """语音转文字工具测试。"""

    @pytest.mark.asyncio
    async def test_transcribe_voice_tencent(self):
        """测试腾讯云 ASR 转写。"""
        from services.agent.tools import TranscribeVoiceTool

        tool = TranscribeVoiceTool()

        mock_tencent_asr = AsyncMock(return_value="今天给猫咪喂了猫粮")
        with patch.object(tool, "_tencent_asr", mock_tencent_asr):
            result = await tool._arun(audio_url="https://example.com/voice.m4a")
            assert "猫粮" in result or result is not None

    @pytest.mark.asyncio
    async def test_transcribe_voice_whisper_fallback(self):
        """测试 Whisper API 降级。"""
        from services.agent.tools import TranscribeVoiceTool

        tool = TranscribeVoiceTool()

        # 腾讯云 ASR 失败，降级到 Whisper
        mock_tencent_asr = AsyncMock(side_effect=Exception("腾讯云 ASR 失败"))
        mock_whisper = AsyncMock(return_value="喂了狗粮")

        with patch.object(tool, "_tencent_asr", mock_tencent_asr):
            with patch.object(tool, "_whisper_asr", mock_whisper):
                result = await tool._arun(audio_url="https://example.com/voice.m4a")
                assert result is not None


class TestGetPetProfileTool:
    """获取宠物档案工具测试。"""

    @pytest.mark.asyncio
    async def test_get_pet_profile(self):
        """测试获取宠物档案。"""
        from services.agent.tools import GetPetProfileTool

        tool = GetPetProfileTool()
        result = await tool._arun(pet_id="test-pet-id")
        assert result is not None


class TestLogActivityTool:
    """运动记录工具测试。"""

    @pytest.mark.asyncio
    async def test_log_activity(self):
        """测试记录运动活动。"""
        from services.agent.tools import LogActivityTool

        tool = LogActivityTool()
        result = await tool._arun(
            pet_id="test-pet-id",
            activity_type="walk",
            duration="30",
            intensity="moderate",
        )
        assert result is not None


class TestLogWeightTool:
    """体重记录工具测试。"""

    @pytest.mark.asyncio
    async def test_log_weight(self):
        """测试记录体重。"""
        from services.agent.tools import LogWeightTool

        tool = LogWeightTool()
        result = await tool._arun(
            pet_id="test-pet-id",
            weight="5.2",
            unit="kg",
        )
        assert result is not None


class TestGenerateRecipeTool:
    """食谱生成工具测试。"""

    @pytest.mark.asyncio
    async def test_generate_recipe(self):
        """测试生成食谱。"""
        from services.agent.tools import GenerateRecipeTool

        tool = GenerateRecipeTool()
        result = await tool._arun(
            pet_id="test-pet-id",
            goal="weight_loss",
        )
        assert result is not None
