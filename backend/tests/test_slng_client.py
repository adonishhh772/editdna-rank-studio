from app.integrations.slng_client import extract_transcript_from_stt_response


def test_extract_transcript_from_stt_response_uses_top_level_text():
    payload = {"text": "  hello world  "}
    assert extract_transcript_from_stt_response(payload) == "hello world"


def test_extract_transcript_from_stt_response_uses_deepgram_channels_format():
    payload = {
        "results": {
            "channels": [
                {
                    "alternatives": [
                        {"transcript": "rank five is the best", "confidence": 0.98},
                    ],
                },
            ],
        },
    }
    assert extract_transcript_from_stt_response(payload) == "rank five is the best"


def test_extract_transcript_from_stt_response_returns_empty_for_missing_transcript():
    assert extract_transcript_from_stt_response({}) == ""
    assert extract_transcript_from_stt_response({"results": {"channels": []}}) == ""
