#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUDIT = ROOT / "live-card-semantic-audit.md"


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

    if fail > 0 or (args.fail_on_weak and weak > 0):
        print("semantic audit gate failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
