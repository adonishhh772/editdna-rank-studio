from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agents.workflow import nodes
from app.agents.workflow.state import WorkflowState
from app.constants.harness import HARNESS_ROUTE_CONTINUE, HARNESS_ROUTE_RETRY
from app.constants.workflow import (
    HUMAN_INTERRUPT_NODES,
    NODE_BUILD_EDIT_PLAN,
    NODE_CANDIDATE_ANALYSIS,
    NODE_CANDIDATE_APPROVAL_GATE,
    NODE_CANDIDATE_DISCOVERY,
    NODE_COMPARISON,
    NODE_CRITIC,
    NODE_EDIT_PLAN_APPROVAL_GATE,
    NODE_FEEDBACK_MEMORY,
    NODE_FUSION,
    NODE_MEMORY_RECALL,
    NODE_MOE_PIPELINE,
    NODE_PLATFORM_VIDEO_DOWNLOAD_APPROVED,
    NODE_PLATFORM_VIDEO_DOWNLOAD_POOL,
    NODE_PLATFORM_VIDEO_SEARCH,
    NODE_PREPARE_HARNESS_RETRY,
    NODE_PREPARE_REGENERATE,
    NODE_RANKING,
    NODE_REFERENCE_ANALYST,
    NODE_RENDER,
    NODE_SLNG_AUDIO,
    NODE_TAVILY_RESEARCH,
    NODE_TOPIC,
    STAGE_ANALYSE_REFERENCE,
    STAGE_COMPARE,
    STAGE_CREATE_EDIT_PLAN,
    STAGE_DISCOVER_CANDIDATES,
    STAGE_FEEDBACK,
    STAGE_REGENERATE,
    STAGE_RENDER,
    STAGE_RESEARCH_TOPIC,
    STAGE_SELECT_RANKING,
)

NODE_VALIDATE_GEMINI = "validate_gemini"
NODE_VALIDATE_TAVILY = "validate_tavily"
NODE_VALIDATE_CANDIDATES = "validate_candidates"
NODE_FINALIZE_EDIT_PLAN = "finalize_edit_plan"


def _build_linear_graph(
    stage_name: str,
    node_specs: list[tuple[str, object]],
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    graph_builder = StateGraph(WorkflowState)

    for node_name, node_fn in node_specs:
        graph_builder.add_node(node_name, node_fn)

    first_node = node_specs[0][0]
    graph_builder.add_edge(START, first_node)

    for index in range(len(node_specs) - 1):
        graph_builder.add_edge(node_specs[index][0], node_specs[index + 1][0])

    graph_builder.add_edge(node_specs[-1][0], END)

    return graph_builder.compile(
        checkpointer=checkpointer,
        name=stage_name,
    )


def _build_edit_plan_graph(
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    graph_builder = StateGraph(WorkflowState)

    edit_plan_node_specs: list[tuple[str, object]] = [
        (NODE_VALIDATE_CANDIDATES, nodes.validate_candidates_node),
        (NODE_MOE_PIPELINE, nodes.moe_pipeline_node),
        (NODE_FUSION, nodes.fusion_node),
        (NODE_BUILD_EDIT_PLAN, nodes.build_edit_plan_node),
        (NODE_SLNG_AUDIO, nodes.slng_audio_node),
        (NODE_CRITIC, nodes.critic_node),
        (NODE_PREPARE_HARNESS_RETRY, nodes.prepare_harness_retry_node),
        (NODE_EDIT_PLAN_APPROVAL_GATE, nodes.edit_plan_approval_gate_node),
        (NODE_FINALIZE_EDIT_PLAN, nodes.finalize_edit_plan_node),
    ]

    for node_name, node_fn in edit_plan_node_specs:
        graph_builder.add_node(node_name, node_fn)

    graph_builder.add_edge(START, NODE_VALIDATE_CANDIDATES)
    graph_builder.add_edge(NODE_VALIDATE_CANDIDATES, NODE_MOE_PIPELINE)
    graph_builder.add_edge(NODE_MOE_PIPELINE, NODE_FUSION)
    graph_builder.add_edge(NODE_FUSION, NODE_BUILD_EDIT_PLAN)
    graph_builder.add_edge(NODE_BUILD_EDIT_PLAN, NODE_SLNG_AUDIO)
    graph_builder.add_edge(NODE_SLNG_AUDIO, NODE_CRITIC)
    graph_builder.add_conditional_edges(
        NODE_CRITIC,
        nodes.route_after_critic,
        {
            HARNESS_ROUTE_RETRY: NODE_PREPARE_HARNESS_RETRY,
            HARNESS_ROUTE_CONTINUE: NODE_EDIT_PLAN_APPROVAL_GATE,
        },
    )
    graph_builder.add_edge(NODE_PREPARE_HARNESS_RETRY, NODE_MOE_PIPELINE)
    graph_builder.add_edge(NODE_EDIT_PLAN_APPROVAL_GATE, NODE_FINALIZE_EDIT_PLAN)
    graph_builder.add_edge(NODE_FINALIZE_EDIT_PLAN, END)

    return graph_builder.compile(
        checkpointer=checkpointer,
        interrupt_after=[NODE_EDIT_PLAN_APPROVAL_GATE],
        name=STAGE_CREATE_EDIT_PLAN,
    )


def _build_regenerate_graph(
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    graph_builder = StateGraph(WorkflowState)

    regenerate_node_specs: list[tuple[str, object]] = [
        (NODE_PREPARE_REGENERATE, nodes.prepare_regenerate_node),
        (NODE_VALIDATE_CANDIDATES, nodes.validate_candidates_node),
        (NODE_MOE_PIPELINE, nodes.moe_pipeline_node),
        (NODE_FUSION, nodes.fusion_node),
        (NODE_BUILD_EDIT_PLAN, nodes.build_edit_plan_node),
        (NODE_SLNG_AUDIO, nodes.slng_audio_node),
        (NODE_CRITIC, nodes.critic_node),
        (NODE_PREPARE_HARNESS_RETRY, nodes.prepare_harness_retry_node),
        (NODE_EDIT_PLAN_APPROVAL_GATE, nodes.edit_plan_approval_gate_node),
        (NODE_FINALIZE_EDIT_PLAN, nodes.finalize_edit_plan_node),
        (NODE_RENDER, nodes.render_node),
    ]

    for node_name, node_fn in regenerate_node_specs:
        graph_builder.add_node(node_name, node_fn)

    graph_builder.add_edge(START, NODE_PREPARE_REGENERATE)
    graph_builder.add_edge(NODE_PREPARE_REGENERATE, NODE_VALIDATE_CANDIDATES)
    graph_builder.add_edge(NODE_VALIDATE_CANDIDATES, NODE_MOE_PIPELINE)
    graph_builder.add_edge(NODE_MOE_PIPELINE, NODE_FUSION)
    graph_builder.add_edge(NODE_FUSION, NODE_BUILD_EDIT_PLAN)
    graph_builder.add_edge(NODE_BUILD_EDIT_PLAN, NODE_SLNG_AUDIO)
    graph_builder.add_edge(NODE_SLNG_AUDIO, NODE_CRITIC)
    graph_builder.add_conditional_edges(
        NODE_CRITIC,
        nodes.route_after_critic,
        {
            HARNESS_ROUTE_RETRY: NODE_PREPARE_HARNESS_RETRY,
            HARNESS_ROUTE_CONTINUE: NODE_EDIT_PLAN_APPROVAL_GATE,
        },
    )
    graph_builder.add_edge(NODE_PREPARE_HARNESS_RETRY, NODE_MOE_PIPELINE)
    graph_builder.add_edge(NODE_EDIT_PLAN_APPROVAL_GATE, NODE_FINALIZE_EDIT_PLAN)
    graph_builder.add_edge(NODE_FINALIZE_EDIT_PLAN, NODE_RENDER)
    graph_builder.add_edge(NODE_RENDER, END)

    return graph_builder.compile(
        checkpointer=checkpointer,
        interrupt_after=[NODE_EDIT_PLAN_APPROVAL_GATE],
        name=STAGE_REGENERATE,
    )


def build_stage_graphs(
    checkpointer: BaseCheckpointSaver | None = None,
) -> dict[str, CompiledStateGraph]:
    return {
        STAGE_ANALYSE_REFERENCE: _build_linear_graph(
            STAGE_ANALYSE_REFERENCE,
            [
                (NODE_VALIDATE_GEMINI, nodes.validate_gemini_key_node),
                (NODE_REFERENCE_ANALYST, nodes.reference_analyst_node),
            ],
            checkpointer,
        ),
        STAGE_RESEARCH_TOPIC: _build_linear_graph(
            STAGE_RESEARCH_TOPIC,
            [
                (NODE_VALIDATE_TAVILY, nodes.validate_tavily_key_node),
                (NODE_TOPIC, nodes.topic_node),
                (NODE_MEMORY_RECALL, nodes.memory_recall_node),
                (NODE_TAVILY_RESEARCH, nodes.tavily_research_node),
            ],
            checkpointer,
        ),
        STAGE_DISCOVER_CANDIDATES: _build_linear_graph(
            STAGE_DISCOVER_CANDIDATES,
            [
                (NODE_VALIDATE_GEMINI, nodes.validate_gemini_key_node),
                (NODE_CANDIDATE_DISCOVERY, nodes.candidate_discovery_node),
            ],
            checkpointer,
        ),
        STAGE_SELECT_RANKING: _build_linear_graph(
            STAGE_SELECT_RANKING,
            [
                (NODE_RANKING, nodes.ranking_node),
                (NODE_CANDIDATE_APPROVAL_GATE, nodes.candidate_approval_gate_node),
            ],
            checkpointer,
        ),
        STAGE_CREATE_EDIT_PLAN: _build_edit_plan_graph(checkpointer),
        STAGE_RENDER: _build_linear_graph(
            STAGE_RENDER,
            [(NODE_RENDER, nodes.render_node)],
            checkpointer,
        ),
        STAGE_COMPARE: _build_linear_graph(
            STAGE_COMPARE,
            [(NODE_COMPARISON, nodes.comparison_node)],
            checkpointer,
        ),
        STAGE_FEEDBACK: _build_linear_graph(
            STAGE_FEEDBACK,
            [(NODE_FEEDBACK_MEMORY, nodes.feedback_memory_node)],
            checkpointer,
        ),
        STAGE_REGENERATE: _build_regenerate_graph(checkpointer),
    }


def build_full_pipeline_graph(
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    graph_builder = StateGraph(WorkflowState)

    pipeline_nodes: list[tuple[str, object]] = [
        (NODE_VALIDATE_GEMINI, nodes.validate_gemini_key_node),
        (NODE_REFERENCE_ANALYST, nodes.reference_analyst_node),
        (NODE_VALIDATE_TAVILY, nodes.validate_tavily_key_node),
        (NODE_TOPIC, nodes.topic_node),
        (NODE_MEMORY_RECALL, nodes.memory_recall_node),
        (NODE_TAVILY_RESEARCH, nodes.tavily_research_node),
        (NODE_CANDIDATE_DISCOVERY, nodes.candidate_discovery_node),
        (NODE_CANDIDATE_APPROVAL_GATE, nodes.candidate_approval_gate_node),
        (NODE_VALIDATE_CANDIDATES, nodes.validate_candidates_node),
        (NODE_MOE_PIPELINE, nodes.moe_pipeline_node),
        (NODE_FUSION, nodes.fusion_node),
        (NODE_BUILD_EDIT_PLAN, nodes.build_edit_plan_node),
        (NODE_SLNG_AUDIO, nodes.slng_audio_node),
        (NODE_CRITIC, nodes.critic_node),
        (NODE_PREPARE_HARNESS_RETRY, nodes.prepare_harness_retry_node),
        (NODE_EDIT_PLAN_APPROVAL_GATE, nodes.edit_plan_approval_gate_node),
        (NODE_FINALIZE_EDIT_PLAN, nodes.finalize_edit_plan_node),
        (NODE_RENDER, nodes.render_node),
        (NODE_COMPARISON, nodes.comparison_node),
    ]

    for node_name, node_fn in pipeline_nodes:
        graph_builder.add_node(node_name, node_fn)

    linear_prefix = [
        NODE_VALIDATE_GEMINI,
        NODE_REFERENCE_ANALYST,
        NODE_VALIDATE_TAVILY,
        NODE_TOPIC,
        NODE_MEMORY_RECALL,
        NODE_TAVILY_RESEARCH,
        NODE_CANDIDATE_DISCOVERY,
        NODE_CANDIDATE_APPROVAL_GATE,
        NODE_VALIDATE_CANDIDATES,
        NODE_MOE_PIPELINE,
        NODE_FUSION,
        NODE_BUILD_EDIT_PLAN,
        NODE_SLNG_AUDIO,
        NODE_CRITIC,
    ]

    graph_builder.add_edge(START, linear_prefix[0])
    for index in range(len(linear_prefix) - 1):
        graph_builder.add_edge(linear_prefix[index], linear_prefix[index + 1])

    graph_builder.add_conditional_edges(
        NODE_CRITIC,
        nodes.route_after_critic,
        {
            HARNESS_ROUTE_RETRY: NODE_PREPARE_HARNESS_RETRY,
            HARNESS_ROUTE_CONTINUE: NODE_EDIT_PLAN_APPROVAL_GATE,
        },
    )
    graph_builder.add_edge(NODE_PREPARE_HARNESS_RETRY, NODE_MOE_PIPELINE)
    graph_builder.add_edge(NODE_EDIT_PLAN_APPROVAL_GATE, NODE_FINALIZE_EDIT_PLAN)
    graph_builder.add_edge(NODE_FINALIZE_EDIT_PLAN, NODE_RENDER)
    graph_builder.add_edge(NODE_RENDER, NODE_COMPARISON)
    graph_builder.add_edge(NODE_COMPARISON, END)

    return graph_builder.compile(
        checkpointer=checkpointer,
        interrupt_after=list(HUMAN_INTERRUPT_NODES),
        name="full_pipeline",
    )
