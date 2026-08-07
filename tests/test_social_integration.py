from __future__ import annotations

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
    assert 'assets/social-player.js' in html
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


def test_social_videos_are_browser_ready_and_silent() -> None:
    first = load_document()["stories"][0]["turns"][0]
    probe = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "stream=codec_name,codec_type,width,height",
            "-of", "json", str(ROOT / first["video"]),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    streams = json.loads(probe.stdout)["streams"]
    assert streams == [{"codec_name": "h264", "codec_type": "video", "width": 720, "height": 480}]
