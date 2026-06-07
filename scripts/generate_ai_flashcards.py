#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageOps

from fetch_openverse_photos import ADJ_SELECTIONS, PHRASE_SELECTIONS, PLAIN_BG_WORDS, WORD_SELECTIONS


ROOT = Path(__file__).resolve().parents[1]
CODEX_HOME = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
IMAGE_GEN_CLI = CODEX_HOME / "skills" / ".system" / "imagegen" / "scripts" / "image_gen.py"
TMP_DIR = ROOT / ".tmp" / "ai_flashcards"

WORD_DIR = ROOT / "images" / "generated" / "vocab"
ADJ_DIR = ROOT / "images" / "generated" / "adjs"
PHRASE_DIR = ROOT / "images" / "generated" / "phrases"
PHRASE_GIF_DIR = ROOT / "images" / "generated" / "phrase_gifs"
PHRASE_FRAME_DIR = PHRASE_GIF_DIR / "frames"

WORD_EXT = ".jpg"
PHRASE_EXT = ".jpg"
GIF_EXT = ".gif"

ANIMAL_WORDS = {
    "cat", "dog", "bird", "lion", "monkey", "rabbit", "elephant", "bear", "fish", "frog",
    "duck", "pig", "cow", "horse", "sheep", "chicken", "tiger", "panda", "turtle", "butterfly",
}
FOOD_WORDS = {
    "apple", "banana", "orange", "grape", "pear", "watermelon", "strawberry", "cherry", "peach",
    "mango", "pineapple", "lemon", "bread", "cake", "cookie", "milk", "egg", "cheese", "rice",
    "water", "candy", "ice_cream",
}
BODY_WORDS = {"eye", "ear", "nose", "mouth", "hand", "foot", "head", "arm"}
HOME_WORDS = {"bed", "chair", "table", "door", "window", "cup", "spoon", "clock"}
ACTION_WORDS = {"eat", "drink", "sleep", "run", "jump", "walk", "sit", "stand", "clap", "wave"}

ADJ_PROMPTS = {
    "big": "A very large elephant beside a tiny toy block so the meaning of big is immediately obvious.",
    "small": "A very small kitten next to a much larger shoe so the meaning of small is immediately obvious.",
    "tall": "A very tall tree stretching high in the frame with a short fence nearby for scale.",
    "short": "A short pencil next to a much longer pencil so short is obvious.",
    "long": "Two simple horizontal lines on a plain background, one clearly much longer than the other, with the long line emphasized.",
    "round": "A perfectly round red ball centered in the frame.",
    "square": "A clear square gift box centered in the frame.",
    "fast": "A child sprinting across a playground with obvious motion blur or wind cues.",
    "slow": "A slow snail moving across a leaf in close-up.",
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


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def title_case_slug(slug: str) -> str:
    if slug in PHRASE_LABEL_OVERRIDES:
        return PHRASE_LABEL_OVERRIDES[slug]
    return slug.replace("_", " ").title()


def clean_query(query: str) -> str:
    return query.replace(" photo", "").strip()


def word_prompt(slug: str, query: str) -> str:
    label = title_case_slug(slug)
    desc = clean_query(query)
    shared = (
        "Create a realistic square educational flashcard photo for a private kids English app. "
        "Make the meaning instant and literal for a toddler. No text, no watermark, no collage, "
        "no illustration, no clipart, no extra subjects, no visible letters, logos, labels, signs, "
        "or packaging text."
    )

    if slug in ANIMAL_WORDS:
        return (
            f"{shared} Show one {label.lower()} clearly and fully visible. "
            "Use a natural but uncluttered background with soft blur. "
            "Center the subject and keep the animal easy to recognize."
        )
    if slug in FOOD_WORDS:
        background = "clean pale studio background" if slug in PLAIN_BG_WORDS else "simple clean background"
        return (
            f"{shared} Show {desc}. "
            f"Use a {background}. "
            "Keep the item large in frame and easy to recognize."
        )
    if slug in BODY_WORDS:
        return (
            f"{shared} Show a human {label.lower()} in close-up. "
            "Use simple neutral surroundings and make the body part the obvious focal point."
        )
    if slug in HOME_WORDS:
        background = "clean simple background" if slug in PLAIN_BG_WORDS else "real home setting with minimal clutter"
        return (
            f"{shared} Show one {label.lower()}. "
            f"Use a {background}. "
            "Center the object and keep it very easy to identify."
        )
    if slug in ACTION_WORDS:
        return (
            f"{shared} Show one young child clearly demonstrating the action '{label}'. "
            f"Scene: {desc}. "
            "Full body visible when helpful. Use a simple uncluttered setting."
        )
    return (
        f"{shared} Show {desc}. "
        "Keep the composition simple, centered, and very easy to understand."
    )


def adjective_prompt(slug: str, query: str) -> str:
    label = title_case_slug(slug)
    idea = ADJ_PROMPTS.get(slug, clean_query(query))
    return (
        "Create a realistic square educational flashcard photo for a private kids English app. "
        f"Teach the adjective '{label}' in one instant literal image. "
        f"Scene: {idea} "
        "Simple composition, child-friendly, no text, no watermark, no collage, no illustration, "
        "no labels, no signs, and no readable words anywhere in frame."
    )


PHRASE_SCENES = {
    "wake_up": "child waking up in bed, eyes open, arms raised",
    "get_up": "child sitting up and stepping out of bed",
    "goodbye": "children waving goodbye while separating",
    "see_you_later": "child waving while walking away through a doorway",
    "my_name_is": "child pointing to their chest while introducing themself",
    "nice_to_meet_you": "two children smiling and greeting each other after meeting",
    "please": "child asking politely with hands together and a gentle expression",
    "thank_you": "child receiving a gift and smiling gratefully",
    "youre_welcome": "child smiling back after helping someone",
    "sorry": "child apologizing after a small mistake",
    "more_please": "child asking for more food with an empty bowl",
    "no_more": "child pushing a bowl away to show no more",
    "good_job": "child receiving praise after finishing a task",
    "well_done": "child celebrating after completing a task well",
    "you_can_do_it": "adult encouraging a child who is trying a task",
    "whats_that": "child pointing to a distant object",
    "go_there": "child pointing toward a faraway place",
    "wait": "child holding up one hand to ask someone to wait",
    "show_me": "child showing an object to another person",
}


def phrase_prompt(slug: str, query: str) -> str:
    label = title_case_slug(slug)
    desc = clean_query(query)
    scene = PHRASE_SCENES.get(slug, desc)
    return (
        "Create a realistic square educational photo for a private kids English app. "
        f"The meaning to teach is '{label}'. "
        f"Show this literally: {scene}. "
        "Keep the scene simple and immediately understandable for a toddler. "
        "Use one child or a parent and child when needed. "
        "No text, no watermark, no split screen, no collage, no illustration, and do not render "
        "the sentence itself as written words anywhere in the image."
    )


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
    model: str,
    quality: str,
    size: str,
    concurrency: int,
    max_attempts: int,
    dry_run: bool,
    force: bool,
) -> None:
    if not specs:
        print(f"{name}: nothing to generate")
        return
    if not IMAGE_GEN_CLI.exists():
        raise FileNotFoundError(f"Image generator CLI not found: {IMAGE_GEN_CLI}")

    jobs_path = TMP_DIR / f"{name}.jsonl"
    count = write_jobs_file(jobs_path, specs)
    cmd = [
        sys.executable,
        str(IMAGE_GEN_CLI),
        "generate-batch",
        "--model",
        model,
        "--input",
        str(jobs_path),
        "--out-dir",
        str(specs[0].out_dir),
        "--concurrency",
        str(concurrency),
        "--max-attempts",
        str(max_attempts),
        "--quality",
        quality,
        "--size",
        size,
        "--output-format",
        "jpeg",
        "--no-augment",
    ]
    if force:
        cmd.append("--force")
    if dry_run:
        cmd.append("--dry-run")

    print(f"{name}: generating {count} assets")
    subprocess.run(cmd, cwd=ROOT, check=True)


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


def write_still_manifest(out_dir: Path, specs: list[AssetSpec]) -> None:
    manifest = {}
    timestamp = now_iso()
    for spec in specs:
        if not spec.out_path.exists():
            continue
        manifest[spec.slug] = {
            "label": spec.label,
            "query": spec.query,
            "prompt": spec.prompt,
            "asset_type": spec.asset_type,
            "frames": [],
            "output_file": str(spec.out_path.relative_to(ROOT)),
            "generated_at": timestamp,
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
    parser = argparse.ArgumentParser(description="Generate AI flashcard images and GIFs")
    parser.add_argument(
        "--only",
        default="words,adjs,phrases,gifs,manifests",
        help="Comma-separated stages: words,adjs,phrases,gifs,manifests",
    )
    parser.add_argument("--limit", type=int, help="Generate only the first N missing stills per stage")
    parser.add_argument("--model", default="gpt-image-2")
    parser.add_argument("--quality", default="medium")
    parser.add_argument("--size", default="1024x1024")
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--max-attempts", type=int, default=4)
    parser.add_argument("--gif-size", type=int, default=768)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    stages = {part.strip() for part in args.only.split(",") if part.strip()}
    needs_generation = bool({"words", "adjs", "phrases"} & stages)
    if needs_generation and not os.environ.get("OPENAI_API_KEY") and not args.dry_run:
        raise SystemExit("OPENAI_API_KEY is not set.")

    word_specs = build_word_specs()
    adj_specs = build_adj_specs()
    phrase_specs = build_phrase_specs()

    if "words" in stages:
        run_batch(
            name="words",
            specs=select_specs(word_specs, limit=args.limit, force=args.force),
            model=args.model,
            quality=args.quality,
            size=args.size,
            concurrency=args.concurrency,
            max_attempts=args.max_attempts,
            dry_run=args.dry_run,
            force=args.force,
        )
    if "adjs" in stages:
        run_batch(
            name="adjs",
            specs=select_specs(adj_specs, limit=args.limit, force=args.force),
            model=args.model,
            quality=args.quality,
            size=args.size,
            concurrency=args.concurrency,
            max_attempts=args.max_attempts,
            dry_run=args.dry_run,
            force=args.force,
        )
    if "phrases" in stages:
        run_batch(
            name="phrases",
            specs=select_specs(phrase_specs, limit=args.limit, force=args.force),
            model=args.model,
            quality=args.quality,
            size=args.size,
            concurrency=args.concurrency,
            max_attempts=args.max_attempts,
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
        write_still_manifest(WORD_DIR, word_specs)
        write_still_manifest(ADJ_DIR, adj_specs)
        write_still_manifest(PHRASE_DIR, phrase_specs)
        write_phrase_gif_manifest(phrase_specs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
