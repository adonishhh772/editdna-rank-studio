from typing import Any


def __getattr__(name: str) -> Any:
    if name in {"LangGraphRunner", "SwarmOrchestrator"}:
        from app.agents.workflow.runner import LangGraphRunner

        if name == "SwarmOrchestrator":
            return LangGraphRunner
        return LangGraphRunner
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["LangGraphRunner", "SwarmOrchestrator"]
