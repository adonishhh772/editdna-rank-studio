import pytest

from app.constants.demo import DEMO_PACK_LIVE, DEMO_PACK_RECORDING
from app.services.demo_pack_loader import load_demo_pack


def test_load_pack_recording_has_five_candidates():
    pack = load_demo_pack(DEMO_PACK_RECORDING)
    assert pack.ranking_count == 5
    assert pack.reject_demo_slot == 3
    assert pack.reject_concepts[3] == "Off-topic clip — not strong enough for 3D art ranking"
    assert pack.youtube_url.startswith("https://")
    assert "3D Arts" in pack.topic
    assert pack.project_title is not None
    assert pack.rank_concepts[1] == "Hero cinematic 3D scene"
    assert pack.rank_concepts[5] == "Stylized character sculpt"
    assert 1 in pack.candidate_files
    assert 5 in pack.candidate_files
    assert pack.final_output_path.exists()


def test_load_pack_live_has_six_candidates():
    pack = load_demo_pack(DEMO_PACK_LIVE)
    assert pack.ranking_count == 6
    assert pack.reject_demo_slot == 4
    assert pack.reject_concepts[4] == "Generic dance clip — not strong enough for sea lion trend"
    assert "Sea Lion" in pack.topic
    assert pack.rank_concepts[6] == "Classic aquarium sea lion spin"
    assert 6 in pack.candidate_files
    assert pack.final_output_path.exists()


def test_load_unknown_pack_raises():
    with pytest.raises(ValueError, match="Unknown demo pack"):
        load_demo_pack("pack_unknown")
