#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import re
from urllib.parse import quote
from urllib.request import urlopen
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "index.html"
OPENMOJI_DIR = ROOT / "assets" / "images" / "openmoji" / "color" / "618x618"
FLUENT_DIR = ROOT / "assets" / "images" / "fluent"
OUT_BASE = ROOT / "images" / "generated"
FLUENT_BASE_URL = "https://raw.githubusercontent.com/microsoft/fluentui-emoji/main/"

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
VOCAB_THEMES = [
    ("#fffef7", "#ffe9b8", "#ffc857", "#8b5a00", "#fff6dc"),
    ("#f4fbff", "#d3ebff", "#89c7ff", "#235a87", "#eaf6ff"),
    ("#f9fff5", "#d8f7c6", "#8add73", "#2f6b2d", "#efffea"),
    ("#fff7fb", "#ffd7ea", "#ff9bc6", "#92406a", "#fff0f8"),
    ("#f8f7ff", "#ddd6ff", "#a99bff", "#4f4a9a", "#f1efff"),
]

VOCAB_ASSET_SOURCES = {
    "cat": "assets/Cat/3D/cat_3d.png",
    "dog": "assets/Dog/3D/dog_3d.png",
    "bird": "assets/Bird/3D/bird_3d.png",
    "lion": "assets/Lion/3D/lion_3d.png",
    "monkey": "assets/Monkey/3D/monkey_3d.png",
    "rabbit": "assets/Rabbit/3D/rabbit_3d.png",
    "elephant": "assets/Elephant/3D/elephant_3d.png",
    "bear": "assets/Bear/3D/bear_3d.png",
    "fish": "assets/Fish/3D/fish_3d.png",
    "frog": "assets/Frog/3D/frog_3d.png",
    "duck": "assets/Duck/3D/duck_3d.png",
    "pig": "assets/Pig/3D/pig_3d.png",
    "cow": "assets/Cow/3D/cow_3d.png",
    "horse": "assets/Horse/3D/horse_3d.png",
    "sheep": "assets/Ewe/3D/ewe_3d.png",
    "chicken": "assets/Chicken/3D/chicken_3d.png",
    "tiger": "assets/Tiger/3D/tiger_3d.png",
    "panda": "assets/Panda/3D/panda_3d.png",
    "turtle": "assets/Turtle/3D/turtle_3d.png",
    "butterfly": "assets/Butterfly/3D/butterfly_3d.png",
    "apple": "assets/Red apple/3D/red_apple_3d.png",
    "banana": "assets/Banana/3D/banana_3d.png",
    "orange": "assets/Tangerine/3D/tangerine_3d.png",
    "grape": "assets/Grapes/3D/grapes_3d.png",
    "pear": "assets/Pear/3D/pear_3d.png",
    "watermelon": "assets/Watermelon/3D/watermelon_3d.png",
    "strawberry": "assets/Strawberry/3D/strawberry_3d.png",
    "cherry": "assets/Cherries/3D/cherries_3d.png",
    "peach": "assets/Peach/3D/peach_3d.png",
    "mango": "assets/Mango/3D/mango_3d.png",
    "pineapple": "assets/Pineapple/3D/pineapple_3d.png",
    "lemon": "assets/Lemon/3D/lemon_3d.png",
    "bread": "assets/Bread/3D/bread_3d.png",
    "cake": "assets/Birthday cake/3D/birthday_cake_3d.png",
    "cookie": "assets/Cookie/3D/cookie_3d.png",
    "milk": "assets/Glass of milk/3D/glass_of_milk_3d.png",
    "egg": "assets/Egg/3D/egg_3d.png",
    "cheese": "assets/Cheese wedge/3D/cheese_wedge_3d.png",
    "rice": "assets/Rice ball/3D/rice_ball_3d.png",
    "water": "assets/Droplet/3D/droplet_3d.png",
    "candy": "assets/Candy/3D/candy_3d.png",
    "ice_cream": "assets/Ice cream/3D/ice_cream_3d.png",
    "eye": "assets/Eye/3D/eye_3d.png",
    "ear": "assets/Ear/Default/3D/ear_3d_default.png",
    "nose": "assets/Nose/Default/3D/nose_3d_default.png",
    "mouth": "assets/Mouth/3D/mouth_3d.png",
    "hand": "assets/Hand with fingers splayed/Default/3D/hand_with_fingers_splayed_3d_default.png",
    "foot": "assets/Foot/Default/3D/foot_3d_default.png",
    "head": "assets/Bust in silhouette/3D/bust_in_silhouette_3d.png",
    "arm": "assets/Flexed biceps/Default/3D/flexed_biceps_3d_default.png",
    "bed": "assets/Bed/3D/bed_3d.png",
    "chair": "assets/Chair/3D/chair_3d.png",
    "table": "images/table.svg",
    "door": "assets/Door/3D/door_3d.png",
    "window": "assets/Window/3D/window_3d.png",
    "cup": "assets/Cup with straw/3D/cup_with_straw_3d.png",
    "spoon": "assets/Spoon/3D/spoon_3d.png",
    "clock": "assets/Alarm clock/3D/alarm_clock_3d.png",
    "eat": "assets/Fork and knife with plate/3D/fork_and_knife_with_plate_3d.png",
    "drink": "assets/Cup with straw/3D/cup_with_straw_3d.png",
    "sleep": "assets/Person in bed/Default/3D/person_in_bed_3d_default.png",
    "run": "assets/Person running/Default/3D/person_running_3d_default.png",
    "jump": "images/jump.svg",
    "walk": "images/walk.svg",
    "sit": "images/sit.svg",
    "stand": "images/stand.svg",
    "clap": "images/clap.svg",
    "wave": "images/wave.svg",
}


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


def data_url_for_file(path: Path) -> str:
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    mime = "image/svg+xml" if path.suffix.lower() == ".svg" else "image/png"
    return f"data:{mime};base64,{data}"


def resolve_vocab_asset(slug: str, source: str) -> Path:
    local_path = ROOT / source
    if local_path.exists():
        return local_path

    FLUENT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = FLUENT_DIR / f"{slug}.png"
    if not out_path.exists():
        url = FLUENT_BASE_URL + quote(source, safe="/")
        with urlopen(url) as response:
            out_path.write_bytes(response.read())
    return out_path


def pick_theme(seed: str, themes: list[tuple[str, str, str, str, str]]) -> tuple[str, str, str, str, str]:
    idx = int(hashlib.sha256(seed.encode("utf-8")).hexdigest(), 16) % len(themes)
    return themes[idx]


def build_svg(seed: str, icon_href: str, kind: str) -> str:
    theme_pool = PHRASE_THEMES if kind == "phrases" else VOCAB_THEMES if kind == "vocab" else EMOJI_THEMES
    bg0, bg1, accent, line, cloud = pick_theme(seed, theme_pool)
    sparkle = accent.replace("#", "#")
    icon_x, icon_y, icon_w, icon_h = (220, 150, 760, 760) if kind == "vocab" else (250, 180, 700, 700)

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
    <image href="{icon_href}" x="{icon_x}" y="{icon_y}" width="{icon_w}" height="{icon_h}" preserveAspectRatio="xMidYMid meet"/>
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
    vocab_dir = OUT_BASE / "vocab"
    emoji_dir.mkdir(parents=True, exist_ok=True)
    phrase_dir.mkdir(parents=True, exist_ok=True)
    vocab_dir.mkdir(parents=True, exist_ok=True)

    for label, emoji in emoji_items:
        slug = slugify(label)
        svg = build_svg(slug, resolve_icon_path(emoji), "emoji")
        (emoji_dir / f"{slug}.svg").write_text(svg, encoding="utf-8")

    for emoji, slug in phrase_items:
        svg = build_svg(slug, resolve_icon_path(emoji), "phrases")
        (phrase_dir / f"{slug}.svg").write_text(svg, encoding="utf-8")

    for slug, source in VOCAB_ASSET_SOURCES.items():
        local_path = resolve_vocab_asset(slug, source)
        svg = build_svg(slug, data_url_for_file(local_path), "vocab")
        (vocab_dir / f"{slug}.svg").write_text(svg, encoding="utf-8")

    print(
        f"generated {len(emoji_items)} emoji cards, {len(phrase_items)} phrase cards, "
        f"and {len(VOCAB_ASSET_SOURCES)} vocabulary cards"
    )


if __name__ == "__main__":
    write_assets()
