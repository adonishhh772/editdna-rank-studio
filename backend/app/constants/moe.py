from typing import Final

EXPERT_DOMAIN_STORY: Final[str] = "story"
EXPERT_DOMAIN_CUT: Final[str] = "cut"
EXPERT_DOMAIN_CAPTION: Final[str] = "caption"
EXPERT_DOMAIN_MOTION: Final[str] = "motion"

EXPERT_DOMAINS: Final[tuple[str, ...]] = (
    EXPERT_DOMAIN_STORY,
    EXPERT_DOMAIN_CUT,
    EXPERT_DOMAIN_CAPTION,
    EXPERT_DOMAIN_MOTION,
)

MESSAGE_TYPE_PROPOSAL: Final[str] = "proposal"
MESSAGE_TYPE_REQUEST: Final[str] = "request"
MESSAGE_TYPE_FEEDBACK: Final[str] = "feedback"
MESSAGE_TYPE_AGREEMENT: Final[str] = "agreement"
MESSAGE_TYPE_CONFLICT: Final[str] = "conflict"
MESSAGE_TYPE_ROUTING: Final[str] = "routing"

MOE_ROUND_PROPOSE: Final[str] = "propose"
MOE_ROUND_REFINE: Final[str] = "refine"
MOE_ROUND_FUSE: Final[str] = "fuse"
