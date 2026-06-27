from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.agents.demo_workflow_runner import DemoWorkflowRunner
from app.agents.workflow.checkpointer import close_checkpointer, init_checkpointer
from app.agents.workflow.runner import LangGraphRunner
from app.config import get_settings
from app.db import init_db
from app.middleware.security_headers_middleware import SecurityHeadersMiddleware
from app.routes import projects as projects_routes
from app.routes.projects import router as projects_router
from app.services.api_status_service import build_api_status_response
from app.services.demo_pack_loader import is_demo_mode_active

settings = get_settings()
init_db()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_checkpointer()
    if is_demo_mode_active():
        projects_routes.orchestrator = DemoWorkflowRunner()
    else:
        projects_routes.orchestrator = LangGraphRunner()
    yield
    await close_checkpointer()


app = FastAPI(title="EditDNA Rank Studio", version="0.1.0", lifespan=lifespan)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3})(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects_router)

uploads_path = Path(settings.upload_dir)
outputs_path = Path(settings.output_dir)
uploads_path.mkdir(parents=True, exist_ok=True)
outputs_path.mkdir(parents=True, exist_ok=True)

app.mount("/uploads", StaticFiles(directory=str(uploads_path)), name="uploads")
app.mount("/outputs", StaticFiles(directory=str(outputs_path)), name="outputs")


@app.get("/api/health")
async def health(probe: bool = False):
    status = await build_api_status_response(probe=probe)
    return {
        "status": "ok",
        "missing_keys": status.missing_keys,
        "allow_demo_fallback": status.allow_demo_fallback,
        "gemini": status.gemini,
        "tavily": status.tavily,
        "slng": status.slng,
        "mubit": status.mubit,
        "integrations": [item.model_dump() for item in status.integrations],
    }
