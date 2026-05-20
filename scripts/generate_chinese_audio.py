#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEXTS_PATH = ROOT / "content" / "chinese_texts.json"
OUT_DIR = ROOT / "audio_cn"
VOICE = "zh-CN-XiaoxiaoNeural"
RATE = "-8%"
VOLUME = "+0%"
PITCH = "+0Hz"


async def synthesize_all(limit: int | None, only_missing: bool) -> None:
    try:
        import edge_tts
    except ImportError as exc:
        raise SystemExit(
            "Missing dependency: edge_tts. Install it with `python3 -m pip install --user edge-tts`."
        ) from exc

    texts = json.loads(TEXTS_PATH.read_text(encoding="utf-8"))
    items = list(texts.items())
    if limit:
        items = items[:limit]

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for key, text in items:
        out_path = OUT_DIR / f"{key}.mp3"
        if only_missing and out_path.exists():
            continue

        success = False
        for attempt in range(3):
            try:
                communicate = edge_tts.Communicate(
                    text,
                    VOICE,
                    rate=RATE,
                    volume=VOLUME,
                    pitch=PITCH,
                )
                await communicate.save(str(out_path))
                success = True
                break
            except Exception as exc:  # pragma: no cover - network/runtime dependent
                if attempt == 2:
                    raise RuntimeError(f"Failed to synthesize {key}: {exc}") from exc
                await asyncio.sleep(1.5 * (attempt + 1))

        if success:
            print(f"generated {out_path.name}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate child-friendly Mandarin audio files.")
    parser.add_argument("--limit", type=int, default=None, help="Only synthesize the first N entries.")
    parser.add_argument(
        "--only-missing",
        action="store_true",
        help="Skip files that already exist in audio_cn/.",
    )
    args = parser.parse_args()

    asyncio.run(synthesize_all(limit=args.limit, only_missing=args.only_missing))
    return 0


if __name__ == "__main__":
    sys.exit(main())
