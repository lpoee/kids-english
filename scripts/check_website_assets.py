#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"


def fail(message: str) -> int:
    print(message, file=sys.stderr)
    return 1


def main() -> int:
    if not INDEX.exists():
        return fail(f"missing website file: {INDEX}")

    text = INDEX.read_text(encoding="utf-8")

    if "images/adjectives/" in text:
        return fail("stale adjective path found in index.html: images/adjectives/")

    if re.search(r"generatedImg\(kind,\s*slug,\s*ext\s*=\s*'svg'\)", text):
        return fail("generatedImg still defaults to svg; stills should resolve as jpg by default")

    if "generatedImg('adjs'" not in text and 'generatedImg("adjs"' not in text:
        return fail("missing canonical adjective asset helper in index.html")

    expected_dirs = [
        ROOT / "images" / "generated" / "vocab",
        ROOT / "images" / "generated" / "adjs",
        ROOT / "images" / "generated" / "phrases",
        ROOT / "images" / "generated" / "phrase_gifs",
    ]
    missing = [str(path.relative_to(ROOT)) for path in expected_dirs if not path.exists()]
    if missing:
        return fail("missing generated asset directories: " + ", ".join(missing))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
