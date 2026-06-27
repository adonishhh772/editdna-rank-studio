from typing import Final

GOAL_CANDIDATES_SELECTED: Final[str] = "candidates_selected"
GOAL_MOE_COMPLETE: Final[str] = "moe_complete"
GOAL_NO_CONFLICTS: Final[str] = "no_conflicts"
GOAL_RANK_ONE_EMPHASIS: Final[str] = "rank_one_emphasis"
GOAL_STORY_COHERENCE: Final[str] = "story_coherence"

HARNESS_ROUTE_RETRY: Final[str] = "retry"
HARNESS_ROUTE_CONTINUE: Final[str] = "continue"

MAX_HARNESS_REVISIONS: Final[int] = 2

EDIT_PLAN_GOALS: Final[tuple[str, ...]] = (
    GOAL_CANDIDATES_SELECTED,
    GOAL_MOE_COMPLETE,
    GOAL_NO_CONFLICTS,
    GOAL_RANK_ONE_EMPHASIS,
    GOAL_STORY_COHERENCE,
)
