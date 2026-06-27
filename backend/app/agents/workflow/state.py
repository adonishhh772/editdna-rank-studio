from typing_extensions import TypedDict

from app.blackboard import ProjectBlackboard


class WorkflowState(TypedDict):
    blackboard: ProjectBlackboard
