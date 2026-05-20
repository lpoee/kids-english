#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "index.html"
OPENMOJI_DIR = ROOT / "assets" / "images" / "openmoji" / "color" / "618x618"
OUT_BASE = ROOT / "images" / "generated"

PHRASE_THEMES = [
    ("#f8fbff", "#cfe8ff", "#8ac6ff", "#1f4d8f", "#ecf6ff"),
    ("#fff8f0", "#ffd7ad", "#ff9c73", "#96411d", "#fff0de"),
    ("#f7fff6", "#c6f2c0", "#74d66f", "#21613d", "#eaffea"),
    ("#fff5fb", "#f7c4e6", "#f287c2", "#8f2c66", "#fff0f8"),
    ("#f8f6ff", "#d9cdfc", "#9b84ff", "#4c3b92", "#f0ecff"),
    ("#fffef3", "#ffe890", "#ffcb45", "#8e6714", "#fff8d1")
]
EMOJI_THEMES = [
    ("#f5fff8", "#c7f1d4", "#7ed79a", "#275940", "#ecfff1"),
    ("#fff8f2", "#ffd9b8", "#ffab6e", "#8d4f1f", "#fff0e3"),
    ("#f4fbff", "#cbeaff", "#87c8ff", "#21507a", "#ebf7ff"),
    ("#fff6fb", "#f7d0e9", "#ee9bc9", "#843460", "#fff0f7")
]


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def emoji_to_codepoints(emoji: str) -> str:
    return "-".join(f"{ord(char):X}" for char in emoji)


def resolve_icon_path(emoji: str) -> str:
    candidates = [emoji_to_codepoints(emoji)]
    if "FE0F" in candidates[0]:
        candidates.append(candidates[0].replace("-FE0F", "").replace("FE0F-", ""))

    for code in candidates:
        path = OPENMOJI_DIR / f"{code}.png"
        if path.exists():
            data = base64.b64encode(path.read_bytes()).decode("ascii")
            return f"data:image/png;base64,{data}"

    raise FileNotFoundError(f"No OpenMoji PNG found for {emoji!r}")


def pick_theme(seed: str, themes: list[tuple[str, str, str, str, str]]) -> tuple[str, str, str, str, str]:
    idx = int(hashlib.sha256(seed.encode("utf-8")).hexdigest(), 16) % len(themes)
    return themes[idx]


def build_svg(seed: str, icon_href: str, kind: str) -> str:
    bg0, bg1, accent, line, cloud = pick_theme(seed, PHRASE_THEMES if kind == "phrases" else EMOJI_THEMES)
    sparkle = accent.replace("#", "#")

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 1200" role="img" aria-label="{seed}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{bg0}"/>
      <stop offset="55%" stop-color="{bg1}"/>
      <stop offset="100%" stop-color="{accent}"/>
    </linearGradient>
    <radialGradient id="glow" cx="50%" cy="28%" r="52%">
      <stop offset="0%" stop-color="#ffffff" stop-opacity="0.92"/>
      <stop offset="100%" stop-color="#ffffff" stop-opacity="0"/>
    </radialGradient>
    <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="26" stdDeviation="28" flood-color="#132238" flood-opacity="0.18"/>
    </filter>
  </defs>
  <rect width="1200" height="1200" rx="96" fill="url(#bg)"/>
  <circle cx="320" cy="220" r="180" fill="url(#glow)"/>
  <circle cx="950" cy="160" r="82" fill="#ffffff" opacity="0.22"/>
  <circle cx="1040" cy="280" r="34" fill="#ffffff" opacity="0.28"/>
  <circle cx="178" cy="360" r="28" fill="#ffffff" opacity="0.22"/>
  <path d="M120 860C250 780 410 760 540 812C674 867 810 873 1080 760V1200H120Z" fill="{cloud}" opacity="0.9"/>
  <path d="M0 916C188 810 356 790 560 868C786 954 934 962 1200 850V1200H0Z" fill="#ffffff" opacity="0.38"/>
  <ellipse cx="600" cy="880" rx="314" ry="76" fill="{line}" opacity="0.16"/>
  <g opacity="0.14">
    <circle cx="266" cy="540" r="14" fill="{sparkle}"/>
    <circle cx="902" cy="528" r="10" fill="{sparkle}"/>
    <circle cx="972" cy="624" r="18" fill="{sparkle}"/>
    <circle cx="238" cy="648" r="18" fill="{sparkle}"/>
  </g>
  <g filter="url(#shadow)">
    <image href="{icon_href}" x="250" y="180" width="700" height="700" preserveAspectRatio="xMidYMid meet"/>
  </g>
  <g opacity="0.15">
    <image href="{icon_href}" x="865" y="116" width="160" height="160" preserveAspectRatio="xMidYMid meet"/>
  </g>
</svg>
"""


def extract_items() -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    html = INDEX_PATH.read_text(encoding="utf-8")
    emoji_items = re.findall(r"emojiItem\('([^']+)'\s*,\s*'([^']+)'\)", html)
    phrase_items = re.findall(
        r"phraseItem\((?:'[^']*'|\"[^\"]*\"),\s*'([^']+)'\s*,\s*'([^']+)'\)",
        html,
    )
    return emoji_items, phrase_items


def write_assets() -> None:
    emoji_items, phrase_items = extract_items()
    emoji_dir = OUT_BASE / "emoji"
    phrase_dir = OUT_BASE / "phrases"
    emoji_dir.mkdir(parents=True, exist_ok=True)
    phrase_dir.mkdir(parents=True, exist_ok=True)

    for label, emoji in emoji_items:
        slug = slugify(label)
        svg = build_svg(slug, resolve_icon_path(emoji), "emoji")
        (emoji_dir / f"{slug}.svg").write_text(svg, encoding="utf-8")

    for emoji, slug in phrase_items:
        svg = build_svg(slug, resolve_icon_path(emoji), "phrases")
        (phrase_dir / f"{slug}.svg").write_text(svg, encoding="utf-8")

    print(f"generated {len(emoji_items)} emoji cards and {len(phrase_items)} phrase cards")


if __name__ == "__main__":
    write_assets()
