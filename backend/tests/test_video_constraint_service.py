from app.constants.video_sources import YOUTUBE_SEARCH_MODE_SHORTS
from app.schemas import ReferenceBlueprint
from app.services.video_constraint_service import ReferenceVideoConstraints


def _blueprint() -> ReferenceBlueprint:
    return ReferenceBlueprint(
        blueprint_id="bp_test",
        project_id="proj_test",
        video_type="ranking_video",
        ranking_count=5,
        ranking_order="5_to_1",
        hook_duration_sec=3.0,
        average_item_duration_sec=4.0,
        outro_duration_sec=2.0,
        duration_sec=20.0,
        aspect_ratio="9:16",
        hook_style="question",
        rank_reveal_style="countdown",
        final_rank_drama_level="medium",
        confidence=0.9,
        section_order=[],
        caption_style={},
        text_overlay_style={},
        transition_style={},
        audio_style={},
        motion_style={},
        pacing_style={},
    )


def test_for_platform_search_relaxes_shorts_max_duration():
    constraints = ReferenceVideoConstraints.from_blueprint(_blueprint())
    search_constraints = constraints.for_platform_search(YOUTUBE_SEARCH_MODE_SHORTS)
    assert search_constraints.max_source_duration_sec == 60.0
    assert search_constraints.min_source_duration_sec == 1.0


def test_for_source_acceptance_allows_trim_from_longer_shorts():
    constraints = ReferenceVideoConstraints.from_blueprint(_blueprint())
    acceptance = constraints.for_source_acceptance(YOUTUBE_SEARCH_MODE_SHORTS)
    assert acceptance.max_source_duration_sec >= 90.0


def test_unknown_duration_shorts_url_with_mobile_orientation_is_acceptable():
    from app.services.video_constraint_service import evaluate_video_fit

    constraints = ReferenceVideoConstraints.from_blueprint(_blueprint()).for_platform_search(
        YOUTUBE_SEARCH_MODE_SHORTS
    )
    evaluation = evaluate_video_fit(
        duration_sec=None,
        width=None,
        height=None,
        orientation="mobile",
        aspect_ratio_hint="9:16",
        constraints=constraints,
    )
    assert evaluation.acceptable is True
