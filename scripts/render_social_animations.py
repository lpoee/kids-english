#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "social_dialogues.json"
WIDTH = 720
HEIGHT = 480
FPS = 12
FRAMES = 36


@dataclass(frozen=True)
class RenderItem:
    story_id: str
    turn_id: str
    title: str
    action: str
    prop: str
    focus: str | None
    requester: str
    responder: str
    video: Path
    poster: Path


def build_render_plan(document: dict[str, Any], root: Path = ROOT) -> list[RenderItem]:
    plan: list[RenderItem] = []
    for story in document["stories"]:
        request = next(turn for turn in story["turns"] if turn["id"] == "request")
        requester = request["speaker"]
        responder = next(character["id"] for character in story["characters"] if character["id"] != requester)
        for turn in story["turns"]:
            visual = turn["visual"]
            plan.append(
                RenderItem(
                    story_id=story["id"],
                    turn_id=turn["id"],
                    title=story["title"],
                    action=visual["action"],
                    prop=visual["prop"],
                    focus=visual.get("focus"),
                    requester=requester,
                    responder=responder,
                    video=root / turn["video"],
                    poster=root / turn["poster"],
                )
            )
    return plan


def _rounded(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], radius: int, fill: str, outline: str | None = None, width: int = 1) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def _room(draw: ImageDraw.ImageDraw, accent: str, marker_x: int, marker_y: int) -> None:
    draw.rectangle((0, 0, WIDTH, 325), fill="#dff5ff")
    draw.rectangle((0, 325, WIDTH, HEIGHT), fill="#f3d3a1")
    draw.ellipse((marker_x - 18, marker_y - 18, marker_x + 18, marker_y + 18), fill=accent)
    draw.ellipse((marker_x + 28, marker_y - 8, marker_x + 48, marker_y + 12), fill="#ffffff", outline=accent, width=4)
    draw.rectangle((56, 48, 224, 190), fill="#fff8d9", outline="#83c5e5", width=10)
    draw.line((140, 52, 140, 186), fill="#83c5e5", width=6)
    draw.line((60, 119, 220, 119), fill="#83c5e5", width=6)
    draw.ellipse((85, 70, 125, 110), fill="#ffd166")
    _rounded(draw, (540, 58, 675, 210), 8, "#c98f65")
    for y in (98, 148):
        draw.rectangle((548, y, 667, y + 8), fill="#8f5f3d")
    for x, color in ((558, "#ff6b6b"), (590, "#4dabf7"), (622, "#69db7c")):
        draw.rectangle((x, 70, x + 22, 96), fill=color)
    draw.ellipse((125, 340, 595, 468), fill="#fff1a8", outline=accent, width=7)
    for x, y, color in ((90, 280, "#ff8fab"), (620, 275, "#74c0fc"), (665, 300, "#8ce99a")):
        draw.ellipse((x - 12, y - 12, x + 12, y + 12), fill=color)


def _character(
    draw: ImageDraw.ImageDraw,
    character: str,
    x: int,
    y: int,
    *,
    talking: bool,
    hand: str,
    bob: int,
    facing: int,
    mood: str = "happy",
    seated: bool = False,
) -> None:
    is_mia = character == "mia"
    skin = "#d89b73"
    hair = "#3b2a25"
    shirt = "#f35b8f" if is_mia else "#4b8fe2"
    pants = "#315b9a"
    y += bob
    # legs and shoes
    if seated:
        draw.line((x - 20, y + 118, x - 42, y + 140, x - 42, y + 166), fill=pants, width=18)
        draw.line((x + 20, y + 118, x + 42, y + 140, x + 42, y + 166), fill=pants, width=18)
        draw.ellipse((x - 57, y + 158, x - 25, y + 175), fill="#f7f7f7")
        draw.ellipse((x + 25, y + 158, x + 57, y + 175), fill="#f7f7f7")
    else:
        draw.line((x - 20, y + 118, x - 25, y + 166), fill=pants, width=18)
        draw.line((x + 20, y + 118, x + 25, y + 166), fill=pants, width=18)
        draw.ellipse((x - 42, y + 154, x - 10, y + 171), fill="#f7f7f7")
        draw.ellipse((x + 10, y + 154, x + 42, y + 171), fill="#f7f7f7")
    # body
    _rounded(draw, (x - 47, y + 48, x + 47, y + 128), 24, shirt)
    if not is_mia:
        for stripe_y in (68, 89, 110):
            draw.rectangle((x - 42, y + stripe_y, x + 42, y + stripe_y + 7), fill="#edf6ff")
    # arms
    shoulder_y = y + 72
    if hand == "ask":
        draw.line((x + 30 * facing, shoulder_y, x + 77 * facing, y + 82), fill=skin, width=16)
        draw.ellipse((x + 68 * facing - 9, y + 73, x + 68 * facing + 9, y + 91), fill=skin)
        draw.line((x - 28 * facing, shoulder_y, x - 25 * facing, y + 116), fill=skin, width=16)
    elif hand == "stop":
        draw.line((x + 28 * facing, shoulder_y, x + 58 * facing, y + 45), fill=skin, width=16)
        draw.ellipse((x + 50 * facing - 10, y + 32, x + 50 * facing + 10, y + 54), fill=skin)
        draw.line((x - 28 * facing, shoulder_y, x - 24 * facing, y + 115), fill=skin, width=16)
    elif hand == "offer":
        draw.line((x - 28, shoulder_y, x - 4, y + 105), fill=skin, width=16)
        draw.line((x + 28, shoulder_y, x + 4, y + 105), fill=skin, width=16)
    else:
        draw.line((x - 28, shoulder_y, x - 38, y + 118), fill=skin, width=16)
        draw.line((x + 28, shoulder_y, x + 38, y + 118), fill=skin, width=16)
    # head and hair
    draw.ellipse((x - 49, y - 42, x + 49, y + 55), fill=skin)
    draw.pieslice((x - 52, y - 48, x + 52, y + 42), 180, 360, fill=hair)
    if is_mia:
        draw.ellipse((x - 70, y - 15, x - 42, y + 20), fill=hair)
    eye_y = y + 9
    draw.ellipse((x - 24, eye_y - 5, x - 14, eye_y + 5), fill="#2d2523")
    draw.ellipse((x + 14, eye_y - 5, x + 24, eye_y + 5), fill="#2d2523")
    if talking:
        draw.ellipse((x - 10, y + 29, x + 10, y + 44), fill="#7b2d3b")
    elif mood == "upset":
        draw.arc((x - 14, y + 31, x + 14, y + 49), 190, 350, fill="#7b2d3b", width=3)
    else:
        draw.arc((x - 14, y + 22, x + 14, y + 43), 10, 170, fill="#7b2d3b", width=3)


def _prop(draw: ImageDraw.ImageDraw, prop: str, x: int, y: int, action: str, scale: float = 1.0) -> None:
    if prop == "car":
        _rounded(draw, (x - 48, y - 24, x + 48, y + 18), 12, "#ef4444")
        draw.polygon([(x - 26, y - 24), (x - 8, y - 48), (x + 27, y - 48), (x + 40, y - 24)], fill="#60a5fa")
        for wx in (x - 29, x + 29):
            draw.ellipse((wx - 11, y + 7, wx + 11, y + 29), fill="#263238")
    elif prop == "truck":
        draw.rectangle((x - 58, y - 30, x + 15, y + 22), fill="#f59f00")
        draw.rectangle((x + 15, y - 16, x + 55, y + 22), fill="#ffd43b")
        for wx in (x - 33, x + 32):
            draw.ellipse((wx - 12, y + 10, wx + 12, y + 34), fill="#263238")
    elif prop == "ball" or prop == "tag":
        draw.ellipse((x - 37, y - 37, x + 37, y + 37), fill="#ff6b6b", outline="#fff", width=5)
        draw.arc((x - 30, y - 30, x + 30, y + 30), 70, 250, fill="#ffd166", width=6)
    elif prop == "crayons":
        for index, color in enumerate(("#ff4d6d", "#4dabf7", "#51cf66", "#ffd43b", "#845ef7")):
            px = x - 50 + index * 24
            draw.rounded_rectangle((px, y - 42, px + 12, y + 30), radius=5, fill=color)
    elif prop == "bench":
        _rounded(draw, (x - 95, y - 20, x + 95, y + 12), 8, "#c68642")
        draw.rectangle((x - 75, y + 10, x - 60, y + 55), fill="#8d5524")
        draw.rectangle((x + 60, y + 10, x + 75, y + 55), fill="#8d5524")
    elif prop == "train":
        draw.rectangle((x - 62, y - 33, x + 35, y + 20), fill="#e03131")
        draw.rectangle((x + 8, y - 55, x + 48, y + 20), fill="#339af0")
        draw.rectangle((x + 18, y - 44, x + 38, y - 18), fill="#dff5ff")
        for wx in (x - 38, x + 25):
            draw.ellipse((wx - 13, y + 8, wx + 13, y + 34), fill="#263238")
    elif prop == "swing":
        draw.line((x - 70, y + 50, x, y - 80, x + 70, y + 50), fill="#495057", width=9)
        draw.line((x - 28, y - 30, x - 28, y + 25), fill="#495057", width=4)
        draw.line((x + 28, y - 30, x + 28, y + 25), fill="#495057", width=4)
        draw.rectangle((x - 38, y + 20, x + 38, y + 32), fill="#ff922b")
    elif prop == "repair_blocks":
        colors = ("#ff6b6b", "#4dabf7", "#ffd43b", "#69db7c")
        if action in {"accept", "positive_result"}:
            for index, color in enumerate(colors):
                half = 62 - index * 10
                draw.rounded_rectangle((x - half, y + 20 - index * 42, x + half, y + 53 - index * 42), radius=5, fill=color)
        else:
            pieces = ((-92, 18, 0), (-35, 35, 12), (28, 12, -8), (82, 38, 7))
            for (dx, dy, tilt), color in zip(pieces, colors):
                draw.rounded_rectangle((x + dx - 31, y + dy - 16, x + dx + 31, y + dy + 16), radius=5, fill=color)
    elif prop == "tower" or prop == "blocks":
        colors = ("#ff6b6b", "#4dabf7", "#ffd43b", "#69db7c")
        for index, color in enumerate(colors):
            half = 62 - index * 10
            draw.rounded_rectangle((x - half, y + 20 - index * 42, x + half, y + 53 - index * 42), radius=5, fill=color)
    elif prop == "book":
        draw.polygon([(x - 70, y - 35), (x - 5, y - 18), (x - 5, y + 48), (x - 70, y + 30)], fill="#845ef7")
        draw.polygon([(x + 70, y - 35), (x + 5, y - 18), (x + 5, y + 48), (x + 70, y + 30)], fill="#5f3dc4")
    elif prop == "jar":
        draw.rounded_rectangle((x - 38, y - 62, x + 38, y + 35), radius=14, fill="#dff5ff", outline="#74c0fc", width=5)
        draw.rectangle((x - 42, y - 68, x + 42, y - 55), fill="#868e96")
        draw.ellipse((x - 24, y - 20, x + 24, y + 25), fill="#ffd43b")
    else:
        draw.ellipse((x - 35, y - 35, x + 35, y + 35), fill="#74c0fc")


def scene_plan(item: RenderItem, phase: float) -> dict[str, Any]:
    """Return the explicit, testable visual state for one story turn."""
    state: dict[str, Any] = {
        "owner": item.responder,
        "requester_hand": "ask" if item.turn_id == "request" else "rest",
        "responder_hand": "rest",
        "active_children": [],
        "seated_children": [],
        "distance": 310,
        "intrusion": False,
    }

    if item.turn_id == "accept":
        state["responder_hand"] = "offer"
        state["owner"] = item.responder if phase < 0.55 else item.requester
    elif item.turn_id == "thanks":
        state["owner"] = item.requester
    elif item.turn_id in {"decline", "wait"}:
        state["owner"] = item.responder

    if item.story_id == "toy_car" and item.turn_id == "next_turn":
        state["future_turn"] = "mia"

    if item.story_id == "join_play":
        if item.turn_id in {"accept", "thanks"}:
            state.update(active_children=["mia", "leo"], build_shape="shared_tower")
        if item.turn_id == "wait":
            state["waiting_child"] = "mia"

    if item.story_id == "borrow_toy" and item.turn_id == "wait":
        state["waiting_child"] = "mia"
    if item.story_id == "borrow_toy" and item.turn_id == "thanks":
        state["return_to"] = "leo"

    if item.story_id == "take_turns":
        state["owner"] = "leo"
        if item.turn_id in {"accept", "thanks"}:
            state["future_turn"] = "mia"
        if item.turn_id == "thanks":
            state["confirmed_future_turn"] = True
        if item.turn_id == "wait":
            state["waiting_child"] = "mia"
        if item.turn_id == "decline":
            state["busy_more_time"] = "leo"

    if item.story_id == "share_materials":
        if item.turn_id in {"accept", "thanks", "wait"}:
            state["split_prop"] = True
            state["active_children"] = ["mia", "leo"]
            state["crayon_allocation"] = {"mia": 3, "leo": 2}
        if item.turn_id == "thanks":
            state["highlight_color"] = "blue"

    if item.story_id == "accept_yes":
        if item.turn_id in {"accept", "thanks"}:
            state.update(active_children=["mia", "leo"], build_shape="bridge")
        if item.turn_id in {"decline", "wait"}:
            state["alternative"] = "drawing"

    if item.story_id == "polite_no":
        if item.turn_id == "accept":
            state["active_children"] = ["mia", "leo"]
        if item.turn_id in {"decline", "wait"}:
            state["alternative"] = "book"
        if item.turn_id == "wait":
            state["quiet_children"] = ["mia", "leo"]

    if item.story_id == "accept_no":
        if item.turn_id in {"setup", "request", "decline"}:
            state["seated_children"] = ["mia"]
        if item.turn_id in {"accept", "thanks"}:
            state["seated_children"] = ["mia", "leo"]
        if item.turn_id == "wait":
            state["separate_seat"] = "leo"
            state["seated_children"] = ["mia", "leo"]

    if item.story_id == "still_using" and item.turn_id == "wait":
        state["waiting_child"] = "mia"

    if item.story_id == "wait_calmly":
        state["fixed_equipment"] = "swing"
        state["owner"] = "mia"
        if item.turn_id in {"accept", "thanks"}:
            state["owner"] = "mia" if phase < 0.55 and item.turn_id == "accept" else "leo"
        if item.turn_id == "accept":
            state["seated_children"] = [state["owner"]]
        if item.turn_id == "wait":
            state["waiting_child"] = "leo"
        if item.turn_id == "thanks":
            state["seated_children"] = ["leo"]
        elif item.turn_id in {"setup", "request", "decline", "wait"}:
            state["seated_children"] = ["mia"]

    if item.story_id == "next_turn":
        state["owner"] = "leo"
        if item.turn_id == "accept":
            state["future_turn"] = "mia"
        if item.turn_id == "decline":
            state["queued_before"] = "mia"
        if item.turn_id == "thanks":
            state["ready_child"] = "mia"
        if item.turn_id == "wait":
            state["queued_before"] = "mia"
            state["waiting_child"] = "mia"

    if item.story_id == "please_stop":
        state["intrusion"] = item.turn_id in {"setup", "request", "decline"}
        if item.turn_id == "request":
            state["boundary_hand"] = "mia"
        if item.turn_id in {"accept", "decline"}:
            state["intrusion"] = phase < 0.55
        if item.turn_id == "accept":
            state["accepted_stop"] = True
        if item.turn_id == "decline":
            state["apology"] = True
        if item.turn_id in {"thanks", "wait"}:
            state["comfortable"] = True
        if item.turn_id == "thanks":
            state["gratitude"] = True
        if item.turn_id == "wait":
            state["relief"] = True

    if item.story_id == "personal_space":
        if item.turn_id in {"setup", "request"}:
            state["distance"] = 120
        elif item.turn_id in {"accept", "decline", "wait"}:
            state["distance"] = int(120 + 210 * phase)
        else:
            state["distance"] = 330

    if item.story_id == "ask_for_help":
        state["owner"] = "mia"
        state["jar_open"] = item.turn_id in {"thanks"}
        if item.turn_id == "accept":
            state["jar_open"] = phase >= 0.6
            state["active_children"] = ["mia", "leo"]
        if item.turn_id == "wait":
            state["active_children"] = ["mia"]

    if item.story_id == "offer_help":
        state["blocks_state"] = "scattered"
        if item.turn_id == "accept":
            state["blocks_state"] = "stacked" if phase >= 0.72 else "scattered"
            state["active_children"] = ["mia", "leo"]
        elif item.turn_id == "thanks":
            state.update(blocks_state="stacked", active_children=["mia", "leo"])
        elif item.turn_id == "wait":
            state["active_children"] = ["mia"]
            state["blocks_state"] = "partial" if phase >= 0.6 else "scattered"

    if item.story_id == "apologize":
        state["blocks_state"] = "scattered"
        if item.turn_id == "setup":
            state["blocks_state"] = "stacked" if phase < 0.45 else "scattered"
        elif item.turn_id in {"accept", "thanks"}:
            state["blocks_state"] = "stacked" if phase >= 0.72 or item.turn_id == "thanks" else "scattered"
            state["active_children"] = ["mia", "leo"]

    if item.story_id == "invite_friend":
        if item.turn_id in {"accept", "thanks"}:
            state.update(ball_exchange=True, active_children=["mia", "leo"])
        if item.turn_id == "decline":
            state["alternative"] = "book"
        if item.turn_id == "wait":
            state.update(active_children=["mia"], owner="mia", alternative="book")

    if item.story_id == "work_together":
        if item.turn_id in {"accept", "thanks"}:
            state.update(build_shape="bridge", active_children=["mia", "leo"])
        if item.turn_id == "decline":
            state.update(build_shape="tower", active_children=["mia", "leo"])
        if item.turn_id == "wait":
            state.update(build_shape="tower", active_children=["mia", "leo"], passing_blocks=True)

    return state


def _clock(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    draw.ellipse((x - 25, y - 25, x + 25, y + 25), fill="#fff", outline="#495057", width=4)
    draw.line((x, y, x, y - 15), fill="#495057", width=4)
    draw.line((x, y, x + 12, y + 8), fill="#495057", width=4)


def _check_badge(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    draw.ellipse((x - 44, y - 44, x + 44, y + 44), fill="#d3f9d8", outline="#2f9e44", width=7)
    draw.line((x - 24, y, x - 6, y + 20, x + 29, y - 23), fill="#2f9e44", width=10)


def _heart_badge(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    draw.ellipse((x - 43, y - 34, x + 43, y + 48), fill="#fff0f6", outline="#f06595", width=6)
    draw.ellipse((x - 24, y - 14, x, y + 12), fill="#f06595")
    draw.ellipse((x, y - 14, x + 24, y + 12), fill="#f06595")
    draw.polygon([(x - 24, y), (x + 24, y), (x, y + 32)], fill="#f06595")


def _direction_arrow(draw: ImageDraw.ImageDraw, x1: int, x2: int, y: int) -> None:
    draw.line((x1, y, x2, y), fill="#2f9e44", width=8)
    direction = 1 if x2 > x1 else -1
    draw.polygon([(x2, y), (x2 - 18 * direction, y - 13), (x2 - 18 * direction, y + 13)], fill="#2f9e44")


def _draw_blocks(draw: ImageDraw.ImageDraw, x: int, y: int, shape: str) -> None:
    colors = ("#ff6b6b", "#4dabf7", "#ffd43b", "#69db7c")
    if shape in {"tower", "stacked", "shared_tower"}:
        for index, color in enumerate(colors):
            half = 58 - index * 9
            draw.rounded_rectangle((x - half, y - index * 36, x + half, y + 28 - index * 36), radius=5, fill=color)
    elif shape == "partial":
        draw.rounded_rectangle((x - 52, y - 18, x + 52, y + 16), radius=5, fill=colors[0])
        draw.rounded_rectangle((x - 40, y - 54, x + 40, y - 22), radius=5, fill=colors[1])
        draw.rounded_rectangle((x + 70, y - 4, x + 128, y + 26), radius=5, fill=colors[2])
        draw.rounded_rectangle((x - 132, y + 5, x - 72, y + 35), radius=5, fill=colors[3])
    elif shape == "bridge":
        draw.rounded_rectangle((x - 92, y - 60, x - 52, y + 25), radius=5, fill=colors[0])
        draw.rounded_rectangle((x + 52, y - 60, x + 92, y + 25), radius=5, fill=colors[1])
        draw.rounded_rectangle((x - 88, y - 94, x + 88, y - 56), radius=6, fill=colors[2])
        draw.rounded_rectangle((x - 28, y - 130, x + 28, y - 98), radius=5, fill=colors[3])
    else:
        for (dx, dy), color in zip(((-90, 4), (-30, 24), (35, -3), (92, 20)), colors):
            draw.rounded_rectangle((x + dx - 30, y + dy - 15, x + dx + 30, y + dy + 15), radius=5, fill=color)


def _draw_drawing(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    draw.rectangle((x - 60, y - 70, x + 60, y + 35), fill="#fff", outline="#adb5bd", width=4)
    draw.ellipse((x - 12, y - 45, x + 35, y + 2), fill="#ffd43b")
    draw.line((x - 45, y + 20, x + 10, y - 25, x + 50, y + 18), fill="#51cf66", width=6)
    for dx, color in ((-35, "#ff6b6b"), (0, "#4dabf7"), (35, "#845ef7")):
        draw.rectangle((x + dx - 4, y + 40, x + dx + 4, y + 92), fill=color)


def _draw_jar(draw: ImageDraw.ImageDraw, x: int, y: int, opened: bool) -> None:
    draw.rounded_rectangle((x - 38, y - 62, x + 38, y + 35), radius=14, fill="#dff5ff", outline="#74c0fc", width=5)
    draw.ellipse((x - 24, y - 20, x + 24, y + 25), fill="#ffd43b")
    lid_y = y - 95 if opened else y - 68
    lid_x = x + 55 if opened else x
    draw.rectangle((lid_x - 42, lid_y, lid_x + 42, lid_y + 13), fill="#868e96")


def _draw_swing(draw: ImageDraw.ImageDraw) -> None:
    frame = "#495057"
    draw.line((270, 100, 450, 100), fill=frame, width=12)
    draw.line((270, 100, 210, 430), fill=frame, width=12)
    draw.line((450, 100, 510, 430), fill=frame, width=12)
    draw.line((335, 100, 335, 370), fill=frame, width=6)
    draw.line((385, 100, 385, 370), fill=frame, width=6)
    draw.rounded_rectangle((288, 365, 432, 382), radius=5, fill="#ff922b", outline="#c25b00", width=3)


def draw_frame(item: RenderItem, frame_index: int, total_frames: int = FRAMES) -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), "#dff5ff")
    draw = ImageDraw.Draw(image)
    story_digest = hashlib.sha256(item.story_id.encode("utf-8")).digest()
    story_accent = f"#{80 + story_digest[0] % 140:02x}{80 + story_digest[1] % 140:02x}{80 + story_digest[2] % 140:02x}"
    _room(draw, story_accent, -80, -80)
    phase = frame_index / max(1, total_frames - 1)
    wave = math.sin(phase * math.pi * 2)
    bob = int(3 * wave)
    scene = scene_plan(item, phase)

    center = 360
    distance = scene.get("distance", 310)
    positions = {"mia": center - distance // 2, "leo": center + distance // 2}
    if scene.get("intrusion"):
        positions = {"mia": 280, "leo": 405 + int(85 * phase) if item.turn_id == "accept" else 405}
    if scene.get("comfortable"):
        positions = {"mia": 220, "leo": 520}

    waiting_child = scene.get("waiting_child")
    if waiting_child:
        positions[waiting_child] = 145 if waiting_child == "mia" else 575
    if item.story_id == "polite_no" and scene.get("active_children"):
        positions = {"mia": int(170 + 70 * phase), "leo": int(410 + 70 * phase)}
    if item.story_id == "wait_calmly":
        occupant = str(scene.get("owner", "mia"))
        positions[occupant] = 360
        other = "leo" if occupant == "mia" else "mia"
        positions[other] = 575 if other == "leo" else 145
        _draw_swing(draw)

    # Seats belong behind the children.
    if item.story_id == "accept_no":
        if scene.get("separate_seat"):
            _prop(draw, "bench", 220, 350, "setup")
            _prop(draw, "bench", 520, 350, "setup")
            positions = {"mia": 220, "leo": 520}
        else:
            _prop(draw, "bench", 360, 350, "setup")
            if set(scene.get("seated_children", [])) == {"mia", "leo"}:
                positions = {"mia": 300, "leo": 420}
            elif scene.get("seated_children") == ["mia"]:
                positions["mia"] = 330

    requester_hand = scene.get("requester_hand", "rest")
    responder_hand = scene.get("responder_hand", "rest")
    if item.turn_id == "decline":
        responder_hand = "stop"
    if scene.get("boundary_hand") == item.requester:
        requester_hand = "stop"
    if scene.get("intrusion"):
        responder_hand = "ask"
    if scene.get("active_children"):
        requester_hand, responder_hand = "ask", "offer"
    if scene.get("passing_blocks"):
        requester_hand, responder_hand = "offer", "ask"

    focus = item.focus
    talking_mia = focus == "mia" and frame_index % 12 < 7
    talking_leo = focus == "leo" and frame_index % 12 < 7
    mood_mia = "upset" if item.story_id == "apologize" and item.turn_id == "request" else "happy"
    mood_leo = "upset" if item.story_id == "apologize" and item.turn_id in {"decline", "wait"} else "happy"
    mia_seated = "mia" in scene.get("seated_children", [])
    leo_seated = "leo" in scene.get("seated_children", [])
    seated_y = 252 if item.story_id == "wait_calmly" else 212
    mia_y = seated_y if mia_seated else 175
    leo_y = seated_y if leo_seated else 175
    _character(draw, "mia", positions["mia"], mia_y, talking=talking_mia,
               hand=requester_hand if item.requester == "mia" else responder_hand,
               bob=bob, facing=1, mood=mood_mia, seated=mia_seated)
    _character(draw, "leo", positions["leo"], leo_y, talking=talking_leo,
               hand=requester_hand if item.requester == "leo" else responder_hand,
               bob=-bob, facing=-1, mood=mood_leo, seated=leo_seated)

    requester_x = positions[item.requester]
    responder_x = positions[item.responder]
    owner = str(scene.get("owner", ""))
    owner_x = positions[owner] if owner in positions else responder_x
    prop_y = 380

    # Story-specific semantic props and outcomes.
    if item.story_id == "polite_no":
        if scene.get("quiet_children"):
            _prop(draw, "book", positions["mia"], prop_y, "setup")
            _prop(draw, "book", positions["leo"], prop_y, "setup")
        elif scene.get("alternative") == "book":
            _prop(draw, "book", positions[item.responder], prop_y, "setup")
        else:
            for step in range(4):
                x = int(245 + step * 70 + 16 * math.sin(phase * math.pi * 2 + step))
                draw.ellipse((x - 9, 365 + (step % 2) * 12, x + 9, 383 + (step % 2) * 12), fill="#ff6b6b")
            if scene.get("active_children"):
                _direction_arrow(draw, 275, 455, 350)
    elif item.story_id == "accept_no":
        pass
    elif item.story_id in {"join_play", "accept_yes", "work_together"} and not scene.get("alternative"):
        shape = scene.get("build_shape")
        if shape:
            _draw_blocks(draw, 360, 397, shape)
        else:
            _draw_blocks(draw, owner_x, 397, "tower")
        if scene.get("passing_blocks"):
            block_x = int(positions["leo"] + (positions["mia"] - positions["leo"]) * phase)
            draw.rounded_rectangle((block_x - 28, 320, block_x + 28, 350), radius=5, fill="#ff922b")
    elif item.story_id in {"offer_help", "apologize"}:
        state = scene.get("blocks_state", "scattered")
        if item.turn_id in {"accept"} and phase < 0.72:
            moving_x = int(positions[item.requester] + (360 - positions[item.requester]) * phase)
            draw.rounded_rectangle((moving_x - 28, 322, moving_x + 28, 352), radius=5, fill="#69db7c")
        _draw_blocks(draw, 360, 397, state)
    elif item.story_id == "ask_for_help":
        jar_x = 360 if scene.get("active_children") else owner_x
        _draw_jar(draw, jar_x, 382, bool(scene.get("jar_open")))
        if item.turn_id in {"setup", "wait"}:
            _direction_arrow(draw, jar_x - 35, jar_x + 35, 305)
    elif item.story_id == "share_materials" and scene.get("split_prop"):
        palette = ["#ff4d6d", "#51cf66", "#ffd43b", "#4dabf7", "#845ef7"]
        mia_colors = palette[:3]
        leo_colors = ["#4dabf7"] if scene.get("highlight_color") == "blue" else palette[3:]
        for child, colors in (("mia", mia_colors), ("leo", leo_colors)):
            base_x = positions[child] - 13 * (len(colors) - 1)
            if child == "leo" and scene.get("highlight_color") == "blue":
                draw.ellipse((positions[child] - 52, prop_y - 72, positions[child] + 52, prop_y + 50), fill="#d0ebff", outline="#1c7ed6", width=7)
            for index, color in enumerate(colors):
                px = base_x + index * 26
                width = 17 if color == "#4dabf7" and scene.get("highlight_color") else 12
                draw.rounded_rectangle((px - width // 2, prop_y - 42, px + width // 2, prop_y + 30), radius=5, fill=color)
    elif item.story_id == "invite_friend" and scene.get("alternative") == "book":
        _prop(draw, "book", positions[item.responder], prop_y, "setup")
        if item.turn_id == "wait":
            _prop(draw, "ball", positions["mia"], prop_y, "setup")
    elif item.story_id == "accept_yes" and scene.get("alternative") == "drawing":
        _draw_drawing(draw, positions[item.responder], 370)
    elif item.story_id == "invite_friend" and scene.get("ball_exchange"):
        ball_x = int(positions["mia"] + (positions["leo"] - positions["mia"]) * (0.5 - 0.5 * math.cos(phase * math.pi)))
        _prop(draw, "ball", ball_x, prop_y, "accept")
        _direction_arrow(draw, positions["mia"] + 55, positions["leo"] - 55, 345)
    elif item.story_id == "wait_calmly":
        pass
    elif item.story_id == "please_stop":
        _draw_blocks(draw, positions["mia"] + 35, 397, "tower")
        if scene.get("comfortable"):
            draw.ellipse((positions["mia"] - 22, 88, positions["mia"] + 22, 132), fill="#69db7c")
    else:
        if item.turn_id == "accept" and item.story_id not in {"take_turns", "next_turn"}:
            prop_x = int(responder_x + (requester_x - responder_x) * (0.15 + 0.85 * phase))
        else:
            prop_x = owner_x
        _prop(draw, item.prop, prop_x, prop_y, item.action)

    if scene.get("alternative") == "book" and item.story_id != "polite_no":
        _prop(draw, "book", positions[item.responder], prop_y, "setup")
    if scene.get("return_to"):
        _clock(draw, 360, 295)
        _direction_arrow(draw, owner_x, positions[scene["return_to"]], 330)
    if scene.get("busy_more_time"):
        _clock(draw, positions[scene["busy_more_time"]], 115)
    if scene.get("future_turn"):
        future_x = positions[scene["future_turn"]]
        _clock(draw, 360, 295)
        _direction_arrow(draw, owner_x, future_x, 330)
    if scene.get("queued_before"):
        _clock(draw, 360, 295)
        for x, color in ((300, "#4dabf7"), (360, "#ffd43b"), (420, "#ff6b6b")):
            draw.ellipse((x - 15, 325, x + 15, 355), fill=color)
        _direction_arrow(draw, 285, 435, 372)
    if waiting_child:
        _clock(draw, positions[waiting_child], 115)
    if scene.get("confirmed_future_turn"):
        _check_badge(draw, 500, 105)
    if scene.get("ready_child"):
        _check_badge(draw, positions[scene["ready_child"]], 105)
    if scene.get("accepted_stop"):
        _check_badge(draw, positions["leo"], 105)
    if scene.get("apology"):
        _heart_badge(draw, positions["leo"], 105)
    if scene.get("gratitude"):
        _heart_badge(draw, 360, 105)
    if scene.get("relief"):
        _check_badge(draw, positions["mia"], 105)

    return image


def render_item(item: RenderItem, *, force: bool = False) -> None:
    if item.video.exists() and item.poster.exists() and not force:
        return
    item.video.parent.mkdir(parents=True, exist_ok=True)
    item.poster.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{WIDTH}x{HEIGHT}", "-r", str(FPS), "-i", "-",
        "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "24", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        str(item.video),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    assert process.stdin is not None
    poster_frame = FRAMES // 3
    for frame_index in range(FRAMES):
        frame = draw_frame(item, frame_index)
        if frame_index == poster_frame:
            frame.save(item.poster, format="JPEG", quality=90, optimize=True)
        process.stdin.write(frame.tobytes())
    process.stdin.close()
    return_code = process.wait()
    if return_code != 0:
        raise RuntimeError(f"ffmpeg failed for {item.story_id}/{item.turn_id}: {return_code}")


def render_all(document: dict[str, Any], root: Path = ROOT, *, force: bool = False) -> int:
    plan = build_render_plan(document, root)
    for index, item in enumerate(plan, 1):
        render_item(item, force=force)
        print(f"[{index}/{len(plan)}] {item.story_id}/{item.turn_id}")
    return len(plan)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render deterministic text-free social animations")
    parser.add_argument("--data", type=Path, default=DATA_PATH)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    document = json.loads(args.data.read_text(encoding="utf-8"))
    count = render_all(document, ROOT, force=args.force)
    print(f"rendered {count} independent social turn animations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
