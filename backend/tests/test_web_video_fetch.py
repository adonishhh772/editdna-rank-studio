from app.agents.base import BaseAgent
from app.blackboard import ProjectBlackboard
from app.constants.video_sources import (
    is_blocked_platform_url,
    is_downloadable_platform_url,
    platform_download_priority,
)


def test_youtube_url_detection():
    assert is_downloadable_platform_url("https://www.youtube.com/watch?v=abc123") is True


def test_dailymotion_blocked():
    assert is_blocked_platform_url("https://www.dailymotion.com/video/x9z6xjc") is True
    assert is_downloadable_platform_url("https://www.dailymotion.com/video/x9z6xjc") is False


def test_youtube_preferred_over_other_platforms():
    assert platform_download_priority("https://www.youtube.com/watch?v=abc") < platform_download_priority(
        "https://www.tiktok.com/@user/video/123"
    )


def test_tiktok_url_detection():
    assert is_downloadable_platform_url("https://www.tiktok.com/@user/video/123") is True


def test_platform_search_agent_exists():
    from app.agents.platform_video_search_agent import PlatformVideoSearchAgent

    agent = PlatformVideoSearchAgent()
    assert agent.agent_id == "platform_video_search"


def test_platform_download_agent_exists():
    from app.agents.platform_video_download_agent import PlatformVideoDownloadAgent

    agent = PlatformVideoDownloadAgent(target="pool")
    assert agent.agent_id == "platform_video_download"
