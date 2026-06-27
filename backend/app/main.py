from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.agents.workflow.checkpointer import close_checkpointer, init_checkpointer
from app.agents.workflow.runner import LangGraphRunner
from app.config import get_settings
from app.db import init_db
from app.routes import projects as projects_routes
from app.routes.projects import router as projects_router

settings = get_settings()
init_db()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_checkpointer()
    projects_routes.orchestrator = LangGraphRunner()
    yield
    await close_checkpointer()


app = FastAPI(title="EditDNA Rank Studio", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
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
async def health():
    missing = settings.missing_keys()
    return {
        "status": "ok",
        "missing_keys": missing,
        "allow_demo_fallback": settings.allow_demo_fallback,
    }
