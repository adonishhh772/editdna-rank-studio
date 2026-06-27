from app.agents.workflow.stream_events import (
    blackboard_activity_signature,
    build_stream_snapshot,
    find_running_trace,
    node_display_label,
)
from app.blackboard import ProjectBlackboard
from app.schemas import AgentTrace


def test_node_display_label_maps_reference_analyst() -> None:
    assert node_display_label("reference_analyst") == "Analyzing reference video"


def test_find_running_trace_returns_latest_running() -> None:
    board = ProjectBlackboard(
        project_id="proj_1",
        run_id="run_1",
        user_id="user_1",
        traces=[
            AgentTrace(
                trace_id="trace_1",
                project_id="proj_1",
                run_id="run_1",
                agent_id="validate_gemini",
                agent_name="Validate Gemini",
                status="complete",
            ),
            AgentTrace(
                trace_id="trace_2",
                project_id="proj_1",
                run_id="run_1",
                agent_id="reference_analyst",
                agent_name="Gemini Reference Analyst",
                status="running",
            ),
        ],
    )
    running = find_running_trace(board)
    assert running is not None
    assert running["agent_id"] == "reference_analyst"


def test_build_stream_snapshot_includes_active_reasoning() -> None:
    board = ProjectBlackboard(
        project_id="proj_1",
        run_id="run_1",
        user_id="user_1",
        traces=[
            AgentTrace(
                trace_id="trace_1",
                project_id="proj_1",
                run_id="run_1",
                agent_id="reference_analyst",
                agent_name="Gemini Reference Analyst",
                status="running",
                visible_reasoning="Studying hook pacing and rank transitions in the reference clip.",
            ),
        ],
    )
    snapshot = build_stream_snapshot(board, "progress", "analyse_reference", "reference_analyst")
    assert snapshot["type"] == "progress"
    assert snapshot["node_label"] == "Analyzing reference video"
    assert snapshot["active_reasoning"] == (
        "Studying hook pacing and rank transitions in the reference clip."
    )
    assert len(snapshot["traces"]) == 1


def test_blackboard_activity_signature_changes_with_trace_status() -> None:
    board = ProjectBlackboard(project_id="proj_1", run_id="run_1", user_id="user_1")
    initial_signature = blackboard_activity_signature(board)
    board.traces.append(
        AgentTrace(
            trace_id="trace_1",
            project_id="proj_1",
            run_id="run_1",
            agent_id="reference_analyst",
            agent_name="Gemini Reference Analyst",
            status="running",
        )
    )
    updated_signature = blackboard_activity_signature(board)
    assert initial_signature != updated_signature


def test_blackboard_activity_signature_changes_with_memory_updates() -> None:
    board = ProjectBlackboard(project_id="proj_1", run_id="run_1", user_id="user_1")
    initial_signature = blackboard_activity_signature(board)
    board.memory_updates.append(
        {
            "summary": "Stored reference blueprint style memory (5 ranks)",
            "episodic_updates": [{"content": "Reference ranking video uses 5 ranks"}],
            "long_term_updates": [{"content": "User prefers ranking videos with countdown hooks"}],
        }
    )
    updated_signature = blackboard_activity_signature(board)
    assert initial_signature != updated_signature


def test_build_stream_snapshot_includes_memory_updates() -> None:
    board = ProjectBlackboard(project_id="proj_1", run_id="run_1", user_id="user_1")
    board.memory_updates.append(
        {
            "summary": "Stored reference blueprint style memory (5 ranks)",
            "episodic_updates": [{"content": "Reference ranking video uses 5 ranks"}],
            "long_term_updates": [{"content": "User prefers ranking videos with countdown hooks"}],
        }
    )
    board.memory_context["reference_blueprint_memory"] = {"summary": "Stored reference blueprint style memory (5 ranks)"}

    snapshot = build_stream_snapshot(board, "progress", "analyse_reference", "reference_blueprint_memory")

    assert len(snapshot["memory_updates"]) == 1
    assert snapshot["memory_context"]["reference_blueprint_memory"]["summary"].startswith("Stored reference blueprint")
    assert snapshot["node_label"] == "Writing reference DNA to memory"
