#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable
from urllib import error as urlerror
from urllib import request as urlrequest

from PIL import Image, ImageFilter, ImageOps, ImageStat

from fetch_openverse_photos import ADJ_SELECTIONS, PHRASE_SELECTIONS, PLAIN_BG_WORDS, WORD_SELECTIONS


ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "index.html"
TMP_DIR = ROOT / ".tmp" / "ai_flashcards"
GENERATED_DIR = ROOT / "images" / "generated"
MANIFEST_DIR = GENERATED_DIR / "manifests"
WORD_DIR = GENERATED_DIR / "vocab"
ADJ_DIR = GENERATED_DIR / "adjectives"
PHRASE_DIR = GENERATED_DIR / "phrases"
PHRASE_GIF_DIR = GENERATED_DIR / "phrase_gifs"
PHRASE_FRAME_DIR = PHRASE_GIF_DIR / "frames"

WORD_EXT = ".png"
PHRASE_EXT = ".png"
GIF_EXT = ".gif"
COMFYUI_URL = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188")
DEFAULT_GENERATOR = os.environ.get("FLASHCARD_GENERATOR", "comfyui")
FLUX2_KLEIN_CHECKPOINT = "flux-2-klein-4b.safetensors"
FLUX2_KLEIN_TEXT_ENCODER = "qwen_3_4b.safetensors"
FLUX2_VAE = "flux2-vae.safetensors"
DEFAULT_CHECKPOINT = os.environ.get("FLASHCARD_SD_CHECKPOINT", FLUX2_KLEIN_CHECKPOINT)
COMFYUI_TIMEOUT = int(os.environ.get("COMFYUI_TIMEOUT", "300"))
COMFYUI_POLL = float(os.environ.get("COMFYUI_POLL", "3"))
REVIEW_IMAGE_MAX_EDGE = 512
REVIEW_IMAGE_FORMAT = "PNG"

DEFAULT_QA_URL = os.environ.get("OMINI_REVIEW_URL") or os.environ.get(
    "OMNI_REVIEW_URL",
    "http://127.0.0.1:18090/v1/chat/completions",
)
DEFAULT_QA_MODEL = os.environ.get("OMINI_REVIEW_MODEL") or os.environ.get(
    "OMNI_REVIEW_MODEL",
    "Nemotron-3-Nano-Omni-30B-A3B-AWQ",
)
DEFAULT_QA_MIN_SCORE = 85
REVIEW_CHAT_TEMPLATE_KWARGS = {"enable_thinking": False}

QA_PROMPT = """You are reviewing one generated image for a private kids English flashcard app for a 4-year-old child.

Return JSON only with these keys:
- pass: boolean
- score: integer from 0 to 100
- reason: short string
- issues: array of short strings
- rubric: object with integer fields image_quality, concept_clarity, child_friendliness, distraction_level

Rubric — judge the image itself, not whether it follows style instructions:
- image_quality: Is the image technically well-made? Sharp, well-lit, no ugly artifacts, no deformed anatomy, no broken shapes, no harsh noise or compression junk?
- concept_clarity: Would a 4-year-old understand the target concept almost instantly from this image? Is the subject obvious, centered, and the main thing the eye lands on?
- child_friendliness: Is the image warm, age-appropriate, and appealing to a young child? Not scary, not uncanny, not cold or clinical.
- distraction_level: Does anything in the image pull attention away from the concept? Score HIGH when the image is clean and focused. Score LOW when there is visual noise, busy background, extra unrelated subjects, or anything that makes a child confused about what to look at.

Rules:
- PASS if the image is high-quality, the concept is instantly clear, and nothing distracts from it.
- FAIL if the image is technically bad (blurry, ugly, deformed), if the concept is confusing or ambiguous, or if strong distractions compete with the subject.
- Do NOT fail an image just because the background is not plain. Fail only if the background actively distracts from or confuses the concept.
- Do NOT fail an image just because it includes a minor secondary element. Fail only if that element pulls focus away from the target concept.
- Do not explain your reasoning.
- Do not think step by step.
- Put the final JSON in message.content.
- score must be an integer from 0 to 100.
- Keep reason short and concrete.
- issues must be a short list of the biggest problems; use [] when there are no issues.
"""

FLASHCARD_STYLE = (
    "Create one high-quality square cute children's animation illustration for a kids English learning app. "
    "Use a consistent cute children's animation style with bright friendly colors, rounded readable shapes, crisp silhouettes, soft friendly expressions, and an age-appropriate gentle tone. "
    "Make it instantly recognizable to a 4-year-old. "
    "The output must be one single standalone illustration, not a page layout, collection, poster sheet, or multiple framed pictures. "
)

VOCAB_FLASHCARD_STYLE = (
    "Create one square cute animation-style flashcard image of exactly one subject. "
    "Use a simple educational composition with one large centered subject, rounded clean edges, and a plain soft background. "
    "This is a flashcard image, not a poster, page design, or story scene. "
)

ANIMAL_FLASHCARD_STYLE = (
    "Create one square cute animation-style illustration of exactly one animal. "
    "Use flat 2D children's animation artwork with thick clean outlines, simple rounded readable shapes, bright gentle colors, smooth cel shading, and no realistic photography or textured rendering. "
    "Do not make a poster design, printed card mockup, or story scene. "
    "The animal must be the only thing noticed at a glance and must look cute, friendly, and easy for a 4-year-old to recognize. "
)

FOOD_FLASHCARD_STYLE = (
    "Create one square cute cartoon illustration of exactly one food item. "
    "Use simple clean children's animation illustration, not realistic photography, not portrait photography, and not a story scene. "
    "The background must be plain and minimal so the food item fills most of the frame and is the only thing noticed at a glance. "
)

FLASHCARD_NEGATIVE = "No text, watermark, logo, border, collage, split screen, framed picture grid, or multi-panel layout."

FLASHCARD_ARTIFACT_NEGATIVE = (
    "text, watermark, logo, border, frame, collage, split screen, grid, "
    "multi-panel layout, repeated subject, duplicate subject, poster"
)

# Adjective cards need comparison layouts (two shapes + arrow) — strip terms that kill those.
FLASHCARD_ADJ_NEGATIVE = (
    "text, watermark, logo, border, frame, collage, split screen, "
    "poster, busy background, scary"
)

# Action cards need a person, but still must forbid duplicate figures, poster layouts, and text.
FLASHCARD_ACTION_NEGATIVE = (
    "text, watermark, logo, border, frame, collage, split screen, grid, "
    "multi-panel layout, duplicate person, duplicate child, repeated figure, poster"
)

# Animal cards should not turn into printed flashcards, posters, or pasted cutouts.
FLASHCARD_ANIMAL_NEGATIVE = (
    "text, watermark, logo, border, frame, collage, split screen, grid, "
    "multi-panel layout, poster, card mockup, printed card, paper sheet, placard, sign, "
    "label, caption box, scrapbook, sticker sheet, cutout on board, mounted specimen, "
    "taxidermy, specimen photo, isolated specimen, studio cutout, realistic photo, photography, photorealistic, duplicate animal, second animal, person, child, hand, cage, aquarium, fish tank, "
    "plate, bowl, tray, seafood platter, seafood display, market fish, dead fish, fish on ice, ice bed, cutting board, "
    "cooked fish, fish fillet, raw fillet, sushi, garnish, prepared food, food styling, hook, bait, net, "
    "floating card, rounded square backdrop, inset panel, mockup panel"
)

# Fish is taught here as one live fish, not plated food, not a market display, and not a card mockup.
FLASHCARD_FISH_NEGATIVE = (
    "text, watermark, logo, border, frame, collage, split screen, grid, "
    "multi-panel layout, poster, card mockup, printed card, paper sheet, placard, sign, "
    "label, caption box, scrapbook, sticker sheet, rounded square backdrop, inset panel, mockup panel, "
    "person, child, hand, plate, bowl, tray, seafood platter, seafood display, market stall, fish on ice, ice bed, "
    "cutting board, knife, cooked fish, fish fillet, raw fillet, sushi, garnish, prepared food, food styling, "
    "duplicate fish, second fish, cropped subject, dead fish, hook, bait, net, aquarium glass, fish tank, tank decorations"
)

# Food cards must be product photography with NO children, NO people.
FLASHCARD_FOOD_NEGATIVE = (
    "text, watermark, logo, border, frame, collage, split screen, grid, "
    "multi-panel layout, poster, portrait, person, child, children, face, hand, people, human, "
    "plate, bowl, table, cup, glass, bottle, vase, jar, carafe, drink, pitcher, basket, tray, "
    "placemat, napkin, cutting board, square card, paper sheet, black frame, serving dish, "
    "cropped subject, duplicate fruit, second bunch, second item, repeated object, "
    "pile of grapes, loose grapes, fruit pattern, macro close-up, extreme close-up, "
    "cartoon, illustration, animation, drawing, painting, sketch, 3d render"
)

# Body-part cards must be macro photography with NO children, NO faces, NO people.
FLASHCARD_BODY_NEGATIVE = (
    "text, watermark, logo, border, frame, collage, split screen, grid, "
    "multi-panel layout, poster, child, children, kid, person, face, people, human, "
    "jewelry, hat, glasses, realistic skin texture, photographic lighting, "
    "cartoon, illustration, animation, drawing, painting, sketch, 3d render, "
    "toy, doll, mannequin, plastic, puppet"
)

# Home-object cards must be product photography with NO children, NO people.
FLASHCARD_HOME_NEGATIVE = (
    "text, watermark, logo, border, frame, collage, split screen, grid, "
    "multi-panel layout, poster, child, children, kid, person, face, hand, people, human, "
    "cartoon, illustration, animation, drawing, painting, sketch, 3d render, "
    "portrait, lifestyle photo, room scene, interior design, decorated room, "
    "toy version, dollhouse, miniature"
)

ANIMAL_WORDS = {
    "cat", "dog", "bird", "lion", "monkey", "rabbit", "elephant", "bear", "fish", "frog",
    "duck", "pig", "cow", "horse", "sheep", "chicken", "tiger", "panda", "turtle", "butterfly",
}
FOOD_WORDS = {
    "apple", "banana", "orange", "grape", "pear", "watermelon", "strawberry", "cherry", "peach",
    "mango", "pineapple", "lemon", "bread", "cake", "cookie", "milk", "egg", "cheese", "rice",
    "water", "candy", "ice_cream",
}
CLUSTER_FRUIT_WORDS = {"grape", "cherry"}
BODY_WORDS = {"eye", "ear", "nose", "mouth", "hand", "foot", "head", "arm"}
HOME_WORDS = {"bed", "chair", "table", "door", "window", "cup", "spoon", "clock"}
ACTION_WORDS = {"eat", "drink", "sleep", "run", "jump", "walk", "sit", "stand", "clap", "wave"}

ADJ_PROMPTS = {
    "big": "Two identical red circles on a plain pastel background. A bright arrow points to the very large circle that fills most of the frame. The other circle is very small beside it.",
    "small": "Two identical yellow circles on a plain pastel background. A bright arrow points to the very tiny circle. The other circle is very large beside it.",
    "tall": "Two identical green rectangles on a plain pastel background. Both rectangles have exactly the same width. A bright arrow points to the very tall rectangle reaching the top of the frame. The other rectangle is very short beside it.",
    "short": "Two identical blue rectangles on a plain pastel background. Both rectangles have exactly the same width. A bright arrow points to the very short rectangle. The other rectangle is very tall beside it.",
    "long": "Two identical red horizontal lines on a plain pastel background. Both lines have exactly the same thickness. A bright arrow points to the very long line stretching all the way across the frame. The other line is very short beside it.",
    "wide": "Two identical purple rectangles on a plain pastel background. Both rectangles have exactly the same height. A bright arrow points to the very wide rectangle stretching across the frame. The other rectangle is very narrow beside it.",
    "narrow": "Two identical orange rectangles on a plain pastel background. Both rectangles have exactly the same height. A bright arrow points to the very narrow rectangle. The other rectangle is very wide beside it.",
    "round": "A perfectly round red circle centered on a plain pastel background. The round shape is the only thing in the image.",
    "square": "A clear square shape centered on a plain pastel background. The square shape is the only thing in the image.",
    "fast": "A cheetah running with visible speed lines on a plain pastel background.",
    "slow": "A turtle walking slowly on a plain pastel background.",
}

PHRASE_LABEL_OVERRIDES = {
    "im_fine": "I'm fine",
    "im_okay": "I'm okay",
    "whats_your_name": "What's your name",
    "my_name_is": "My name is",
    "youre_welcome": "You're welcome",
    "its_okay": "It's okay",
    "im_happy": "I'm happy",
    "im_sad": "I'm sad",
    "im_angry": "I'm angry",
    "im_scared": "I'm scared",
    "i_like_it": "I like it",
    "i_dont_like_it": "I don't like it",
    "i_love_you": "I love you",
    "thats_funny": "That's funny",
    "im_hungry": "I'm hungry",
    "im_thirsty": "I'm thirsty",
    "im_tired": "I'm tired",
    "can_you_help_me": "Can you help me",
    "i_want": "I want",
    "i_dont_want": "I don't want",
    "more_please": "More please",
    "no_more": "No more",
    "im_done": "I'm done",
    "all_done": "All done",
    "i_dont_know": "I don't know",
    "lets_go": "Let's go",
    "lets_play": "Let's play",
    "my_turn": "My turn",
    "your_turn": "Your turn",
    "share_please": "Share please",
    "be_careful": "Be careful",
    "slow_down": "Slow down",
    "sit_down": "Sit down",
    "stand_up": "Stand up",
    "quiet_please": "Quiet please",
    "raise_your_hand": "Raise your hand",
    "try_again": "Try again",
    "good_job": "Good job",
    "well_done": "Well done",
    "you_can_do_it": "You can do it",
    "whats_this": "What's this",
    "whats_that": "What's that",
    "where_is_it": "Where is it",
    "where_are_you": "Where are you",
    "who_is_it": "Who is it",
    "can_i": "Can I",
    "come_here": "Come here",
    "go_there": "Go there",
    "put_it_here": "Put it here",
    "give_me": "Give me",
    "show_me": "Show me",
    "point_to": "Point to",
}

# Prompt architecture:
# 1. shared base
# 2. category module
# 3. word-specific patch
# 4. retry patch


def vocab_shared_base() -> str:
    return (
        f"{VOCAB_FLASHCARD_STYLE}Show one clear main subject only. "
        "Keep the full subject inside frame, centered, and large. "
        "Keep the composition simple and easy to read. "
        f"{FLASHCARD_NEGATIVE} "
    )


def animal_prompt_module(label: str) -> str:
    if label.lower() == "fish":
        return (
            f"{ANIMAL_FLASHCARD_STYLE}"
            "A single cheerful fish swimming upward at a playful angle through bright clear water. "
            "Show the full body curving in a lively S-curve in side view, with tail, fins, eye, and smiling mouth clearly visible. "
            "The fish must look happy, energetic, and in motion — body curved dynamically, fins spread wide, a few cheerful bubbles trailing behind. "
            "Make the fish large and centered, filling most of the frame, flat 2D, super cute, and instantly recognizable. "
            "Use a bright cheerful sky-blue background as the only background, with no rocks, no plants, no decorations, no seaweed. "
            "The fish should have vibrant playful colors — a warm orange or coral body with brighter accent stripes or spots, not dull or muted. "
            "Use thick bold outlines, simple rounded fins, a big friendly eye with a highlight dot, a cute smile, and smooth cel-shaded color blocks. "
            "Not a goldfish, not a fancy ornamental fish, and not a toy-like fish. "
            "No plate, no bowl, no tray, no cutting board, no ice, no fillet, no garnish, no market display, and no props. "
            "No dead fish, no fish lying flat on its side, no taxidermy, no specimen display."
        )
    if label.lower() == "chicken":
        return (
            f"{ANIMAL_FLASHCARD_STYLE}Show one live hen only. "
            "Full body visible, centered, isolated, and easy to recognize instantly. "
            "Use a plain pale background and no scenery, no props, and no food presentation."
        )
    if label.lower() == "duck":
        return (
            f"{ANIMAL_FLASHCARD_STYLE}Show one live duck only. "
            "Full body visible in clean side view, centered, isolated, and easy to recognize instantly. "
            "Use a plain pale background and no pond, no scenery, no props, and no food presentation."
        )
    return (
        f"{ANIMAL_FLASHCARD_STYLE}Show one {label.lower()} only. "
        "Full body visible, centered, isolated, and easy to recognize instantly. "
        "Use a plain pale background and no scenery or props."
    )


def food_prompt_module(slug: str, desc: str) -> str:
    subject = food_subject_phrase(slug, desc)
    return (
        f"A single {subject}, product photography, studio lighting, "
        "on plain pastel background, isolated, no person, no child, no hand, no face. "
        "Show exactly one complete food item fully inside frame. "
        f"{food_framing_phrase(slug)} "
        "Use a tight object crop with no portrait composition, no lifestyle photography, no decorative framing, and no second item. "
        "Keep the frame object-only with no people and no visible body parts. "
        "Realistic product photo, not cartoon, not illustration, not animation. "
        f"{food_positioning_phrase(slug)}"
    )


def body_prompt_module(label: str) -> str:
    """Macro photography prompts for body parts — NO illustration/cartoon style."""
    label_lower = label.lower()
    body_macro_prompts = {
        "eye": (
            "A close-up macro photograph of a single human eye, iris detail clearly visible, "
            "studio lighting, on plain pastel blue background, no face, no other features, just one eye isolated"
        ),
        "ear": (
            "A close-up macro photograph of a single human ear, studio lighting, "
            "on plain pastel background, no face, no head shape, isolated ear only"
        ),
        "nose": (
            "A close-up photograph of a single human nose, studio lighting, "
            "on plain pastel background, no face, no eyes, no mouth, isolated nose only"
        ),
        "mouth": (
            "A close-up macro photograph of a single child's mouth with lips only, "
            "smooth soft natural skin, no teeth visible, no facial hair, no skin texture, "
            "studio lighting, on plain pastel background, no face, no eyes, no nose, isolated mouth only"
        ),
        "hand": (
            "A photograph of a single open human hand, palm facing camera, studio lighting, "
            "on plain pastel background, no arm, no wrist, no face, isolated hand only"
        ),
        "foot": (
            "A macro photograph of a single child's foot, side view, clean smooth natural skin, "
            "soft natural skin tone, studio lighting, "
            "on plain pastel background, no leg, no ankle, no person, isolated foot only"
        ),
        "arm": (
            "A photograph of a single human arm from shoulder to hand, studio lighting, "
            "on plain pastel background, no face, no torso, isolated arm only"
        ),
    }
    if label_lower in body_macro_prompts:
        return body_macro_prompts[label_lower]
    return (
        f"A close-up macro photograph of a single human {label_lower}, studio lighting, "
        "on plain pastel background, no face, no person, isolated"
    )


def home_object_prompt_module(label: str) -> str:
    return (
        f"A single {label.lower()}, product photography, studio lighting, "
        "on plain pastel background, isolated, no person, no child, no hand, no face. "
        "Center the object and keep it very easy to identify at a glance. "
        "Realistic product photo, not cartoon, not illustration, not animation."
    )


def action_prompt_module(label: str, desc: str) -> str:
    return (
        f"A simple cute cartoon illustration of one Chinese preschool child clearly demonstrating the action '{label}'. "
        f"Scene: {desc}. "
        "Show exactly one child and exactly one body, full body visible, mid-action, with no second child and no repeated figure anywhere. "
        "Use a clear side-view cartoon composition so the motion reads instantly. "
        "Use simple plain clothing with no logos and a very simple uncluttered setting with no border or poster frame. "
        "Keep the action itself as the only thing that matters."
    )


def generic_vocab_prompt_module(desc: str) -> str:
    return (
        f"Show {desc}. "
        "Keep the composition simple, centered, and very easy to understand instantly."
    )


def phrase_shared_base(label: str, desc: str) -> str:
    return (
        f"{FLASHCARD_STYLE}Create a clear scene illustration for a kids English flashcard. "
        f"The sentence to teach is '{label}'. "
        f"Show this literally in one easy-to-read moment: {desc}. "
    )


def phrase_scene_module() -> str:
    return (
        "Use Chinese children. If more than one person is needed, use a Chinese parent and child so the toddler can understand instantly. "
        "Keep the scene simple, with no background clutter, and make the key action or feeling obvious. "
        f"{FLASHCARD_NEGATIVE}"
    )


def adjective_shared_base(label: str, idea: str) -> str:
    return (
        f"{FLASHCARD_STYLE}Teach the adjective '{label}' with simple geometry on a plain background. "
        f"Scene: {idea} "
    )


def adjective_scene_module() -> str:
    return (
        "Use the absolute simplest shapes possible with no decoration or realism. "
        "A bright, obvious arrow points directly at the target. "
        "Keep the background completely plain pastel with no other elements. "
        f"{FLASHCARD_NEGATIVE}"
    )


def animal_retry_prompt_module(label: str) -> str:
    if label.lower() == "fish":
        return (
            "A single cheerful fish swimming upward at a playful angle through bright water, body in a lively S-curve. "
            "Shown in side view, large and centered in frame, with full body, spread tail, fins, big eye with highlight, and a cute smile. "
            "The fish looks happy, energetic, and dynamic — fins spread wide, a few cheerful bubbles trailing. "
            "Vibrant warm orange or coral body with bright accent stripes, on a bright sky-blue background. No plants, no rocks, no seaweed. "
            "No plate, no bowl, no tray, no cutting board, no ice, no garnish, and no props. "
            "Use flat 2D cartoon shapes, thick bold outlines, rounded fins, friendly face, and smooth cel shading. "
            "Not a goldfish, not a fancy ornamental fish, and not a toy-like fish. "
            "No dead fish, no fish lying on its side motionless, no taxidermy, no specimen."
        )
    if label.lower() == "chicken":
        return (
            "Create one animation-style illustration of a single live hen. "
            "Show one full hen, centered and large in frame, on an empty pale background. "
            "Keep the body clear, simple, and isolated, with no scenery, no props, and no food presentation."
        )
    if label.lower() == "duck":
        return (
            "Create one animation-style illustration of a single live duck. "
            "Show one full duck in side view, centered and large in frame, on an empty pale background. "
            "Keep the body clear, simple, and isolated, with no pond, no scenery, no props, and no food presentation."
        )
    return (
        f"Create one cute animation-style illustration of a single {label}. "
        "Show one full animal, centered and large in frame, on an empty pastel background. "
        "Keep the shape clear, simple, cute, and isolated, with no scenery or props."
    )


def food_retry_prompt_module(slug: str, desc: str) -> str:
    return (
        f"A single {food_subject_phrase(slug, desc)}, product photography, studio lighting, "
        "on plain white background, isolated, no person, no child, no hand, no face, no people. "
        "Show exactly one food item centered in frame on a seamless empty pale background. "
        f"{food_framing_phrase(slug)} "
        "Realistic product photo, not cartoon, not illustration, not animation. "
        "Use zero humans, zero faces, zero hands, zero dishes, and zero tables. "
        f"{food_positioning_phrase(slug)}"
    )


def generic_object_retry_prompt_module(label: str) -> str:
    return (
        f"A single {label}, product photography, studio lighting, "
        "on plain white background, isolated, no person, no child, no hand, no face, no people. "
        "Show one object, large and centered, on an empty plain background. "
        "Realistic product photo, not cartoon, not illustration, not animation. "
        "Keep it simple, isolated, and free of extra objects or scenery."
    )


@dataclass(frozen=True)
class AssetSpec:
    slug: str
    prompt: str
    out_dir: Path
    filename: str
    asset_type: str
    label: str
    query: str

    @property
    def out_path(self) -> Path:
        return self.out_dir / self.filename


@dataclass(frozen=True)
class ReviewResult:
    slug: str
    passed: bool
    score: int
    reason: str
    issues: tuple[str, ...]
    reviewer: str
    reviewed_at: str


def review_error_result(slug: str, reviewer: str, reason: str) -> ReviewResult:
    return ReviewResult(
        slug=slug,
        passed=False,
        score=0,
        reason=reason,
        issues=("review_error",),
        reviewer=reviewer,
        reviewed_at=now_iso(),
    )


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def title_case_slug(slug: str) -> str:
    if slug in PHRASE_LABEL_OVERRIDES:
        return PHRASE_LABEL_OVERRIDES[slug]
    return slug.replace("_", " ").title()


def clean_query(query: str) -> str:
    return query.replace(" photo", "").strip()


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def parse_expected_assets_from_index(index_path: Path = INDEX_PATH) -> dict[str, set[str]]:
    html = index_path.read_text(encoding="utf-8")
    vocab: set[str] = set()
    for block in re.findall(r"literalWords\(\[(.*?)\]\)", html, flags=re.DOTALL):
        for label in re.findall(r"'([^']+)'", block):
            vocab.add(slugify(label))

    adjectives = {slugify(label) for label in re.findall(r"\badj\('([^']+)'\)", html)}
    phrases = {
        slug
        for slug in re.findall(
            r"phraseItem\((?:'[^']*'|\"[^\"]*\")\s*,\s*'[^']+'\s*,\s*'([^']+)'\)",
            html,
        )
    }
    return {
        "vocab": vocab,
        "adjectives": adjectives,
        "phrases": phrases,
    }


def expected_stage_map() -> dict[str, set[str]]:
    return {
        "vocab": {slug for slug in WORD_SELECTIONS},
        "adjectives": {slug for slug in ADJ_SELECTIONS},
        "phrases": {slug for slug in PHRASE_SELECTIONS},
    }


def assert_catalog_matches_index() -> None:
    index_map = parse_expected_assets_from_index()
    catalog_map = expected_stage_map()
    mismatches: list[str] = []
    for stage, expected in index_map.items():
        missing = sorted(expected - catalog_map[stage])
        extra = sorted(catalog_map[stage] - expected)
        if missing or extra:
            parts = [f"stage={stage}"]
            if missing:
                parts.append(f"missing={missing}")
            if extra:
                parts.append(f"extra={extra}")
            mismatches.append(", ".join(parts))
    if mismatches:
        raise SystemExit("Catalog/index mismatch: " + " | ".join(mismatches))


def review_manifest_path(stage: str) -> Path:
    return MANIFEST_DIR / f"{stage}_review.json"


def parse_review_payload(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        payload = raw
    else:
        text = raw if isinstance(raw, str) else json.dumps(raw)
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise ValueError(f"Reviewer did not return JSON: {text!r}")
        payload = json.loads(match.group(0))

    issues = payload.get("issues") or []
    if not isinstance(issues, list):
        issues = [str(issues)]

    return {
        "pass": bool(payload.get("pass")),
        "score": max(0, min(100, int(payload.get("score", 0)))),
        "reason": str(payload.get("reason", "")).strip() or "No reason provided",
        "issues": [str(item).strip() for item in issues if str(item).strip()],
    }


def grayscale_band_mean(image: Image.Image, *, axis: str, center: int, half_width: int) -> float:
    if axis not in {"x", "y"}:
        raise ValueError(f"Unsupported axis: {axis}")
    grayscale = ImageOps.grayscale(image)
    if axis == "x":
        left = max(0, center - half_width)
        right = min(grayscale.width, center + half_width + 1)
        band = grayscale.crop((left, 0, right, grayscale.height))
    else:
        top = max(0, center - half_width)
        bottom = min(grayscale.height, center + half_width + 1)
        band = grayscale.crop((0, top, grayscale.width, bottom))
    return float(band.resize((1, 1), Image.Resampling.BILINEAR).getpixel((0, 0)))


def axis_brightness_profile(image: Image.Image, *, axis: str) -> list[int]:
    if axis not in {"x", "y"}:
        raise ValueError(f"Unsupported axis: {axis}")
    grayscale = ImageOps.grayscale(image)
    if axis == "x":
        return [
            grayscale.crop((position, 0, position + 1, grayscale.height)).resize((1, 1), Image.Resampling.BILINEAR).getpixel((0, 0))
            for position in range(grayscale.width)
        ]
    return [
        grayscale.crop((0, position, grayscale.width, position + 1)).resize((1, 1), Image.Resampling.BILINEAR).getpixel((0, 0))
        for position in range(grayscale.height)
    ]


def bright_stripe_groups(
    image: Image.Image,
    *,
    axis: str,
    threshold: int = 208,
    edge_margin: int = 24,
) -> list[tuple[int, int]]:
    profile = axis_brightness_profile(image, axis=axis)
    length = len(profile)
    margin = max(edge_margin, length // 20)
    max_width = max(12, length // 32)
    groups: list[tuple[int, int]] = []
    start: int | None = None
    for index, brightness in enumerate(profile):
        if brightness >= threshold:
            if start is None:
                start = index
        elif start is not None:
            groups.append((start, index - 1))
            start = None
    if start is not None:
        groups.append((start, length - 1))

    return [
        (start_pos, end_pos)
        for start_pos, end_pos in groups
        if start_pos >= margin and end_pos < length - margin and 3 <= (end_pos - start_pos + 1) <= max_width
    ]


def framed_panel_groups(
    image: Image.Image,
    *,
    axis: str,
    threshold: int = 230,
    min_ratio: float = 0.08,
    max_ratio: float = 0.85,
) -> list[tuple[int, int]]:
    if axis not in {"x", "y"}:
        raise ValueError(f"Unsupported axis: {axis}")
    grayscale = ImageOps.grayscale(image)
    length = grayscale.width if axis == "x" else grayscale.height
    other = grayscale.height if axis == "x" else grayscale.width
    groups: list[tuple[int, int]] = []
    start: int | None = None
    last_index: int | None = None

    for index in range(length):
        bright = 0
        if axis == "x":
            for pos in range(other):
                if grayscale.getpixel((index, pos)) >= threshold:
                    bright += 1
        else:
            for pos in range(other):
                if grayscale.getpixel((pos, index)) >= threshold:
                    bright += 1

        ratio = bright / other
        if min_ratio <= ratio <= max_ratio:
            if start is None:
                start = index
            last_index = index
            continue

        if start is not None:
            groups.append((start, last_index if last_index is not None else start))
            start = None
            last_index = None

    if start is not None:
        groups.append((start, last_index if last_index is not None else start))
    return groups


def background_border_strip(image: Image.Image, *, margin_ratio: float = 0.125) -> Image.Image:
    rgb = image.convert("RGB")
    width, height = rgb.size
    margin = max(24, round(min(width, height) * margin_ratio))
    top = rgb.crop((0, 0, width, margin))
    bottom = rgb.crop((0, height - margin, width, height))
    left = rgb.crop((0, margin, margin, height - margin)).resize((margin, margin), Image.Resampling.BILINEAR)
    right = rgb.crop((width - margin, margin, width, height - margin)).resize((margin, margin), Image.Resampling.BILINEAR)
    strip = Image.new("RGB", (width * 2 + margin * 2, margin))
    strip.paste(top, (0, 0))
    strip.paste(bottom, (width, 0))
    strip.paste(left, (width * 2, 0))
    strip.paste(right, (width * 2 + margin, 0))
    return strip


def dominant_border_palette_bins(
    image: Image.Image,
    *,
    colors: int = 8,
    min_fraction: float = 0.08,
) -> int:
    strip = background_border_strip(image)
    quantized = strip.quantize(colors=colors, method=Image.Quantize.MEDIANCUT)
    histogram = quantized.histogram()
    total = sum(histogram) or 1
    return sum(1 for count in histogram if count / total >= min_fraction)


def background_edge_mean(image: Image.Image) -> float:
    strip = background_border_strip(image)
    return float(ImageStat.Stat(strip.convert("L").filter(ImageFilter.FIND_EDGES)).mean[0])


def background_color_stddev_mean(image: Image.Image) -> float:
    strip = background_border_strip(image)
    stat = ImageStat.Stat(strip)
    return sum(float(value) for value in stat.stddev) / len(stat.stddev)


def has_busy_background(image: Image.Image) -> bool:
    palette_bins = dominant_border_palette_bins(image)
    edge_mean = background_edge_mean(image)
    stddev_mean = background_color_stddev_mean(image)
    return (
        palette_bins >= 5
        or (palette_bins >= 4 and edge_mean >= 9.0)
        or (palette_bins >= 4 and stddev_mean >= 32.0)
        or (edge_mean >= 12.0 and stddev_mean >= 36.0)
    )


def requires_clean_background(spec: AssetSpec) -> bool:
    return spec.asset_type == "still" and spec.slug in (ANIMAL_WORDS | FOOD_WORDS | HOME_WORDS)


def food_subject_phrase(slug: str, desc: str) -> str:
    if slug == "grape":
        return "one complete hanging bunch of small oval translucent green grapes on a branching vine, with the stem visible"
    if slug == "cherry":
        return "one complete pair or small cluster of glossy red cherries attached together by thin stems"
    return desc


def food_positioning_phrase(slug: str) -> str:
    if slug in CLUSTER_FRUIT_WORDS:
        return (
            "The fruit is unsupported against the seamless studio background with nothing underneath it. "
            "Show the complete bunch fully inside the frame with empty margin on every side, "
            "no bowl, no plate, no table, no container, no drink, and no nearby prop."
        )
    return "Keep the frame clean with no person and no portrait staging."


def food_framing_phrase(slug: str) -> str:
    if slug == "grape":
        return (
            "The single bunch must read clearly as one whole cluster with the stem visible near the top. "
            "Keep the entire cluster inside the frame with generous plain background around it. "
            "Do not zoom in to a pile or texture of loose grapes. "
            "For grapes, each fruit should read as a small oval grape, not as apples or round fruit."
        )
    if slug == "cherry":
        return (
            "The fruit must read clearly as one attached pair or a very small cherry cluster with the stems visible. "
            "Keep the full cherries inside the frame with generous plain background around them. "
            "Do not zoom in to a repeating cherry pattern or wallpaper-like layout."
        )
    return (
        "The food item must occupy at least 80% of the frame, be centered, "
        "and be the only thing noticed first at a glance."
    )


def preserves_full_subject(spec: AssetSpec) -> bool:
    return spec.asset_type == "still" and spec.slug in CLUSTER_FRUIT_WORDS


def background_fill_color(image: Image.Image) -> tuple[int, int, int]:
    strip = background_border_strip(image)
    stat = ImageStat.Stat(strip)
    return tuple(int(round(channel)) for channel in stat.mean[:3])


def normalize_generated_image(image: Image.Image, spec: AssetSpec, *, width: int, height: int) -> Image.Image:
    rgb = image.convert("RGB")
    if preserves_full_subject(spec):
        contained = ImageOps.contain(
            rgb,
            (width, height),
            method=Image.Resampling.LANCZOS,
        )
        canvas = Image.new("RGB", (width, height), background_fill_color(rgb))
        offset = ((width - contained.width) // 2, (height - contained.height) // 2)
        canvas.paste(contained, offset)
        return canvas
    return ImageOps.fit(
        rgb,
        (width, height),
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5),
    )


def prompt_for_generation_attempt(spec: AssetSpec, *, attempt: int) -> str:
    if attempt < 3 or not requires_clean_background(spec):
        return spec.prompt
    label = spec.label.lower()
    if spec.slug in ANIMAL_WORDS:
        return animal_retry_prompt_module(label)
    if spec.slug in FOOD_WORDS:
        return food_retry_prompt_module(spec.slug, clean_query(spec.query))
    return generic_object_retry_prompt_module(label)


def line_is_panel_divider(image: Image.Image, *, axis: str, center: int) -> bool:
    line_brightness = grayscale_band_mean(image, axis=axis, center=center, half_width=4)
    before_brightness = grayscale_band_mean(image, axis=axis, center=center - 18, half_width=6)
    after_brightness = grayscale_band_mean(image, axis=axis, center=center + 18, half_width=6)
    return (
        line_brightness >= 236
        and before_brightness <= 210
        and after_brightness <= 210
        and line_brightness - max(before_brightness, after_brightness) >= 24
    )


def panel_divider_positions(image: Image.Image, *, axis: str) -> list[int]:
    length = image.width if axis == "x" else image.height
    candidates = sorted({round(length * ratio) for ratio in (0.25, 1 / 3, 0.5, 2 / 3, 0.75)})
    return [center for center in candidates if 24 <= center < length - 24 and line_is_panel_divider(image, axis=axis, center=center)]


def looks_like_multi_panel_layout(image: Image.Image) -> bool:
    vertical = panel_divider_positions(image, axis="x")
    horizontal = panel_divider_positions(image, axis="y")
    framed_vertical = framed_panel_groups(image, axis="x")
    framed_horizontal = framed_panel_groups(image, axis="y")
    return (
        (len(vertical) >= 1 and len(horizontal) >= 1)
        or len(vertical) >= 2
        or len(horizontal) >= 2
        or (len(framed_vertical) >= 6 and len(framed_horizontal) >= 6)
    )


def encode_image_data_url(path: Path) -> str:
    mime = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }.get(path.suffix.lower(), "application/octet-stream")
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def encode_review_image_data_url(path: Path) -> str:
    with Image.open(path) as image:
        image = image.convert("RGB")
        width, height = image.size
        if max(width, height) > REVIEW_IMAGE_MAX_EDGE:
            if width >= height:
                new_size = (
                    REVIEW_IMAGE_MAX_EDGE,
                    max(1, round(height * REVIEW_IMAGE_MAX_EDGE / width)),
                )
            else:
                new_size = (
                    max(1, round(width * REVIEW_IMAGE_MAX_EDGE / height)),
                    REVIEW_IMAGE_MAX_EDGE,
                )
            image = image.resize(new_size, Image.Resampling.LANCZOS)

        from io import BytesIO

        buffer = BytesIO()
        image.save(buffer, format=REVIEW_IMAGE_FORMAT, optimize=True)
    data = base64.b64encode(buffer.getvalue()).decode("ascii")
    return "data:image/png;base64," + data


def extract_message_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if text:
                    parts.append(str(text).strip())
            elif item:
                parts.append(str(item).strip())
        return "\n".join(part for part in parts if part)
    if content is None:
        return ""
    return str(content).strip()


def review_image(spec: AssetSpec, *, qa_url: str, qa_model: str, timeout: int) -> ReviewResult:
    extra_review_rule = ""
    if spec.asset_type == "still" and spec.slug in ANIMAL_WORDS:
        extra_review_rule = (
            "This is an animal vocabulary card for a 4-year-old. "
            "Fail if the image is not about the animal — if a person, another animal, or a complex scene steals focus. "
            "Do NOT fail because of background style. Fail only if the background actively confuses what to look at."
        )
    elif spec.asset_type == "still" and spec.slug in FOOD_WORDS | HOME_WORDS:
        extra_review_rule = (
            "This is a single-word vocabulary card. Reject the image if a person or extra unrelated main subject is needed to understand the scene. "
            "Reject portrait-style compositions where a child face competes with the object. Reject decorative frames, windows, or staged poster-like layouts."
        )

    payload = {
        "model": qa_model,
        "temperature": 0,
        "include_reasoning": False,
        "chat_template_kwargs": REVIEW_CHAT_TEMPLATE_KWARGS,
        "messages": [
            {"role": "system", "content": QA_PROMPT + "\nOutput exactly one JSON object and stop."},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"Label: {spec.label}\n"
                            f"Slug: {spec.slug}\n"
                            f"Query: {spec.query}\n"
                            f"Prompt: {spec.prompt}\n"
                            f"Extra review rule: {extra_review_rule or 'None'}\n"
                            "Review this image strictly for a 4-year-old learner.\n"
                            "Return the final JSON immediately. No prose, no markdown, no hidden reasoning."
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": encode_review_image_data_url(spec.out_path)},
                    },
                ],
            },
        ],
        "max_tokens": 600,
    }
    request = urlrequest.Request(
        qa_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlrequest.urlopen(request, timeout=timeout) as response:
        body = json.loads(response.read().decode("utf-8"))

    message = ((body.get("choices") or [{}])[0].get("message") or {})
    content = extract_message_text(message.get("content"))
    if not content:
        content = extract_message_text(message.get("reasoning"))
    parsed = parse_review_payload(content)
    return ReviewResult(
        slug=spec.slug,
        passed=parsed["pass"],
        score=parsed["score"],
        reason=parsed["reason"],
        issues=tuple(parsed["issues"]),
        reviewer=qa_model,
        reviewed_at=now_iso(),
    )


def load_review_manifest(stage: str) -> dict[str, ReviewResult]:
    path = review_manifest_path(stage)
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    reviews: dict[str, ReviewResult] = {}
    for slug, payload in raw.items():
        reviews[slug] = ReviewResult(
            slug=slug,
            passed=bool(payload.get("pass")),
            score=int(payload.get("score", 0)),
            reason=str(payload.get("reason", "")),
            issues=tuple(str(item) for item in payload.get("issues", [])),
            reviewer=str(payload.get("reviewer", "")),
            reviewed_at=str(payload.get("reviewed_at", "")),
        )
    return reviews


def write_review_manifest(stage: str, specs: list[AssetSpec], reviews: dict[str, ReviewResult]) -> None:
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    specs_by_slug = {spec.slug: spec for spec in specs}
    payload = {}
    for slug, review in sorted(reviews.items()):
        spec = specs_by_slug.get(slug)
        output_file = None
        if spec is not None and spec.out_path.exists():
            output_file = str(spec.out_path.relative_to(ROOT))
        payload[slug] = {
            "label": spec.label if spec else title_case_slug(slug),
            "query": spec.query if spec else "",
            "pass": review.passed,
            "score": review.score,
            "reason": review.reason,
            "issues": list(review.issues),
            "reviewer": review.reviewer,
            "reviewed_at": review.reviewed_at,
            "output_file": output_file,
        }
    review_manifest_path(stage).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def review_specs(
    *,
    stage: str,
    specs: list[AssetSpec],
    qa_url: str,
    qa_model: str,
    min_score: int,
    timeout: int,
    dry_run: bool,
    force: bool,
) -> dict[str, ReviewResult]:
    existing = {} if force else load_review_manifest(stage)
    pending = [spec for spec in specs if spec.out_path.exists() and (force or spec.slug not in existing)]
    if dry_run:
        print(f"{stage}: would review {len(pending)} assets with {qa_model} (min score {min_score})")
        return existing

    if not pending:
        print(f"{stage}: no new assets to review")
        return existing

    print(f"{stage}: reviewing {len(pending)} assets with {qa_model}")
    for spec in pending:
        try:
            existing[spec.slug] = review_image(
                spec,
                qa_url=qa_url,
                qa_model=qa_model,
                timeout=timeout,
            )
        except Exception as exc:
            reason = f"review request failed: {exc}"
            print(f"{stage}:{spec.slug}: {reason}")
            existing[spec.slug] = review_error_result(spec.slug, qa_model, reason)
    write_review_manifest(stage, specs, existing)
    return existing


def generated_stage_map() -> dict[str, set[str]]:
    return {
        "vocab": {path.stem for path in WORD_DIR.glob(f"*{WORD_EXT}")},
        "adjectives": {path.stem for path in ADJ_DIR.glob(f"*{WORD_EXT}")},
        "phrases": {path.stem for path in PHRASE_DIR.glob(f"*{PHRASE_EXT}")},
    }


def build_audit_report(
    *,
    expected: dict[str, set[str]],
    actual: dict[str, set[str]],
    reviews: dict[str, dict[str, ReviewResult]],
    min_score: int,
) -> dict[str, Any]:
    stages: dict[str, dict[str, Any]] = {}
    ok = True
    for stage, wanted in expected.items():
        present = actual.get(stage, set())
        stage_reviews = reviews.get(stage, {})
        missing = sorted(wanted - present)
        unreviewed = sorted(slug for slug in wanted & present if slug not in stage_reviews)
        failed = sorted(slug for slug in wanted & present if slug in stage_reviews and not stage_reviews[slug].passed)
        low_score = sorted(
            slug
            for slug in wanted & present
            if slug in stage_reviews and stage_reviews[slug].score < min_score
        )
        stage_ok = not (missing or unreviewed or failed or low_score)
        ok = ok and stage_ok
        stages[stage] = {
            "ok": stage_ok,
            "missing": missing,
            "unreviewed": unreviewed,
            "failed": failed,
            "low_score": low_score,
        }
    return {"ok": ok, "stages": stages}


def run_audit(*, min_score: int) -> dict[str, Any]:
    report = build_audit_report(
        expected=expected_stage_map(),
        actual=generated_stage_map(),
        reviews={
            "vocab": load_review_manifest("vocab"),
            "adjectives": load_review_manifest("adjectives"),
            "phrases": load_review_manifest("phrases"),
        },
        min_score=min_score,
    )
    for stage, details in report["stages"].items():
        if details["ok"]:
            print(f"audit:{stage}: ok")
            continue
        print(
            "audit:{stage}: missing={missing} unreviewed={unreviewed} failed={failed} low_score={low_score}".format(
                stage=stage,
                missing=details["missing"],
                unreviewed=details["unreviewed"],
                failed=details["failed"],
                low_score=details["low_score"],
            )
        )
    return report


def word_prompt(slug: str, query: str) -> str:
    label = title_case_slug(slug)
    desc = clean_query(query)
    shared = vocab_shared_base()

    if slug in ANIMAL_WORDS:
        return animal_prompt_module(label)
    if slug in FOOD_WORDS:
        return food_prompt_module(slug, desc)
    if slug in BODY_WORDS:
        return body_prompt_module(label)
    if slug in HOME_WORDS:
        return home_object_prompt_module(label)
    if slug in ACTION_WORDS:
        return f"{shared}{action_prompt_module(label, desc)}"
    return f"{shared}{generic_vocab_prompt_module(desc)}"


def adjective_prompt(slug: str, query: str) -> str:
    label = title_case_slug(slug)
    idea = ADJ_PROMPTS.get(slug, clean_query(query))
    return f"{adjective_shared_base(label, idea)}{adjective_scene_module()}"


def phrase_prompt(slug: str, query: str) -> str:
    label = title_case_slug(slug)
    desc = clean_query(query)
    return f"{phrase_shared_base(label, desc)}{phrase_scene_module()}"


def build_word_specs() -> list[AssetSpec]:
    return [
        AssetSpec(
            slug=slug,
            prompt=word_prompt(slug, str(config["query"])),
            out_dir=WORD_DIR,
            filename=f"{slug}{WORD_EXT}",
            asset_type="still",
            label=title_case_slug(slug),
            query=str(config["query"]),
        )
        for slug, config in WORD_SELECTIONS.items()
    ]


def build_adj_specs() -> list[AssetSpec]:
    return [
        AssetSpec(
            slug=slug,
            prompt=adjective_prompt(slug, str(config["query"])),
            out_dir=ADJ_DIR,
            filename=f"{slug}{WORD_EXT}",
            asset_type="still",
            label=title_case_slug(slug),
            query=str(config["query"]),
        )
        for slug, config in ADJ_SELECTIONS.items()
    ]


def build_phrase_specs() -> list[AssetSpec]:
    return [
        AssetSpec(
            slug=slug,
            prompt=phrase_prompt(slug, str(config["query"])),
            out_dir=PHRASE_DIR,
            filename=f"{slug}{PHRASE_EXT}",
            asset_type="still",
            label=title_case_slug(slug),
            query=str(config["query"]),
        )
        for slug, config in PHRASE_SELECTIONS.items()
    ]


def select_specs(specs: list[AssetSpec], *, limit: int | None, force: bool) -> list[AssetSpec]:
    selected = [spec for spec in specs if force or not spec.out_path.exists()]
    if limit is not None:
        selected = selected[:limit]
    return selected


def write_jobs_file(path: Path, specs: Iterable[AssetSpec]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for spec in specs:
            handle.write(json.dumps({"prompt": spec.prompt, "out": spec.filename}, ensure_ascii=True))
            handle.write("\n")
            count += 1
    return count


def run_batch(
    *,
    name: str,
    specs: list[AssetSpec],
    generator: str,
    model: str,
    quality: str,
    size: str,
    concurrency: int,
    max_attempts: int,
    dry_run: bool,
    force: bool,
    gate_on_review: bool,
    review_url: str,
    review_model: str,
    review_timeout: int,
    min_score: int,
) -> None:
    if not specs:
        print(f"{name}: nothing to generate")
        return
    if generator != "comfyui":
        raise ValueError(f"Unsupported generator backend: {generator}")

    print(f"{name}: generating {len(specs)} assets with {generator}:{model}")
    for spec in specs:
        generate_local_asset(
            spec=spec,
            checkpoint=model,
            size=size,
            max_attempts=max_attempts,
            dry_run=dry_run,
            force=force,
            gate_on_review=gate_on_review,
            review_url=review_url,
            review_model=review_model,
            review_timeout=review_timeout,
            min_score=min_score,
        )


def parse_size(size: str) -> tuple[int, int]:
    match = re.fullmatch(r"(\d+)x(\d+)", size)
    if not match:
        raise ValueError(f"Invalid size: {size}")
    return int(match.group(1)), int(match.group(2))


def is_flux2_klein_checkpoint(checkpoint: str) -> bool:
    return checkpoint == FLUX2_KLEIN_CHECKPOINT


def build_flux2_klein_workflow(
    *,
    spec: AssetSpec,
    width: int,
    height: int,
    seed: int,
    negative: str,
) -> dict[str, Any]:
    return {
        "61": {
            "class_type": "KSamplerSelect",
            "inputs": {"sampler_name": "euler"},
        },
        "62": {
            "class_type": "Flux2Scheduler",
            "inputs": {"steps": 20, "width": width, "height": height},
        },
        "63": {
            "class_type": "CFGGuider",
            "inputs": {
                "model": ["64", 0],
                "positive": ["65", 0],
                "negative": ["69", 0],
                "cfg": 5,
            },
        },
        "64": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": FLUX2_KLEIN_CHECKPOINT,
                "weight_dtype": "default",
            },
        },
        "65": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "clip": ["67", 0],
                "text": spec.prompt,
            },
        },
        "66": {
            "class_type": "EmptyFlux2LatentImage",
            "inputs": {"width": width, "height": height, "batch_size": 1},
        },
        "67": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": FLUX2_KLEIN_TEXT_ENCODER,
                "type": "flux2",
                "device": "default",
            },
        },
        "68": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": FLUX2_VAE},
        },
        "69": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "clip": ["67", 0],
                "text": negative,
            },
        },
        "70": {
            "class_type": "RandomNoise",
            "inputs": {"noise_seed": seed},
        },
        "71": {
            "class_type": "SamplerCustomAdvanced",
            "inputs": {
                "noise": ["70", 0],
                "guider": ["63", 0],
                "sampler": ["61", 0],
                "sigmas": ["62", 0],
                "latent_image": ["66", 0],
            },
        },
        "72": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["71", 0], "vae": ["68", 0]},
        },
        "73": {
            "class_type": "SaveImage",
            "inputs": {
                "images": ["72", 0],
                "filename_prefix": f"kids_flashcards_{spec.slug}",
            },
        },
    }


def build_comfyui_workflow(*, spec: AssetSpec, checkpoint: str, width: int, height: int, seed: int, negative: str | None = None) -> dict[str, Any]:
    steps = 36
    cfg = 7.5
    neg_text = negative if negative is not None else FLASHCARD_ARTIFACT_NEGATIVE
    if is_flux2_klein_checkpoint(checkpoint):
        return build_flux2_klein_workflow(
            spec=spec,
            width=width,
            height=height,
            seed=seed,
            negative=neg_text,
        )
    return {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": checkpoint},
        },
        "2": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": spec.prompt, "clip": ["1", 1]},
        },
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": neg_text,
                "clip": ["1", 1],
            },
        },
        "4": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": width, "height": height, "batch_size": 1},
        },
        "5": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0],
                "positive": ["2", 0],
                "negative": ["3", 0],
                "latent_image": ["4", 0],
                "seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": "dpmpp_2m",
                "scheduler": "karras",
                "denoise": 1.0,
            },
        },
        "6": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["5", 0], "vae": ["1", 2]},
        },
        "7": {
            "class_type": "SaveImage",
            "inputs": {
                "images": ["6", 0],
                "filename_prefix": f"kids_flashcards_{spec.slug}",
            },
        },
    }


def negative_prompt_for_spec(spec: AssetSpec) -> str | None:
    if spec.slug == "fish":
        return FLASHCARD_FISH_NEGATIVE
    if spec.slug in ANIMAL_WORDS:
        return FLASHCARD_ANIMAL_NEGATIVE
    if spec.slug in FOOD_WORDS:
        return FLASHCARD_FOOD_NEGATIVE
    if spec.slug in HOME_WORDS:
        return FLASHCARD_HOME_NEGATIVE
    if spec.slug in BODY_WORDS:
        return FLASHCARD_BODY_NEGATIVE
    if spec.slug in ACTION_WORDS:
        return FLASHCARD_ACTION_NEGATIVE
    if spec.slug in ADJ_SELECTIONS:
        return FLASHCARD_ADJ_NEGATIVE
    return None


def comfyui_json_request(url: str, payload: dict[str, Any] | None = None, *, timeout: int = 30) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urlrequest.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST" if payload is not None else "GET",
    )
    with urlrequest.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def ensure_comfyui_ready(checkpoint: str, *, timeout: int = 10) -> None:
    try:
        stats = comfyui_json_request(f"{COMFYUI_URL}/system_stats", None, timeout=timeout)
        if is_flux2_klein_checkpoint(checkpoint):
            unet_info = comfyui_json_request(
                f"{COMFYUI_URL}/object_info/UNETLoader",
                None,
                timeout=timeout,
            )
            clip_info = comfyui_json_request(
                f"{COMFYUI_URL}/object_info/CLIPLoader",
                None,
                timeout=timeout,
            )
            vae_info = comfyui_json_request(
                f"{COMFYUI_URL}/object_info/VAELoader",
                None,
                timeout=timeout,
            )
        else:
            checkpoint_info = comfyui_json_request(
                f"{COMFYUI_URL}/object_info/CheckpointLoaderSimple",
                None,
                timeout=timeout,
            )
    except (urlerror.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise SystemExit(f"ComfyUI not ready at {COMFYUI_URL}: {exc}") from exc

    if not stats.get("devices"):
        raise SystemExit(f"ComfyUI reported no devices at {COMFYUI_URL}")

    if is_flux2_klein_checkpoint(checkpoint):
        unets = (
            unet_info.get("UNETLoader", {})
            .get("input", {})
            .get("required", {})
            .get("unet_name", [[]])[0]
        )
        clips = (
            clip_info.get("CLIPLoader", {})
            .get("input", {})
            .get("required", {})
            .get("clip_name", [[]])[0]
        )
        vaes = (
            vae_info.get("VAELoader", {})
            .get("input", {})
            .get("required", {})
            .get("vae_name", [[]])[0]
        )
        missing = []
        if checkpoint not in unets:
            missing.append(f"unet={checkpoint}")
        if FLUX2_KLEIN_TEXT_ENCODER not in clips:
            missing.append(f"clip={FLUX2_KLEIN_TEXT_ENCODER}")
        if FLUX2_VAE not in vaes:
            missing.append(f"vae={FLUX2_VAE}")
        if missing:
            raise SystemExit(
                "Flux.2 Klein models not available in ComfyUI at "
                f"{COMFYUI_URL}: {', '.join(missing)}"
            )
        return

    checkpoints = (
        checkpoint_info.get("CheckpointLoaderSimple", {})
        .get("input", {})
        .get("required", {})
        .get("ckpt_name", [[]])[0]
    )
    if checkpoint not in checkpoints:
        raise SystemExit(
            f"Checkpoint '{checkpoint}' not available in ComfyUI at {COMFYUI_URL}. "
            f"Available: {sorted(checkpoints)}"
        )


def qa_models_url(qa_url: str) -> str:
    if qa_url.endswith("/chat/completions"):
        return qa_url[: -len("/chat/completions")] + "/models"
    return qa_url.rstrip("/") + "/models"


def ensure_review_model_ready(qa_url: str, qa_model: str, *, timeout: int = 10) -> bool:
    models_url = qa_models_url(qa_url)
    try:
        payload = comfyui_json_request(models_url, None, timeout=timeout)
    except (urlerror.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"Review model endpoint not ready at {models_url}: {exc}")
        return False

    models = {item.get("id") for item in payload.get("data", []) if isinstance(item, dict)}
    if qa_model not in models:
        print(
            f"Review model '{qa_model}' not available at {models_url}. "
            f"Available: {sorted(models)}"
        )
        return False
    return True


def ensure_stage_dependencies(args: argparse.Namespace, stages: set[str]) -> None:
    if args.dry_run:
        return
    if {"words", "adjs", "phrases"} & stages:
        ensure_comfyui_ready(args.model)
    if "review" in stages:
        if not ensure_review_model_ready(args.review_url, args.review_model):
            raise SystemExit(
                f"Review model '{args.review_model}' not ready at {qa_models_url(args.review_url)}"
            )


def comfyui_submit(workflow: dict[str, Any]) -> str:
    response = comfyui_json_request(f"{COMFYUI_URL}/prompt", {"prompt": workflow})
    prompt_id = response.get("prompt_id")
    if not prompt_id:
        raise RuntimeError(f"ComfyUI submit error: {response}")
    return str(prompt_id)


def comfyui_wait(prompt_id: str, *, timeout: int = COMFYUI_TIMEOUT) -> dict[str, Any]:
    start = time.time()
    while time.time() - start < timeout:
        history = comfyui_json_request(f"{COMFYUI_URL}/history/{prompt_id}", None, timeout=10)
        if prompt_id in history:
            entry = history[prompt_id]
            status = entry.get("status", {})
            if status.get("completed", True):
                return entry
        time.sleep(COMFYUI_POLL)
    raise TimeoutError(f"ComfyUI prompt {prompt_id} timed out after {timeout}s")


def comfyui_download_outputs(history: dict[str, Any], output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []
    for node_output in history.get("outputs", {}).values():
        for item in node_output.get("images", []):
            filename = str(item["filename"])
            subfolder = str(item.get("subfolder", ""))
            file_type = str(item.get("type", "output"))
            url = (
                f"{COMFYUI_URL}/view?"
                f"filename={filename}&subfolder={subfolder}&type={file_type}"
            )
            with urlrequest.urlopen(url, timeout=60) as response:
                out_path = output_dir / filename
                out_path.write_bytes(response.read())
                files.append(out_path)
    return files


def generate_local_asset(
    *,
    spec: AssetSpec,
    checkpoint: str,
    size: str,
    max_attempts: int,
    dry_run: bool,
    force: bool,
    gate_on_review: bool,
    review_url: str,
    review_model: str,
    review_timeout: int,
    min_score: int,
) -> None:
    if spec.out_path.exists() and not force:
        return
    if dry_run:
        print(f"  dry-run generate {spec.slug} -> {spec.out_path.name}")
        return

    width, height = parse_size(size)
    spec.out_dir.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, max_attempts + 1):
        seed = int.from_bytes(os.urandom(4), "big")
        tmp_dir = TMP_DIR / spec.slug / f"attempt-{attempt}"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        attempt_spec = replace(spec, prompt=prompt_for_generation_attempt(spec, attempt=attempt))
        try:
            neg = negative_prompt_for_spec(spec)
            workflow = build_comfyui_workflow(
                spec=attempt_spec,
                checkpoint=checkpoint,
                width=width,
                height=height,
                seed=seed,
                negative=neg,
            )
            prompt_id = comfyui_submit(workflow)
            history = comfyui_wait(prompt_id)
            files = comfyui_download_outputs(history, tmp_dir)
            if not files:
                raise RuntimeError("ComfyUI produced no image outputs")
            raw_path = max(files, key=lambda path: path.stat().st_size)
            with Image.open(raw_path) as image:
                image = normalize_generated_image(image, spec, width=width, height=height)
                if not is_flux2_klein_checkpoint(checkpoint) and looks_like_multi_panel_layout(image):
                    raise RuntimeError("generated image looks like a multi-panel layout")
                review_path = tmp_dir / f"{spec.slug}-review.png"
                image.save(review_path, format="PNG", optimize=True)
            if gate_on_review:
                review_spec = AssetSpec(
                    slug=attempt_spec.slug,
                    prompt=attempt_spec.prompt,
                    out_dir=tmp_dir,
                    filename=review_path.name,
                    asset_type=attempt_spec.asset_type,
                    label=attempt_spec.label,
                    query=attempt_spec.query,
                )
                review = review_image(
                    review_spec,
                    qa_url=review_url,
                    qa_model=review_model,
                    timeout=review_timeout,
                )
                if not review.passed or review.score < min_score:
                    raise RuntimeError(
                        f"review gate rejected image: score={review.score} pass={review.passed} reason={review.reason}"
                    )
            spec.out_path.parent.mkdir(parents=True, exist_ok=True)
            review_path.replace(spec.out_path)
            return
        except Exception as exc:
            if attempt == max_attempts:
                raise RuntimeError(f"{spec.slug}: local generation failed after {max_attempts} attempts") from exc
        finally:
            if tmp_dir.exists():
                subprocess.run(["rm", "-rf", str(tmp_dir)], check=False)


def frame_window(slug: str, index: int) -> tuple[float, float, float]:
    seed = sum(ord(ch) for ch in slug) % 3
    start_x = [0.48, 0.42, 0.58][seed]
    start_y = [0.48, 0.44, 0.52][seed]
    dx = [-0.04, 0.05, -0.03][seed]
    dy = [0.03, -0.02, 0.04][seed]
    zooms = [1.00, 1.06, 1.02]
    x = max(0.0, min(1.0, start_x + dx * index))
    y = max(0.0, min(1.0, start_y + dy * index))
    return x, y, zooms[index]


def render_motion_frame(image: Image.Image, slug: str, index: int, size: int) -> Image.Image:
    x_center, y_center, zoom = frame_window(slug, index)
    source = ImageOps.fit(image, (size, size), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    if zoom <= 1.0:
        return source

    enlarged = source.resize(
        (int(round(size * zoom)), int(round(size * zoom))),
        resample=Image.Resampling.LANCZOS,
    )
    max_x = max(0, enlarged.width - size)
    max_y = max(0, enlarged.height - size)
    left = int(round(max_x * x_center))
    top = int(round(max_y * y_center))
    left = max(0, min(left, max_x))
    top = max(0, min(top, max_y))
    return enlarged.crop((left, top, left + size, top + size))


def assemble_phrase_gifs(*, force: bool, gif_size: int) -> None:
    PHRASE_GIF_DIR.mkdir(parents=True, exist_ok=True)
    PHRASE_FRAME_DIR.mkdir(parents=True, exist_ok=True)

    for slug in PHRASE_SELECTIONS:
        still_path = PHRASE_DIR / f"{slug}{PHRASE_EXT}"
        gif_path = PHRASE_GIF_DIR / f"{slug}{GIF_EXT}"
        if not still_path.exists():
            continue
        if gif_path.exists() and not force:
            continue

        with Image.open(still_path) as source:
            source = source.convert("RGB")
            frames: list[Image.Image] = []
            frame_paths: list[Path] = []
            for index in range(3):
                frame = render_motion_frame(source, slug, index, gif_size)
                frame_path = PHRASE_FRAME_DIR / f"{slug}-{index + 1}{WORD_EXT}"
                frame.save(frame_path, quality=88, optimize=True)
                frames.append(frame.convert("P", palette=Image.Palette.ADAPTIVE, colors=128))
                frame_paths.append(frame_path)

            frames[0].save(
                gif_path,
                save_all=True,
                append_images=frames[1:],
                duration=[320, 320, 420],
                loop=0,
                optimize=True,
                disposal=2,
            )

            for frame in frames:
                frame.close()


def write_still_manifest(out_dir: Path, specs: list[AssetSpec], reviews: dict[str, ReviewResult] | None = None) -> None:
    manifest = {}
    timestamp = now_iso()
    reviews = reviews or {}
    for spec in specs:
        if not spec.out_path.exists():
            continue
        review = reviews.get(spec.slug)
        manifest[spec.slug] = {
            "label": spec.label,
            "query": spec.query,
            "prompt": spec.prompt,
            "asset_type": spec.asset_type,
            "frames": [],
            "output_file": str(spec.out_path.relative_to(ROOT)),
            "generated_at": timestamp,
            "review": None if review is None else {
                "pass": review.passed,
                "score": review.score,
                "reason": review.reason,
                "issues": list(review.issues),
                "reviewer": review.reviewer,
                "reviewed_at": review.reviewed_at,
            },
        }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def write_phrase_gif_manifest(phrase_specs: list[AssetSpec]) -> None:
    manifest = {}
    timestamp = now_iso()
    for spec in phrase_specs:
        gif_path = PHRASE_GIF_DIR / f"{spec.slug}{GIF_EXT}"
        if not gif_path.exists():
            continue
        frames = [
            str((PHRASE_FRAME_DIR / f"{spec.slug}-{index}{WORD_EXT}").relative_to(ROOT))
            for index in range(1, 4)
        ]
        manifest[spec.slug] = {
            "label": spec.label,
            "query": spec.query,
            "prompt": spec.prompt,
            "asset_type": "gif",
            "frames": frames,
            "output_file": str(gif_path.relative_to(ROOT)),
            "generated_at": timestamp,
        }
    (PHRASE_GIF_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate and review AI-only flashcard images and GIFs")
    parser.add_argument(
        "--only",
        default="words,adjs,phrases,review,manifests,audit",
        help="Comma-separated stages: words,adjs,phrases,review,gifs,manifests,audit",
    )
    parser.add_argument("--limit", type=int, help="Generate only the first N missing stills per stage")
    parser.add_argument("--generator", default=DEFAULT_GENERATOR, choices=["comfyui"])
    parser.add_argument("--model", default=DEFAULT_CHECKPOINT)
    parser.add_argument("--quality", default="medium")
    parser.add_argument("--size", default="1024x1024")
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--max-attempts", type=int, default=4)
    parser.add_argument("--gif-size", type=int, default=768)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--review-url", default=DEFAULT_QA_URL)
    parser.add_argument("--review-model", default=DEFAULT_QA_MODEL)
    parser.add_argument("--min-score", type=int, default=DEFAULT_QA_MIN_SCORE)
    parser.add_argument("--review-timeout", type=int, default=120)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    assert_catalog_matches_index()
    stages = {part.strip() for part in args.only.split(",") if part.strip()}
    ensure_stage_dependencies(args, stages)

    word_specs = build_word_specs()
    adj_specs = build_adj_specs()
    phrase_specs = build_phrase_specs()
    gate_on_review = "review" in stages and not args.dry_run and ensure_review_model_ready(args.review_url, args.review_model)

    if "words" in stages:
        run_batch(
            name="words",
            specs=select_specs(word_specs, limit=args.limit, force=args.force),
            generator=args.generator,
            model=args.model,
            quality=args.quality,
            size=args.size,
            concurrency=args.concurrency,
            max_attempts=args.max_attempts,
            dry_run=args.dry_run,
            force=args.force,
            gate_on_review=gate_on_review,
            review_url=args.review_url,
            review_model=args.review_model,
            review_timeout=args.review_timeout,
            min_score=args.min_score,
        )
    if "adjs" in stages:
        run_batch(
            name="adjs",
            specs=select_specs(adj_specs, limit=args.limit, force=args.force),
            generator=args.generator,
            model=args.model,
            quality=args.quality,
            size=args.size,
            concurrency=args.concurrency,
            max_attempts=args.max_attempts,
            dry_run=args.dry_run,
            force=args.force,
            gate_on_review=gate_on_review,
            review_url=args.review_url,
            review_model=args.review_model,
            review_timeout=args.review_timeout,
            min_score=args.min_score,
        )
    if "phrases" in stages:
        run_batch(
            name="phrases",
            specs=select_specs(phrase_specs, limit=args.limit, force=args.force),
            generator=args.generator,
            model=args.model,
            quality=args.quality,
            size=args.size,
            concurrency=args.concurrency,
            max_attempts=args.max_attempts,
            dry_run=args.dry_run,
            force=args.force,
            gate_on_review=gate_on_review,
            review_url=args.review_url,
            review_model=args.review_model,
            review_timeout=args.review_timeout,
            min_score=args.min_score,
        )
    word_reviews = load_review_manifest("vocab")
    adj_reviews = load_review_manifest("adjectives")
    phrase_reviews = load_review_manifest("phrases")
    if "review" in stages:
        word_reviews = review_specs(
            stage="vocab",
            specs=word_specs,
            qa_url=args.review_url,
            qa_model=args.review_model,
            min_score=args.min_score,
            timeout=args.review_timeout,
            dry_run=args.dry_run,
            force=args.force,
        )
        adj_reviews = review_specs(
            stage="adjectives",
            specs=adj_specs,
            qa_url=args.review_url,
            qa_model=args.review_model,
            min_score=args.min_score,
            timeout=args.review_timeout,
            dry_run=args.dry_run,
            force=args.force,
        )
        phrase_reviews = review_specs(
            stage="phrases",
            specs=phrase_specs,
            qa_url=args.review_url,
            qa_model=args.review_model,
            min_score=args.min_score,
            timeout=args.review_timeout,
            dry_run=args.dry_run,
            force=args.force,
        )
    if "gifs" in stages and not args.dry_run:
        assemble_phrase_gifs(force=args.force, gif_size=args.gif_size)
    if "manifests" in stages and not args.dry_run:
        WORD_DIR.mkdir(parents=True, exist_ok=True)
        ADJ_DIR.mkdir(parents=True, exist_ok=True)
        PHRASE_DIR.mkdir(parents=True, exist_ok=True)
        PHRASE_GIF_DIR.mkdir(parents=True, exist_ok=True)
        write_still_manifest(WORD_DIR, word_specs, reviews=word_reviews)
        write_still_manifest(ADJ_DIR, adj_specs, reviews=adj_reviews)
        write_still_manifest(PHRASE_DIR, phrase_specs, reviews=phrase_reviews)
        write_phrase_gif_manifest(phrase_specs)
    if "audit" in stages:
        report = run_audit(min_score=args.min_score)
        if not args.dry_run and not report["ok"]:
            raise SystemExit(1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
