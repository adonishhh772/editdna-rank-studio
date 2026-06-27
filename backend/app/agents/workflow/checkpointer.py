from contextlib import AbstractAsyncContextManager
from pathlib import Path

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from app.config import get_settings

_checkpointer: BaseCheckpointSaver | None = None
_checkpointer_context: AbstractAsyncContextManager[AsyncSqliteSaver] | None = None


def resolve_checkpoint_db_path() -> Path:
    settings = get_settings()
    database_url = settings.database_url.replace("sqlite:///", "")
    if database_url.startswith("/"):
        base_dir = Path(database_url).parent
    else:
        base_dir = Path(__file__).resolve().parents[3]
    checkpoint_path = base_dir / "langgraph_checkpoints.db"
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    return checkpoint_path


async def init_checkpointer() -> BaseCheckpointSaver:
    global _checkpointer, _checkpointer_context
    if _checkpointer is not None:
        return _checkpointer

    checkpoint_path = resolve_checkpoint_db_path()
    _checkpointer_context = AsyncSqliteSaver.from_conn_string(str(checkpoint_path))
    _checkpointer = await _checkpointer_context.__aenter__()
    return _checkpointer


async def close_checkpointer() -> None:
    global _checkpointer, _checkpointer_context
    if _checkpointer_context is not None:
        await _checkpointer_context.__aexit__(None, None, None)
    _checkpointer = None
    _checkpointer_context = None


def get_checkpointer() -> BaseCheckpointSaver | None:
    return _checkpointer
