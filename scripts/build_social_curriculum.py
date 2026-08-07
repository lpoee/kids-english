#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "social_dialogues.json"

CHARACTERS = [
    {
        "id": "mia",
        "name": "Mia",
        "voice": "en-US-AnaNeural",
        "pitch": "+8Hz",
        "rate": "-8%",
        "appearance": "pink long-sleeve shirt, blue jeans, dark ponytail",
    },
    {
        "id": "leo",
        "name": "Leo",
        "voice": "en-US-AnaNeural",
        "pitch": "-12Hz",
        "rate": "-12%",
        "appearance": "blue-and-white striped shirt, blue jeans, short dark hair",
    },
]

STORIES: list[dict[str, Any]] = [
    {
        "id": "toy_car", "title": "Can I Play With the Car?", "skill": "ask to use a toy and accept yes or no", "prop": "car",
        "requester": "mia", "responder": "leo", "request": "Can I play with it?",
        "yes_label": "Sure!", "yes": "Sure! Here you go.", "yes_end": "Thank you!",
        "no_label": "Not right now.", "no": "Not right now. I'm still using it.", "no_end": "Okay. I'll wait.",
        "after_no": "You can have it next.",
    },
    {
        "id": "join_play", "title": "Can I Play With You?", "skill": "join another child's play", "prop": "blocks",
        "requester": "mia", "responder": "leo", "request": "Can I play with you?",
        "yes_label": "Yes!", "yes": "Yes! Come play.", "yes_end": "Yay! Let's play together.",
        "no_label": "Not yet.", "no": "Not yet. I'm finishing this part.", "no_end": "Okay. I'll watch for now.",
    },
    {
        "id": "borrow_toy", "title": "Can I Use the Truck?", "skill": "borrow a toy for a short time", "prop": "truck",
        "requester": "mia", "responder": "leo", "request": "Can I use the truck for a little while?",
        "yes_label": "Sure.", "yes": "Sure. Here you go.", "yes_end": "Thanks! I'll bring it back.",
        "no_label": "Not yet.", "no": "Not yet. I'm using it.", "no_end": "Okay. I'll wait.",
    },
    {
        "id": "take_turns", "title": "Can I Have a Turn?", "skill": "ask for and negotiate a turn", "prop": "ball",
        "requester": "mia", "responder": "leo", "request": "Can I have a turn?",
        "yes_label": "After me.", "yes": "Sure. You can go after me.", "yes_end": "Okay! I'll wait here.",
        "no_label": "More time.", "no": "I need a little more time.", "no_end": "Okay. Tell me when you're done.",
    },
    {
        "id": "share_materials", "title": "Can We Share the Crayons?", "skill": "share materials without grabbing", "prop": "crayons",
        "requester": "leo", "responder": "mia", "request": "Can we share the crayons?",
        "yes_label": "Let's share.", "yes": "Yes. Let's share them.", "yes_end": "Thank you! I'll use the blue one.",
        "no_label": "These are busy.", "no": "I'm using these colors right now.", "no_end": "Okay. I'll use the other colors.",
    },
    {
        "id": "accept_yes", "title": "Do You Want to Build?", "skill": "accept an invitation", "prop": "blocks",
        "requester": "leo", "responder": "mia", "request": "Do you want to build with me?",
        "yes_label": "Sure!", "yes": "Sure! Let's build.", "yes_end": "Great! We can make a bridge.",
        "no_label": "No, thank you.", "no": "No, thank you. I want to draw.", "no_end": "Okay. Maybe later.",
    },
    {
        "id": "polite_no", "title": "Do You Want to Play Tag?", "skill": "say no politely and choose quiet play", "prop": "tag",
        "requester": "mia", "responder": "leo", "request": "Do you want to play tag?",
        "yes_label": "Yes!", "yes": "Yes! Let's play.", "yes_end": "Okay! You can chase me.",
        "no_label": "No, thank you.", "no": "No, thank you. I want quiet play.", "no_end": "Okay. I'll play something quiet too.",
    },
    {
        "id": "accept_no", "title": "Can I Sit Here?", "skill": "accept another child's need for space", "prop": "bench",
        "requester": "leo", "responder": "mia", "request": "Can I sit here?",
        "yes_label": "Yes.", "yes": "Yes. You can sit here.", "yes_end": "Thanks!",
        "no_label": "I need space.", "no": "I need some space right now.", "no_end": "Okay. I'll sit over there.",
    },
    {
        "id": "still_using", "title": "I'm Still Using It", "skill": "state that an item is still in use", "prop": "train",
        "requester": "mia", "responder": "leo", "request": "Can I use the train?",
        "yes_label": "I'm done.", "yes": "Sure. I'm done with it.", "yes_end": "Thank you!",
        "no_label": "Still using it.", "no": "I'm still using it.", "no_end": "Okay. I'll wait.",
    },
    {
        "id": "wait_calmly", "title": "Is It My Turn?", "skill": "wait calmly for a turn", "prop": "swing",
        "requester": "leo", "responder": "mia", "request": "Is it my turn?",
        "yes_label": "Your turn.", "yes": "Yes. It's your turn now.", "yes_end": "Thank you!",
        "no_label": "Please wait.", "no": "Not yet. Please wait.", "no_end": "Okay. I can wait.",
    },
    {
        "id": "next_turn", "title": "Can I Go Next?", "skill": "ask to be next in line", "prop": "ball",
        "requester": "mia", "responder": "leo", "request": "Can I have the ball next?",
        "yes_label": "You're next.", "yes": "Yes. You're next.", "yes_end": "Okay! I'll be ready.",
        "no_label": "One more turn.", "no": "I promised one more turn first.", "no_end": "Okay. I'll go after that.",
    },
    {
        "id": "please_stop", "title": "Please Stop", "skill": "ask someone to stop an unwanted action", "prop": "tower",
        "requester": "mia", "responder": "leo", "request": "Please stop. I don't like that.",
        "yes_label": "I'll stop.", "yes": "Okay. I'll stop.", "yes_end": "Thank you for listening.",
        "no_label": "I'll move back.", "no": "I didn't know. I'll move back.", "no_end": "Thank you. That feels better.",
    },
    {
        "id": "personal_space", "title": "I Need Some Space", "skill": "express and respect personal space", "prop": "book",
        "requester": "mia", "responder": "leo", "request": "I need some space, please.",
        "yes_label": "I'll move back.", "yes": "Okay. I'll move back.", "yes_end": "Thank you. That's better.",
        "no_label": "Is this enough?", "no": "Is this far enough?",
        "no_end": "A little more, please.", "after_no": "Okay. How about now?",
    },
    {
        "id": "ask_for_help", "title": "Can You Help Me?", "skill": "ask for help and accept availability", "prop": "jar",
        "requester": "mia", "responder": "leo", "request": "Can you help me open this?",
        "yes_label": "Sure!", "yes": "Sure! I can help.", "yes_end": "Thank you!",
        "no_label": "Not right now.", "no": "I can't help right now.", "no_end": "Okay. I'll try again.",
    },
    {
        "id": "offer_help", "title": "Do You Want Some Help?", "skill": "offer help without taking over", "prop": "repair_blocks",
        "requester": "leo", "responder": "mia", "request": "Do you want some help?",
        "yes_label": "Yes, please.", "yes": "Yes, please. Let's pick them up.", "yes_end": "Okay! I'll help with these.",
        "no_label": "No, thanks.", "no": "No, thanks. I can do it.", "no_end": "Okay. I'll let you do it.",
    },
    {
        "id": "apologize", "title": "I'm Sorry", "skill": "apologize and repair harm", "prop": "repair_blocks",
        "requester": "mia", "responder": "leo", "request": "I'm sorry I knocked it down.",
        "yes_label": "Let's fix it.", "yes": "That's okay. Let's fix it.", "yes_end": "Yes. I'll help rebuild it.",
        "no_label": "I need a minute.", "no": "I'm upset. I need a minute.", "no_end": "Okay. I'll give you time.",
    },
    {
        "id": "invite_friend", "title": "Do You Want to Play?", "skill": "invite a child who is alone", "prop": "ball",
        "requester": "mia", "responder": "leo", "request": "Do you want to play with me?",
        "yes_label": "Yes!", "yes": "Yes! I'd like to play.", "yes_end": "Great! Let's roll the ball.",
        "no_label": "No, thank you.", "no": "No, thank you. I want to read.", "no_end": "Okay. Maybe later.",
    },
    {
        "id": "work_together", "title": "Let's Build Together", "skill": "cooperate when ideas are different", "prop": "blocks",
        "requester": "leo", "responder": "mia", "request": "What should we build together?",
        "yes_label": "A bridge.", "yes": "Let's build a bridge.", "yes_end": "Good idea! I'll make this side.",
        "no_label": "A tower.", "no": "Let's build a tower.", "no_end": "Good idea! I'll pass you the blocks.",
    },
]


def media(story_id: str, turn_id: str, kind: str) -> dict[str, str]:
    values = {
        "video": f"videos/social-dialogues/{story_id}/{turn_id}.mp4",
        "poster": f"images/social-dialogues/{story_id}/{turn_id}.jpg",
    }
    if kind == "line":
        values["audio"] = f"audio/dialogues/{story_id}/{turn_id}.mp3"
    return values


def build_story(spec: dict[str, Any]) -> dict[str, Any]:
    story_id = spec["id"]
    requester = spec["requester"]
    responder = spec["responder"]
    turns: list[dict[str, Any]] = [
        {
            "id": "setup", "kind": "scene", "visual": {"prop": spec["prop"], "action": "setup"},
            **media(story_id, "setup", "scene"), "next": "request",
        },
        {
            "id": "request", "kind": "line", "speaker": requester, "text": spec["request"],
            "visual": {"prop": spec["prop"], "action": "request", "focus": requester},
            **media(story_id, "request", "line"),
            "choice": {
                "prompt": f"What can {next(c['name'] for c in CHARACTERS if c['id'] == responder)} say?",
                "options": [
                    {"label": spec["yes_label"], "next": "accept"},
                    {"label": spec["no_label"], "next": "decline"},
                ],
            },
        },
        {
            "id": "accept", "kind": "line", "speaker": responder, "text": spec["yes"],
            "visual": {"prop": spec["prop"], "action": "accept", "focus": responder},
            **media(story_id, "accept", "line"), "next": "thanks",
        },
        {
            "id": "thanks", "kind": "line", "speaker": requester, "text": spec["yes_end"],
            "visual": {"prop": spec["prop"], "action": "positive_result", "focus": requester},
            **media(story_id, "thanks", "line"), "next": None,
        },
        {
            "id": "decline", "kind": "line", "speaker": responder, "text": spec["no"],
            "visual": {"prop": spec["prop"], "action": "boundary", "focus": responder},
            **media(story_id, "decline", "line"), "next": "wait",
        },
        {
            "id": "wait", "kind": "line", "speaker": requester, "text": spec["no_end"],
            "visual": {"prop": spec["prop"], "action": "respect", "focus": requester},
            **media(story_id, "wait", "line"), "next": "next_turn" if spec.get("after_no") else None,
        },
    ]
    if spec.get("after_no"):
        turns.append(
            {
                "id": "next_turn", "kind": "line", "speaker": responder, "text": spec["after_no"],
                "visual": {"prop": spec["prop"], "action": "repair", "focus": responder},
                **media(story_id, "next_turn", "line"), "next": None,
            }
        )
    return {
        "id": story_id,
        "title": spec["title"],
        "skill": spec["skill"],
        "age_range": "4-6",
        "start": "setup",
        "characters": CHARACTERS,
        "turns": turns,
    }


def build_document() -> dict[str, Any]:
    return {
        "version": "2.0",
        "mode": "social-dialogues",
        "language": "en",
        "stories": [build_story(spec) for spec in STORIES],
    }


def main() -> int:
    document = build_document()
    OUTPUT.write_text(json.dumps(document, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"wrote {len(document['stories'])} complete social dialogue stories")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
