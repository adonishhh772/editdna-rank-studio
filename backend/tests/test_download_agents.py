from app.agents.platform_video_download_agent import PlatformVideoDownloadAgent
from app.db import create_project, new_id
from app.schemas import AgentTrace


def test_download_event_recorded_on_blackboard():
    blackboard = create_project("test-user", "Download Trace Test")
    agent = PlatformVideoDownloadAgent(target="pool")
    blackboard.traces.append(
        AgentTrace(
            trace_id=new_id("trace"),
            project_id=blackboard.project_id,
            run_id=blackboard.run_id,
            agent_id=agent.agent_id,
            agent_name=agent.agent_name,
            status="running",
        )
    )

    agent.record_download_event(
        blackboard,
        concept="Runway ML",
        stage="download_started",
        candidate_id=new_id("cand"),
        platform="youtube",
        source_url="https://www.youtube.com/watch?v=example",
    )
    agent.record_download_event(
        blackboard,
        concept="Runway ML",
        stage="download_success",
        candidate_id=new_id("cand"),
        platform="youtube",
        local_file_path="/tmp/example.mp4",
        file_size_bytes=123456,
    )

    assert len(blackboard.download_events) == 2
    assert blackboard.download_events[0].stage == "download_started"
    assert blackboard.traces[-1].tool_calls
    assert blackboard.traces[-1].tool_calls[-1]["stage"] == "download_success"


def test_platform_agents_registered():
    from app.agents.platform_video_search_agent import PlatformVideoSearchAgent

    search_agent = PlatformVideoSearchAgent()
    download_agent = PlatformVideoDownloadAgent(target="approved")
    assert search_agent.agent_name == "Video Search"
    assert download_agent.agent_name == "Video Download"
