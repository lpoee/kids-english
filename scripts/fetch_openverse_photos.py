#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
OPENVERSE_URL = "https://api.openverse.org/v1/images"
COMMONS_URL = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "kids-english-app-codex/1.0"
MAX_SIZE = 1400

WORD_DIR = ROOT / "images" / "photos"
ADJ_DIR = ROOT / "images" / "adj_photos"
PHRASE_DIR = ROOT / "images" / "phrase_photos"

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "at",
    "for",
    "from",
    "here",
    "i",
    "im",
    "in",
    "is",
    "it",
    "its",
    "me",
    "my",
    "of",
    "on",
    "or",
    "please",
    "the",
    "this",
    "to",
    "up",
    "you",
    "your",
}

BAD_TITLE_TERMS = {
    "advert",
    "book",
    "cartoon",
    "clipart",
    "comic",
    "cover",
    "diagram",
    "drawing",
    "etching",
    "illustrated",
    "flag",
    "icon",
    "illustration",
    "logo",
    "map",
    "museum",
    "parasite",
    "painting",
    "page",
    "pdf",
    "poster",
    "psd",
    "ruined",
    "screenshot",
    "sign",
    "sketch",
    "stock",
    "statue",
    "stamp",
    "text",
    "teddy",
    "template",
    "vintage",
}

PLAIN_BACKGROUND_HINTS = {
    "close up",
    "close-up",
    "cutout",
    "isolated",
    "on white",
    "plain background",
    "white background",
    "whitebackground",
}

PLAIN_BG_WORDS = {
    "apple",
    "banana",
    "bread",
    "cake",
    "candy",
    "cheese",
    "cherry",
    "clock",
    "cookie",
    "cup",
    "door",
    "ear",
    "egg",
    "eye",
    "foot",
    "grape",
    "hand",
    "head",
    "ice_cream",
    "lemon",
    "mango",
    "milk",
    "mouth",
    "nose",
    "orange",
    "peach",
    "pear",
    "pineapple",
    "rice",
    "spoon",
    "strawberry",
    "table",
    "water",
    "watermelon",
    "window",
}

WORD_CONFLICT_TOKENS = {
    "apple",
    "banana",
    "bear",
    "bird",
    "butterfly",
    "cat",
    "chicken",
    "clock",
    "cow",
    "cup",
    "dog",
    "duck",
    "ear",
    "egg",
    "elephant",
    "eye",
    "fish",
    "frog",
    "grape",
    "hand",
    "horse",
    "house",
    "ice",
    "lemon",
    "lion",
    "mango",
    "monkey",
    "mouth",
    "nose",
    "orange",
    "panda",
    "pear",
    "pig",
    "rabbit",
    "sheep",
    "spoon",
    "strawberry",
    "table",
    "tiger",
    "turtle",
    "water",
    "window",
}

WORD_SELECTIONS = {
    "cat": {"query": "cat", "index": 1},
    "dog": {"query": "dog", "index": 1},
    "bird": {"query": "bird animal photo", "index": 1},
    "lion": {"query": "lion animal photo", "index": 2},
    "monkey": {"query": "monkey animal photo", "index": 1},
    "rabbit": {"query": "rabbit animal photo", "index": 1},
    "elephant": {"query": "elephant animal", "index": 1},
    "bear": {"query": "brown bear animal photo", "index": 3},
    "fish": {"query": "fish animal photo", "index": 1},
    "frog": {"query": "frog animal photo", "index": 3},
    "duck": {"query": "duck animal photo", "index": 3},
    "pig": {"query": "pig farm animal photo", "index": 2},
    "cow": {"query": "cow animal photo", "index": 1},
    "horse": {"query": "horse animal photo", "index": 3},
    "sheep": {"query": "sheep animal photo", "index": 1},
    "chicken": {"query": "chicken animal photo", "index": 3},
    "tiger": {"query": "tiger animal", "index": 1},
    "panda": {"query": "panda animal", "index": 1},
    "turtle": {"query": "turtle animal photo", "index": 2},
    "butterfly": {"query": "butterfly animal photo", "index": 3},
    "apple": {"query": "red apple", "index": 1},
    "banana": {"query": "banana fruit isolated", "index": 1},
    "orange": {"query": "orange fruit", "index": 1},
    "grape": {"query": "grapes fruit photo", "index": 1},
    "pear": {"query": "pear fruit photo", "index": 1},
    "watermelon": {"query": "watermelon fruit photo", "index": 1},
    "strawberry": {"query": "strawberry fruit photo", "index": 3},
    "cherry": {"query": "cherries fruit photo", "index": 1},
    "peach": {"query": "peach fruit photo", "index": 1},
    "mango": {"query": "mango fruit", "index": 1},
    "pineapple": {"query": "whole pineapple fruit photo", "index": 1},
    "lemon": {"query": "lemon fruit photo", "index": 3},
    "bread": {"query": "bread loaf", "index": 1},
    "cake": {"query": "birthday cake dessert photo", "index": 1},
    "cookie": {"query": "chocolate chip cookies photo", "index": 1},
    "milk": {"query": "glass of milk photo", "index": 1},
    "egg": {"query": "egg photo food", "index": 1},
    "cheese": {"query": "cheese wedge photo", "index": 1},
    "rice": {"query": "rice bowl food", "index": 1},
    "water": {"query": "glass of water", "index": 1},
    "candy": {"query": "candy sweet photo", "index": 1},
    "ice_cream": {"query": "ice cream cone", "index": 1},
    "eye": {"query": "eye close up photo", "index": 1},
    "ear": {"query": "ear close up photo", "index": 1},
    "nose": {"query": "nose close up photo", "index": 1},
    "mouth": {"query": "mouth close up photo", "index": 1},
    "hand": {"query": "hand palm photo", "index": 1},
    "foot": {"query": "foot close up photo", "index": 1},
    "head": {"query": "child face portrait photo", "index": 1},
    "arm": {"query": "arm photo person", "index": 1},
    "bed": {"query": "bed furniture photo", "index": 1},
    "chair": {"query": "chair furniture photo", "index": 1},
    "table": {"query": "table furniture photo", "index": 1},
    "door": {"query": "door house photo", "index": 1},
    "window": {"query": "window house photo", "index": 1},
    "cup": {"query": "cup mug photo", "index": 1},
    "spoon": {"query": "spoon utensil photo", "index": 1},
    "clock": {"query": "alarm clock photo", "index": 1},
    "eat": {"query": "child eating food photo", "index": 1},
    "drink": {"query": "child drinking water photo", "index": 1},
    "sleep": {"query": "sleeping child photo", "index": 1},
    "run": {"query": "running child photo", "index": 1},
    "jump": {"query": "jumping child photo", "index": 1},
    "walk": {"query": "walking child photo", "index": 1},
    "sit": {"query": "sitting child photo", "index": 1},
    "stand": {"query": "standing child photo", "index": 1},
    "clap": {"query": "clapping hands photo", "index": 1},
    "wave": {"query": "waving hand photo", "index": 1},
}

ADJ_SELECTIONS = {
    "big": {"query": "big elephant photo", "index": 1},
    "small": {"query": "small kitten photo", "index": 1},
    "tall": {"query": "tall tree photo", "index": 1},
    "short": {"query": "short pencil photo", "index": 1},
    "long": {"query": "long rope photo", "index": 1},
    "round": {"query": "round ball photo", "index": 1},
    "square": {"query": "square box photo", "index": 1},
    "fast": {"query": "fast runner photo", "index": 1},
    "slow": {"query": "slow snail photo", "index": 1},
}

PHRASE_SELECTIONS = {
    "wake_up": {"query": "child waking up in bed photo", "index": 1},
    "get_up": {"query": "child getting out of bed photo", "index": 1},
    "brush_teeth": {"query": "child brushing teeth photo", "index": 1},
    "wash_face": {"query": "child washing face photo", "index": 1},
    "wash_hands": {"query": "child washing hands photo", "index": 1},
    "get_dressed": {"query": "child getting dressed photo", "index": 1},
    "put_on_shoes": {"query": "child putting on shoes photo", "index": 1},
    "take_off_shoes": {"query": "child taking off shoes photo", "index": 1},
    "time_to_eat": {"query": "child eating meal photo", "index": 1},
    "breakfast_time": {"query": "breakfast table photo", "index": 1},
    "lunch_time": {"query": "lunch meal photo", "index": 1},
    "dinner_time": {"query": "family dinner photo", "index": 1},
    "snack_time": {"query": "child eating snack photo", "index": 1},
    "clean_up": {"query": "child cleaning up toys photo", "index": 1},
    "bath_time": {"query": "child bath time photo", "index": 1},
    "time_for_bed": {"query": "child bedtime photo", "index": 1},
    "go_to_sleep": {"query": "sleeping child photo", "index": 1},
    "good_morning": {"query": "happy child morning photo", "index": 1},
    "good_night": {"query": "child saying good night photo", "index": 1},
    "hello": {"query": "child waving hello photo", "index": 1},
    "goodbye": {"query": "waving goodbye photo", "index": 1},
    "see_you_later": {"query": "children saying goodbye photo", "index": 1},
    "how_are_you": {"query": "two children talking photo", "index": 1},
    "im_fine": {"query": "happy child portrait photo", "index": 1},
    "im_okay": {"query": "okay child portrait photo", "index": 1},
    "whats_your_name": {"query": "children meeting photo", "index": 1},
    "my_name_is": {"query": "child introducing self photo", "index": 1},
    "nice_to_meet_you": {"query": "children meeting handshake photo", "index": 1},
    "please": {"query": "child asking politely photo", "index": 1},
    "thank_you": {"query": "child saying thank you photo", "index": 1},
    "youre_welcome": {"query": "friendly child smile photo", "index": 1},
    "excuse_me": {"query": "child getting attention photo", "index": 1},
    "sorry": {"query": "apologizing child photo", "index": 1},
    "its_okay": {"query": "comforting child photo", "index": 1},
    "im_happy": {"query": "happy child portrait photo", "index": 1},
    "im_sad": {"query": "sad child portrait photo", "index": 1},
    "im_angry": {"query": "angry child portrait photo", "index": 1},
    "im_scared": {"query": "scared child portrait photo", "index": 1},
    "i_like_it": {"query": "child thumbs up photo", "index": 1},
    "i_dont_like_it": {"query": "child thumbs down photo", "index": 1},
    "i_love_you": {"query": "parent child hug photo", "index": 1},
    "thats_funny": {"query": "laughing child photo", "index": 1},
    "im_hungry": {"query": "hungry child photo", "index": 1},
    "im_thirsty": {"query": "thirsty child drinking water photo", "index": 1},
    "im_tired": {"query": "tired sleepy child photo", "index": 1},
    "help_me": {"query": "child asking for help photo", "index": 1},
    "can_you_help_me": {"query": "adult helping child photo", "index": 1},
    "i_want": {"query": "child pointing to toy photo", "index": 1},
    "i_dont_want": {"query": "child refusing photo", "index": 1},
    "more_please": {"query": "child asking for more food photo", "index": 1},
    "no_more": {"query": "child saying no more photo", "index": 1},
    "im_done": {"query": "child finished activity photo", "index": 1},
    "all_done": {"query": "child finished meal photo", "index": 1},
    "i_dont_know": {"query": "shrug child photo", "index": 1},
    "lets_go": {"query": "children going together photo", "index": 1},
    "lets_play": {"query": "children playing photo", "index": 1},
    "my_turn": {"query": "child taking turn game photo", "index": 1},
    "your_turn": {"query": "children taking turns photo", "index": 1},
    "share_please": {"query": "children sharing toys photo", "index": 1},
    "be_careful": {"query": "child being careful photo", "index": 1},
    "slow_down": {"query": "child slowing down photo", "index": 1},
    "listen": {"query": "child listening photo", "index": 1},
    "look": {"query": "child looking photo", "index": 1},
    "sit_down": {"query": "child sitting down photo", "index": 1},
    "stand_up": {"query": "child standing up photo", "index": 1},
    "line_up": {"query": "children line up photo", "index": 1},
    "quiet_please": {"query": "quiet finger lips child photo", "index": 1},
    "raise_your_hand": {"query": "child raising hand photo", "index": 1},
    "try_again": {"query": "child trying again photo", "index": 1},
    "good_job": {"query": "child praise photo", "index": 1},
    "well_done": {"query": "celebrating child success photo", "index": 1},
    "you_can_do_it": {"query": "encouraging child photo", "index": 1},
    "whats_this": {"query": "child looking at object photo", "index": 1},
    "whats_that": {"query": "child pointing far photo", "index": 1},
    "where_is_it": {"query": "child searching for object photo", "index": 1},
    "where_are_you": {"query": "child looking around photo", "index": 1},
    "who_is_it": {"query": "child asking who is it photo", "index": 1},
    "can_i": {"query": "child asking permission photo", "index": 1},
    "yes": {"query": "yes thumbs up photo", "index": 1},
    "no": {"query": "child shaking head no photo", "index": 1},
    "come_here": {"query": "come here hand gesture photo", "index": 1},
    "go_there": {"query": "child pointing direction photo", "index": 1},
    "wait": {"query": "child waiting photo", "index": 1},
    "stop": {"query": "stop hand gesture photo", "index": 1},
    "open": {"query": "open door photo", "index": 1},
    "close": {"query": "closing door photo", "index": 1},
    "put_it_here": {"query": "hand placing object here photo", "index": 1},
    "give_me": {"query": "child reaching hand photo", "index": 1},
    "show_me": {"query": "child showing object photo", "index": 1},
    "touch": {"query": "child touching object photo", "index": 1},
    "point_to": {"query": "finger pointing at object photo", "index": 1},
}


def slug_words(slug: str) -> list[str]:
    return slug.replace("_", " ").split()


def normalized_tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z]+", text.lower()) if t not in STOPWORDS]


def uniq(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        value = " ".join(item.split()).strip()
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def build_queries(slug: str, query: str, collection: str) -> list[str]:
    base = query.replace(" photo", "").strip()
    bare = base.replace("child ", "").replace("children ", "").strip()
    words = slug.replace("_", " ")

    if collection == "phrases":
        return uniq([query, base, bare, words, f"child {words}"])

    if collection == "adjs" or slug in PLAIN_BG_WORDS:
        return uniq(
            [
                query,
                base,
                f"{base} isolated",
                f"{base} white background",
                f"{words} isolated",
                f"{words} white background",
                words,
            ]
        )

    return uniq(
        [
            query,
            base,
            words,
        ]
    )


def score_candidate(
    slug: str,
    query: str,
    title: str,
    source: str,
    collection: str,
    rank: int,
) -> int:
    title_l = title.lower()
    score = 100 - (rank * 3)

    for token in slug_words(slug):
        if token in title_l:
            score += 16
    for token in normalized_tokens(query):
        if token in title_l:
            score += 7

    for token in WORD_CONFLICT_TOKENS:
        if token in slug_words(slug):
            continue
        if token in title_l:
            score -= 10

    if slug == "lion" and "sea lion" in title_l:
        score -= 35
    if slug == "bird" and "bird house" in title_l:
        score -= 35
    if slug == "monkey" and "monkey nut" in title_l:
        score -= 35
    if slug == "panda" and "red panda" in title_l:
        score -= 12

    if any(term in title_l for term in BAD_TITLE_TERMS):
        score -= 40
    if len(title.split()) > 10:
        score -= 10

    if collection != "phrases":
        if any(term in title_l for term in PLAIN_BACKGROUND_HINTS):
            score += 18
        if source == "commons":
            score += 12
    else:
        if source in {"rawpixel", "wellcome_collection"}:
            score += 12
        if "child" in title_l or "children" in title_l:
            score += 8

    if source == "flickr":
        score -= 5

    return score


def search_openverse(session: requests.Session, query: str) -> list[dict]:
    response = session.get(
        OPENVERSE_URL,
        params={
            "q": query,
            "license_type": "commercial,modification",
            "page_size": 12,
        },
        timeout=30,
    )
    response.raise_for_status()
    results = response.json().get("results", [])
    candidates: list[dict] = []
    for rank, item in enumerate(results, start=1):
        candidates.append(
            {
                "title": item.get("title") or query,
                "creator": item.get("creator"),
                "license": item.get("license"),
                "license_version": item.get("license_version"),
                "source": item.get("source") or "openverse",
                "foreign_landing_url": item.get("foreign_landing_url"),
                "detail_url": item.get("detail_url"),
                "original_url": item.get("url"),
                "thumbnail": item.get("thumbnail"),
                "download_url": item.get("url") or item.get("thumbnail"),
                "rank": rank,
                "matched_query": query,
            }
        )
    return candidates


def search_commons(session: requests.Session, query: str) -> list[dict]:
    response = session.get(
        COMMONS_URL,
        params={
            "action": "query",
            "generator": "search",
            "gsrsearch": query,
            "gsrnamespace": 6,
            "gsrlimit": 12,
            "prop": "imageinfo",
            "iiprop": "url|mime",
            "iiurlwidth": 1200,
            "format": "json",
        },
        timeout=30,
    )
    if response.status_code == 429:
        return []
    response.raise_for_status()
    pages = list(((response.json().get("query") or {}).get("pages") or {}).values())
    pages.sort(key=lambda page: page.get("index", 999))

    candidates: list[dict] = []
    for rank, page in enumerate(pages, start=1):
        info = (page.get("imageinfo") or [{}])[0]
        mime = (info.get("mime") or "").lower()
        if mime not in {"image/jpeg", "image/png", "image/webp"}:
            continue
        candidates.append(
            {
                "title": (page.get("title") or query).replace("File:", ""),
                "creator": "Wikimedia Commons",
                "license": "varies",
                "license_version": "",
                "source": "commons",
                "foreign_landing_url": info.get("descriptionurl"),
                "detail_url": info.get("descriptionurl"),
                "original_url": info.get("url"),
                "thumbnail": info.get("thumburl"),
                "download_url": info.get("thumburl") or info.get("url"),
                "rank": rank,
                "matched_query": query,
            }
        )
    return candidates


def fetch_selected_items(
    session: requests.Session,
    slug: str,
    config: dict[str, str | int],
    collection: str,
) -> list[dict]:
    query = str(config["query"])
    queries = build_queries(slug, query, collection)
    source_order = ["openverse", "commons"]

    all_candidates: list[dict] = []
    seen_urls: set[str] = set()
    for source_name in source_order:
        for q in queries:
            if source_name == "commons":
                candidates = search_commons(session, q)
            else:
                candidates = search_openverse(session, q)
            if not candidates:
                continue

            scored = []
            for candidate in candidates:
                candidate["score"] = score_candidate(
                    slug,
                    q,
                    str(candidate.get("title") or q),
                    str(candidate.get("source") or source_name),
                    collection,
                    int(candidate.get("rank") or 99),
                )
                scored.append(candidate)

            scored.sort(key=lambda item: int(item["score"]), reverse=True)
            for candidate in scored[:5]:
                key = str(candidate.get("original_url") or candidate.get("thumbnail") or candidate.get("title"))
                if key in seen_urls:
                    continue
                seen_urls.add(key)
                all_candidates.append(candidate)

            if scored and int(scored[0]["score"]) >= 130:
                break

    all_candidates.sort(key=lambda item: int(item["score"]), reverse=True)
    if not all_candidates:
        raise RuntimeError(f"No image candidates for slug={slug!r} query={query!r}")
    return all_candidates


def download_image(session: requests.Session, item: dict) -> Image.Image:
    candidates = [item.get("download_url"), item.get("original_url"), item.get("thumbnail")]
    for url in candidates:
        if not url:
            continue
        try:
            response = session.get(url, timeout=60)
            response.raise_for_status()
            image = Image.open(BytesIO(response.content))
            if image.mode in {"RGBA", "LA"} or (
                image.mode == "P" and "transparency" in image.info
            ):
                rgba = image.convert("RGBA")
                background = Image.new("RGB", rgba.size, "white")
                background.paste(rgba, mask=rgba.getchannel("A"))
                image = background
            else:
                image = image.convert("RGB")
            image.thumbnail((MAX_SIZE, MAX_SIZE))
            return image
        except Exception:
            continue
    raise RuntimeError(f"Failed to download image for {item.get('title')!r}")


def fetch_collection(
    session: requests.Session,
    out_dir: Path,
    selections: dict[str, dict[str, str | int]],
    collection: str,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, dict] = {}
    for slug, config in selections.items():
        candidates = fetch_selected_items(session, slug, config, collection)
        selected_item: dict | None = None
        image: Image.Image | None = None
        last_error: Exception | None = None
        for item in candidates:
            try:
                image = download_image(session, item)
                selected_item = item
                break
            except Exception as exc:
                last_error = exc

        if image is None or selected_item is None:
            raise RuntimeError(f"Failed to download a usable image for {slug!r}") from last_error

        out_path = out_dir / f"{slug}.jpg"
        image.save(out_path, quality=88, optimize=True)
        manifest[slug] = {
            "query": config["query"],
            "matched_query": selected_item.get("matched_query"),
            "title": selected_item.get("title"),
            "creator": selected_item.get("creator"),
            "license": selected_item.get("license"),
            "license_version": selected_item.get("license_version"),
            "source": selected_item.get("source"),
            "foreign_landing_url": selected_item.get("foreign_landing_url"),
            "detail_url": selected_item.get("detail_url"),
            "original_url": selected_item.get("original_url"),
            "thumbnail": selected_item.get("thumbnail"),
            "score": selected_item.get("score"),
            "local_file": str(out_path.relative_to(ROOT)),
        }
        print(
            f"saved {out_dir.name}/{slug}: {selected_item.get('title')} "
            f"[{selected_item.get('source')}]"
        )

    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"wrote manifest: {manifest_path.relative_to(ROOT)}")


def main() -> None:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    fetch_collection(session, WORD_DIR, WORD_SELECTIONS, "words")
    fetch_collection(session, ADJ_DIR, ADJ_SELECTIONS, "adjs")
    fetch_collection(session, PHRASE_DIR, PHRASE_SELECTIONS, "phrases")


if __name__ == "__main__":
    main()
