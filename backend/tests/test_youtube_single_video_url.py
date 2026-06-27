from app.constants.video_sources import is_single_youtube_video_url, is_youtube_url


def test_is_youtube_url_accepts_playlist():
    playlist_url = "https://music.youtube.com/playlist?list=PL2_v15L-r6ZyVKdoabk1so8EhjeyS4aZ1"
    assert is_youtube_url(playlist_url) is True
    assert is_single_youtube_video_url(playlist_url) is False


def test_is_single_youtube_video_url_accepts_watch_and_shorts():
    assert is_single_youtube_video_url("https://www.youtube.com/watch?v=abc123") is True
    assert is_single_youtube_video_url("https://youtu.be/abc123") is True
    assert is_single_youtube_video_url("https://www.youtube.com/shorts/7WD9AvjX0Jw") is True


def test_is_single_youtube_video_url_accepts_watch_with_playlist_context():
    assert (
        is_single_youtube_video_url(
            "https://www.youtube.com/watch?v=abc123&list=PLsomething"
        )
        is True
    )


def test_is_single_youtube_video_url_rejects_channel_pages():
    assert is_single_youtube_video_url("https://www.youtube.com/channel/UCabc123") is False
    assert is_single_youtube_video_url("https://www.youtube.com/@somecreator") is False
