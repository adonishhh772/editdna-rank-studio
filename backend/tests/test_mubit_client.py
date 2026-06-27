from unittest.mock import MagicMock, patch

import pytest

from app.integrations.mubit_client import MubitMemoryClient


@pytest.fixture
def mock_mubit_client() -> MagicMock:
    with patch("app.integrations.mubit_client.Client") as client_cls:
        mock_client = MagicMock()
        mock_client.recall.return_value = {
            "final_answer": "prefers fast cuts",
            "evidence": [],
        }
        mock_client.get_context.return_value = {
            "section_summaries": [],
            "context_block": "",
        }
        client_cls.return_value = mock_client
        with patch("app.integrations.mubit_client.get_settings") as settings_mock:
            settings = MagicMock()
            settings.mubit_api_key = "test-key"
            settings.mubit_endpoint = "https://api.mubit.ai"
            settings.mubit_transport = "http"
            settings_mock.return_value = settings
            yield mock_client


@pytest.mark.asyncio
async def test_recall_context_uses_protobuf_enum_values(mock_mubit_client: MagicMock) -> None:
    client = MubitMemoryClient(run_id="run_123")
    result = await client.recall_context(
        user_id="user_1",
        project_id="proj_1",
        topic="AI tools",
        video_type="ranking_video",
    )

    mock_mubit_client.recall.assert_called_once_with(
        session_id="proj_1",
        user_id="user_1",
        query="User preferences for ranking_video about AI tools. Editing style, pacing, captions, audio.",
        entry_types=["fact", "lesson", "rule"],
        mode=MubitMemoryClient.QUERY_MODE_AGENT_ROUTED,
        direct_lane=MubitMemoryClient.DIRECT_QUERY_LANE_SEMANTIC_SEARCH,
    )
    assert result["final_answer"] == "prefers fast cuts"
