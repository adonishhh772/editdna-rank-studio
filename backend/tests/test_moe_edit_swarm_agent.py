import asyncio
from unittest.mock import AsyncMock, patch

from app.agents.moe_edit_swarm_agent import MoEEditSwarmAgent
from app.db import create_project


def test_moe_edit_swarm_records_swarm_trace():
    board = create_project("test-user", "MoE Swarm Test")
    board.approved_candidates = []

    with patch(
        "app.agents.moe_edit_swarm_agent.MoEBus.run_moe_pipeline",
        new_callable=AsyncMock,
        return_value=board,
    ):
        result = asyncio.run(MoEEditSwarmAgent().execute(board, swarm=True))

    assert result.traces
    parent = result.traces[-1]
    assert parent.agent_id == "moe_edit_swarm"
    assert parent.metadata.get("swarm") is True
    assert "story_agent" in parent.metadata.get("sub_agents", [])
