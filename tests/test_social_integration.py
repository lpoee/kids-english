from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_document() -> dict:
    return json.loads((ROOT / "data" / "social_dialogues.json").read_text(encoding="utf-8"))


def test_original_site_exposes_social_mode_without_becoming_2_0() -> None:
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    assert "<title>English Fun!</title>" in html
    assert 'id="mode-social"' in html
    assert 'id="social-panel"' in html
    assert 'assets/social-player.js?v=4' in html
    assert "Kids English 2.0" not in html


def test_complete_social_curriculum_is_present() -> None:
    stories = load_document()["stories"]
    assert len(stories) == 18
    assert sum(len(story["turns"]) for story in stories) == 110
    assert all(sum("choice" in turn for turn in story["turns"]) == 1 for story in stories)
    assert all(
        len(next(turn["choice"]["options"] for turn in story["turns"] if "choice" in turn)) == 2
        for story in stories
    )


def test_every_social_turn_has_real_media() -> None:
    for story in load_document()["stories"]:
        for turn in story["turns"]:
            video = ROOT / turn["video"]
            poster = ROOT / turn["poster"]
            assert video.is_file(), video
            assert poster.is_file(), poster
            if turn["kind"] == "line":
                assert (ROOT / turn["audio"]).is_file(), turn["audio"]


def test_social_videos_are_browser_ready_silent_and_unique() -> None:
    videos = [
        ROOT / turn["video"]
        for story in load_document()["stories"]
        for turn in story["turns"]
    ]
    hashes = set()
    for video in videos:
        probe = subprocess.run(
            [
                "ffprobe", "-v", "error", "-show_entries", "stream=codec_name,codec_type,width,height",
                "-of", "json", str(video),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        streams = json.loads(probe.stdout)["streams"]
        assert streams == [{"codec_name": "h264", "codec_type": "video", "width": 720, "height": 480}], video
        hashes.add(hashlib.sha256(video.read_bytes()).hexdigest())
    assert len(videos) == 110
    assert len(hashes) == len(videos)


def test_first_story_uses_reviewed_minimax_media_without_model_audio() -> None:
    manifest = json.loads((ROOT / "data" / "social_media_manifest.json").read_text(encoding="utf-8"))
    first = manifest["stories"]["toy_car"]
    assert first["renderer"] == "minimax-h3"
    assert first["model_audio"] == "stripped"
    assert first["dialogue_audio"] == "approved-child-tts"
    assert first["source_size"] == [608, 352]
    assert first["published_size"] == [720, 480]
    assert first["turns"] == ["setup", "request", "accept", "thanks", "decline", "wait", "next_turn"]


def test_social_player_busts_the_minimax_media_cache() -> None:
    script = (ROOT / "assets" / "social-player.js").read_text(encoding="utf-8")
    assert "const ASSET_VERSION = '6';" in script


def test_second_story_uses_reviewed_minimax_media_without_model_audio() -> None:
    manifest = json.loads((ROOT / "data" / "social_media_manifest.json").read_text(encoding="utf-8"))
    story = manifest["stories"]["join_play"]
    assert story["renderer"] == "minimax-h3"
    assert story["model_audio"] == "stripped"
    assert story["dialogue_audio"] == "approved-child-tts"
    assert story["source_size"] == [608, 352]
    assert story["published_size"] == [720, 480]
    assert story["turns"] == ["setup", "request", "accept", "thanks", "decline", "wait"]


def test_all_social_stories_have_reviewed_minimax_media() -> None:
    document = load_document()
    manifest = json.loads((ROOT / "data" / "social_media_manifest.json").read_text(encoding="utf-8"))
    expected = {story["id"] for story in document["stories"]}
    assert set(manifest["stories"]) == expected
    for story in document["stories"]:
        media = manifest["stories"][story["id"]]
        assert media["renderer"] == "minimax-h3"
        assert media["model_audio"] == "stripped"
        assert media["visual_review"] == "start-middle-end-approved"
        assert media["turns"] == [turn["id"] for turn in story["turns"]]
