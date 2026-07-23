import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "index.html").read_text(encoding="utf-8")


class IPadAudioPlaybackTests(unittest.TestCase):
    def test_uses_one_persistent_html_audio_player(self):
        self.assertRegex(
            HTML,
            r'<audio\s+id="audio-player"[^>]*preload="auto"[^>]*playsinline[^>]*></audio>',
        )
        self.assertIn("const audioPlayer = $('audio-player');", HTML)

    def test_does_not_use_async_web_audio_decode_pipeline(self):
        self.assertNotIn("AudioContext", HTML)
        self.assertNotIn("decodeAudioData", HTML)
        self.assertNotRegex(HTML, r"fetch\(word\.aud\)")

    def test_english_and_chinese_reuse_the_persistent_player(self):
        self.assertRegex(HTML, r"audioPlayer\.src\s*=\s*path")
        self.assertRegex(HTML, r"playAudioFile\(word\.aud")
        self.assertRegex(HTML, r"playAudioFile\(cnPath")
        self.assertNotIn("new Audio(", HTML)

    def test_autoplay_starts_from_the_button_gesture(self):
        toggle = re.search(
            r"function toggleAutoplay\(\)\s*\{(?P<body>.*?)\n\}", HTML, re.S
        )
        self.assertIsNotNone(toggle)
        if toggle is None:
            return
        self.assertRegex(toggle.group("body"), r"if \(state\.autoplay\) tapWord\(\)")


if __name__ == "__main__":
    unittest.main()
