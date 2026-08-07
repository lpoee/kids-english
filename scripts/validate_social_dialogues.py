#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "data" / "social_dialogues.json"
MEDIA_FIELDS = ("audio", "video", "poster")


class ValidationError(ValueError):
    pass


def _story_errors(story: dict[str, Any], root: Path, require_media: bool) -> list[str]:
    errors: list[str] = []
    story_id = story.get("id", "<missing>")
    characters = story.get("characters")
    if not isinstance(characters, list) or not characters:
        errors.append(f"{story_id}: characters must be a non-empty list")
        character_ids: set[str] = set()
    else:
        character_ids = {str(character.get("id")) for character in characters if character.get("id")}

    turns = story.get("turns")
    if not isinstance(turns, list) or not turns:
        return errors + [f"{story_id}: turns must be a non-empty list"]

    turn_ids = [str(turn.get("id")) for turn in turns if turn.get("id")]
    if len(turn_ids) != len(turns) or len(set(turn_ids)) != len(turn_ids):
        errors.append(f"{story_id}: every turn needs a unique id")
    known_turns = set(turn_ids)
    start = story.get("start")
    if start not in known_turns:
        errors.append(f"{story_id}: start turn {start!r} does not exist")

    edges: dict[str, list[str]] = {turn_id: [] for turn_id in known_turns}
    for turn in turns:
        turn_id = str(turn.get("id", "<missing>"))
        kind = turn.get("kind")
        if kind not in {"scene", "line"}:
            errors.append(f"{story_id}/{turn_id}: invalid kind {kind!r}")
        if kind == "line":
            if turn.get("speaker") not in character_ids:
                errors.append(f"{story_id}/{turn_id}: unknown speaker {turn.get('speaker')!r}")
            if not isinstance(turn.get("text"), str) or not turn["text"].strip():
                errors.append(f"{story_id}/{turn_id}: line text is required")
            if any(ord(character) >= 128 for character in turn.get("text", "")):
                errors.append(f"{story_id}/{turn_id}: child-facing text must be ASCII English")

        destinations: list[str] = []
        if turn.get("next") is not None:
            destinations.append(str(turn["next"]))
        choice = turn.get("choice")
        if choice is not None:
            options = choice.get("options") if isinstance(choice, dict) else None
            if not isinstance(options, list) or len(options) < 2:
                errors.append(f"{story_id}/{turn_id}: choice needs at least two options")
            else:
                for option in options:
                    label = option.get("label")
                    if not isinstance(label, str) or not label.strip():
                        errors.append(f"{story_id}/{turn_id}: choice label is required")
                    destinations.append(str(option.get("next")))

        for destination in destinations:
            if destination not in known_turns:
                errors.append(f"{story_id}/{turn_id}: destination {destination!r} does not exist")
            else:
                edges.setdefault(turn_id, []).append(destination)

        if require_media:
            for field in MEDIA_FIELDS:
                value = turn.get(field)
                if field == "audio" and kind == "scene":
                    continue
                if not isinstance(value, str) or not (root / value).is_file():
                    errors.append(f"{story_id}/{turn_id}: missing media {field}: {value!r}")

    if start in known_turns:
        reachable: set[str] = set()
        stack = [str(start)]
        while stack:
            turn_id = stack.pop()
            if turn_id in reachable:
                continue
            reachable.add(turn_id)
            stack.extend(edges.get(turn_id, []))
        for unreachable in sorted(known_turns - reachable):
            errors.append(f"{story_id}: unreachable turn {unreachable!r}")
    return errors


def validate_document(
    document: dict[str, Any],
    root: Path = ROOT,
    *,
    require_media: bool = True,
    raise_on_error: bool = False,
) -> list[str]:
    errors: list[str] = []
    if document.get("language") != "en":
        errors.append("document language must be 'en'")
    stories = document.get("stories")
    if not isinstance(stories, list) or not stories:
        errors.append("stories must be a non-empty list")
    else:
        for story in stories:
            errors.extend(_story_errors(story, root, require_media))
    if raise_on_error and errors:
        raise ValidationError("\n".join(errors))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Kids English social dialogue data")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--no-media", action="store_true")
    args = parser.parse_args()
    document = json.loads(args.data.read_text(encoding="utf-8"))
    errors = validate_document(document, ROOT, require_media=not args.no_media)
    if errors:
        for error in errors:
            print(error)
        return 1
    print(f"validated {len(document['stories'])} social dialogue story")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
