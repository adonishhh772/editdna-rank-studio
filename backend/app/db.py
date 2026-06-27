import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from sqlmodel import Field, Session, SQLModel, create_engine, select

from app.blackboard import ProjectBlackboard
from app.config import get_settings
from app.constants.project_visibility import is_visible_saved_project


class ProjectRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: str = Field(index=True, unique=True)
    user_id: str
    title: str
    run_id: str
    stage: str = "created"
    blackboard_json: str
    created_at: str
    updated_at: str


settings = get_settings()
db_path = settings.database_url.replace("sqlite:///", "")
if not db_path.startswith("/"):
    db_path = str(Path(__file__).resolve().parents[2] / db_path)
engine = create_engine(f"sqlite:///{db_path}", echo=False)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def save_blackboard(blackboard: ProjectBlackboard) -> None:
    with Session(engine) as session:
        record = session.exec(
            select(ProjectRecord).where(ProjectRecord.project_id == blackboard.project_id)
        ).first()
        payload = blackboard.model_dump(mode="json")
        now = utc_now()
        if record is None:
            record = ProjectRecord(
                project_id=blackboard.project_id,
                user_id=blackboard.user_id,
                title=blackboard.title,
                run_id=blackboard.run_id,
                stage=blackboard.stage,
                blackboard_json=json.dumps(payload),
                created_at=now,
                updated_at=now,
            )
        else:
            record.title = blackboard.title
            record.run_id = blackboard.run_id
            record.stage = blackboard.stage
            record.blackboard_json = json.dumps(payload)
            record.updated_at = now
        session.add(record)
        session.commit()


def load_blackboard(project_id: str) -> Optional[ProjectBlackboard]:
    with Session(engine) as session:
        record = session.exec(
            select(ProjectRecord).where(ProjectRecord.project_id == project_id)
        ).first()
        if record is None:
            return None
        data: dict[str, Any] = json.loads(record.blackboard_json)
        return ProjectBlackboard.model_validate(data)


def create_project(user_id: str, title: str) -> ProjectBlackboard:
    project_id = new_id("proj")
    run_id = new_id("run")
    blackboard = ProjectBlackboard(
        project_id=project_id,
        run_id=run_id,
        user_id=user_id,
        title=title,
    )
    save_blackboard(blackboard)
    return blackboard


def list_projects(include_tests: bool = False) -> list[dict[str, Any]]:
    with Session(engine) as session:
        records = session.exec(select(ProjectRecord)).all()
        summaries = [
            {
                "project_id": record.project_id,
                "title": record.title,
                "stage": record.stage,
                "user_id": record.user_id,
                "created_at": record.created_at,
                "updated_at": record.updated_at,
            }
            for record in records
        ]
        if include_tests:
            return summaries
        return [record for record in summaries if is_visible_saved_project(record)]


def delete_project(project_id: str) -> bool:
    with Session(engine) as session:
        record = session.exec(
            select(ProjectRecord).where(ProjectRecord.project_id == project_id)
        ).first()
        if record is None:
            return False
        session.delete(record)
        session.commit()
        return True
