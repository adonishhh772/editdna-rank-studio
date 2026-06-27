"use client";

import { useCallback, useMemo, useState } from "react";
import {
  runWorkflowStream,
  type WorkflowAgentMessage,
  type WorkflowDownloadEvent,
  type WorkflowStreamEvent,
  type WorkflowTrace,
} from "@/lib/workflowStream";
import { resolveTraceActivityText } from "@/lib/traceDisplay";

type WorkflowStreamState = {
  traces: WorkflowTrace[];
  downloadEvents: WorkflowDownloadEvent[];
  agentMessages: WorkflowAgentMessage[];
  activeNodeLabel: string | null;
  activeReasoning: string | null;
  memoryContext: Record<string, unknown>;
  memoryUpdates: Array<Record<string, unknown>>;
  learningPreferences: Record<string, unknown>;
  isRunning: boolean;
};

const INITIAL_STATE: WorkflowStreamState = {
  traces: [],
  downloadEvents: [],
  agentMessages: [],
  activeNodeLabel: null,
  activeReasoning: null,
  memoryContext: {},
  memoryUpdates: [],
  learningPreferences: {},
  isRunning: false,
};

function resolveActiveReasoning(event: WorkflowStreamEvent): string | null {
  if (event.active_reasoning?.trim()) {
    return event.active_reasoning.trim();
  }
  if (event.running_trace) {
    const reasoning = resolveTraceActivityText(event.running_trace);
    return reasoning === "Working..." ? null : reasoning;
  }
  return null;
}

function applyStreamEvent(
  state: WorkflowStreamState,
  event: WorkflowStreamEvent,
): WorkflowStreamState {
  const nextState: WorkflowStreamState = { ...state };

  if (event.traces) {
    nextState.traces = event.traces;
  }
  if (event.download_events) {
    nextState.downloadEvents = event.download_events;
  }
  if (event.agent_messages) {
    nextState.agentMessages = event.agent_messages;
  }
  if (event.memory_context) {
    nextState.memoryContext = event.memory_context;
  }
  if (event.memory_updates) {
    nextState.memoryUpdates = event.memory_updates;
  }
  if (event.learning_preferences) {
    nextState.learningPreferences = event.learning_preferences;
  }

  if (event.type === "progress" || event.type === "node_complete") {
    nextState.activeNodeLabel = event.node_label || event.node || null;
    const reasoning = resolveActiveReasoning(event);
    if (reasoning) {
      nextState.activeReasoning = reasoning;
    }
  }

  if (event.type === "complete") {
    nextState.activeNodeLabel = null;
    nextState.activeReasoning = null;
  }

  return nextState;
}

export function useWorkflowStream() {
  const [state, setState] = useState<WorkflowStreamState>(INITIAL_STATE);

  const resetStream = useCallback(() => {
    setState(INITIAL_STATE);
  }, []);

  const run = useCallback(async (path: string) => {
    setState((current) => ({
      ...current,
      isRunning: true,
      activeNodeLabel: "Starting workflow...",
    }));

    try {
      const board = await runWorkflowStream(path, (event) => {
        setState((current) => applyStreamEvent({ ...current, isRunning: true }, event));
      });
      setState((current) => ({
        ...current,
        isRunning: false,
        activeNodeLabel: null,
        activeReasoning: null,
      }));
      return board;
    } catch (error) {
      setState((current) => ({
        ...current,
        isRunning: false,
        activeNodeLabel: null,
        activeReasoning: null,
      }));
      throw error;
    }
  }, []);

  return useMemo(
    () => ({
      traces: state.traces,
      downloadEvents: state.downloadEvents,
      agentMessages: state.agentMessages,
      activeNodeLabel: state.activeNodeLabel,
      activeReasoning: state.activeReasoning,
      memoryContext: state.memoryContext,
      memoryUpdates: state.memoryUpdates,
      learningPreferences: state.learningPreferences,
      isRunning: state.isRunning,
      run,
      resetStream,
    }),
    [
      state.traces,
      state.downloadEvents,
      state.agentMessages,
      state.activeNodeLabel,
      state.activeReasoning,
      state.memoryContext,
      state.memoryUpdates,
      state.learningPreferences,
      state.isRunning,
      run,
      resetStream,
    ],
  );
}
