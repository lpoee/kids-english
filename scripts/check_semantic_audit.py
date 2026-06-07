#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUDIT = ROOT / "live-card-semantic-audit.md"
INDEX = ROOT / "index.html"


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def load_blocked_words(index_path: Path) -> set[str]:
    if not index_path.exists():
        return set()
    text = index_path.read_text(encoding="utf-8")
    match = re.search(r"const BLOCKED_WORDS = new Set\(\[(.*?)\]\);", text, re.S)
    if not match:
        return set()
    body = match.group(1)
    words = set()
    for value in re.findall(r'"([^"]+)"', body):
        words.add(value)
    return words


def parse_audit_cards(text: str) -> list[tuple[str, str]]:
    cards: list[tuple[str, str]] = []
    for line in text.splitlines():
        if not line.startswith("| "):
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) < 7:
          continue
        card = parts[3]
        score = parts[5]
        if score in {"PASS", "WEAK", "FAIL"}:
            cards.append((card, score))
    return cards


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the live semantic audit report.")
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument(
        "--fail-on-weak",
        action="store_true",
        help="Treat WEAK cards as a build failure, not just FAIL cards.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.audit.exists():
        print(f"missing audit file: {args.audit}", file=sys.stderr)
        return 1

    text = args.audit.read_text(encoding="utf-8")
    summary = re.search(
        r"Summary:\s*- Total cards reviewed:\s*(\d+)\s*- PASS:\s*(\d+)\s*- WEAK:\s*(\d+)\s*- FAIL:\s*(\d+)",
        text,
        re.S,
    )
    if not summary:
        print(f"could not parse summary from {args.audit}", file=sys.stderr)
        return 1

    total, passed, weak, fail = map(int, summary.groups())
    print(f"semantic audit: total={total} pass={passed} weak={weak} fail={fail}")

    blocked = load_blocked_words(INDEX)
    if not blocked:
        print(f"missing blocked-word list in {INDEX}", file=sys.stderr)
        return 1

    cards = parse_audit_cards(text)
    bad_cards = []
    for card, score in cards:
        slug = slugify(card)
        if score in {"WEAK", "FAIL"} and slug not in blocked:
            bad_cards.append(card)
        if score == "PASS" and slug in blocked:
            bad_cards.append(card)

    if bad_cards:
        print("semantic audit gate failed", file=sys.stderr)
        print("unaccounted cards: " + ", ".join(sorted(set(bad_cards))), file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
