#!/usr/bin/env python3
"""Generate branch-continuous MiniMax H3 media for Social stories 3-18.

Raw H3 audio is retained outside the repo for audit only. Published MP4s are
always silent 720x480 H.264 and continue to use approved child-role MP3s.
The raw directory makes the run resumable: existing turn MP4s are reused.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path

HOST = "http://127.0.0.1:8188"
COMFY = Path("/home/lpoeeo/comfy/ComfyUI")
INPUT = COMFY / "input"
WORKFLOW = Path("/home/lpoeeo/comfy/workflows/minimax_h3_t2v_api.json")
ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = Path("/mnt/data/projects/websites/kids-english-minimax-all-raw")
DATA_PATH = ROOT / "data" / "social_dialogues.json"
MANIFEST_PATH = ROOT / "data" / "social_media_manifest.json"

CHARACTERS = (
    "Preserve exactly two five-year-old children: Mia is a girl with a dark ponytail, pink long-sleeve shirt and blue jeans; "
    "Leo is a boy with short dark hair, blue-and-white striped shirt and blue jeans. "
)
COMMON = (
    "Polished high-quality 2D children's storybook animation in a warm colorful preschool environment, matching the established Kids English Social style. "
    + CHARACTERS
    + "Keep faces, hair, clothing, body proportions, room layout, props, and colors stable throughout this story. "
    "One continuous medium-wide fixed-camera shot with natural child motion and clear hands. "
    "Exactly two children; no extra people, extra limbs, generated text, subtitles, signs, logos, watermarks, cuts, or camera movement. "
    "Audio: quiet natural ambience only, no speech and no music. "
)

ACTIONS: dict[str, dict[str, str]] = {
    "borrow_toy": {
        "setup": "In a preschool toy area, Leo sits on the right and calmly rolls exactly one yellow toy dump truck beside his hands. Mia watches from the left with empty relaxed hands.",
        "request": "Leo still owns the one yellow truck. Mia stops at a respectful distance and raises one empty open palm to ask to borrow it; she never touches it.",
        "accept": "Leo smiles and deliberately hands the one yellow truck to Mia. Mia receives it only after the offer. End with Mia holding the truck and Leo empty-handed.",
        "thanks": "Mia keeps the one yellow truck, smiles and gently rolls it, while Leo watches with empty hands. No duplicate truck.",
        "decline": "Leo keeps the truck close and raises a calm not-yet palm. Mia stops with both hands empty; no transfer or grabbing.",
        "wait": "Leo continues using the one truck. Mia lowers her empty hand, steps well back, and sits in a separate waiting spot.",
    },
    "take_turns": {
        "setup": "In a preschool gym, Leo stands inside a marked play circle bouncing exactly one red ball while Mia waits outside the circle.",
        "request": "Leo keeps the ball. Mia stays outside the circle and asks for a turn with one empty open palm; she never reaches for the ball.",
        "accept": "Leo nods and points from himself to Mia to promise she goes after him, but he keeps the ball for his current turn. No immediate transfer.",
        "thanks": "Leo continues his current ball turn while Mia smiles and waits ready behind the marked line with empty hands.",
        "decline": "Leo keeps the ball, raises one finger for a little more time, and continues his turn. Mia remains outside with empty hands.",
        "wait": "Mia nods, steps to the waiting marker, and calmly watches while Leo keeps using the one ball.",
    },
    "share_materials": {
        "setup": "At a preschool art table, Mia draws on white paper using a stable set of exactly six thick crayons: red, green, yellow, blue, purple, and orange. Leo watches empty-handed.",
        "request": "Mia keeps all six crayons on her side. Leo asks to share with an empty open palm and never takes one before permission.",
        "accept": "Mia smiles and divides the same six crayons into two clear groups of three, sliding three toward Leo. End with Mia holding three and Leo holding three.",
        "thanks": "Leo clearly draws a blue mark with the blue crayon while his purple and orange crayons remain visible; Mia continues with red, green, and yellow. All six remain visible.",
        "decline": "Mia calmly indicates the red, green, and yellow crayons she is currently using. Leo stays empty-handed and does not take them.",
        "wait": "Mia keeps her three busy colors while Leo accepts and uses the other three colors—blue, purple, and orange—on separate paper. All six remain visible.",
    },
    "accept_yes": {
        "setup": "In a block area, Leo sits with a stable set of colorful loose wooden blocks and begins a small unfinished structure. Mia draws at a separate table on the left.",
        "request": "Leo gestures from Mia toward the loose blocks to invite her to build. Mia listens with empty hands and has not joined yet.",
        "accept": "Mia smiles, leaves the drawing table, joins only after accepting, and both children each move one block toward a shared structure. Show scattered blocks becoming a partial build.",
        "thanks": "Both children actively place blocks from opposite sides until a recognizable colorful bridge is formed. Each visibly contributes.",
        "decline": "Mia politely raises a no-thank-you palm and remains at her separate table drawing, while Leo keeps the blocks.",
        "wait": "Leo smiles and continues building alone; Mia continues drawing at the separate table. Keep the two activities spatially distinct.",
    },
    "polite_no": {
        "setup": "On a safe preschool playground, Mia and Leo stand several feet apart in an open running area, relaxed and not yet running.",
        "request": "Mia points to the open running area and makes an inviting open-hand gesture to ask Leo to play tag. Leo listens.",
        "accept": "Leo nods yes. Both begin running safely, with Mia clearly ahead and Leo clearly chasing from at least one body length behind.",
        "thanks": "Continue the clear tag chase: Mia runs in front while Leo follows behind, both smiling, with visible leg motion and separation.",
        "decline": "Leo raises a polite no-thank-you palm, then sits in a quiet corner with a picture book. Mia stops and respects the answer.",
        "wait": "Mia chooses a separate quiet floor puzzle while Leo reads his book. Both remain calm and do different quiet activities.",
    },
    "accept_no": {
        "setup": "In a preschool reading corner, Mia sits on the left side of one wooden bench reading a picture book. Leo stands nearby on the right.",
        "request": "Leo points to the empty right side of the bench and asks with an open palm. He remains standing and does not crowd Mia.",
        "accept": "Mia smiles, shifts slightly left and pats the empty right seat. Leo sits only after permission, leaving a comfortable gap.",
        "thanks": "Both children sit on the bench with a clear comfortable gap; Mia reads and Leo smiles with relaxed hands.",
        "decline": "Mia keeps her book and raises a calm need-space palm. Leo remains standing at a respectful distance and does not sit.",
        "wait": "Leo accepts, walks to a separate chair well away from Mia's bench, and sits there. Mia keeps her space and book.",
    },
    "still_using": {
        "setup": "In a preschool train area, Leo sits on the right operating exactly one blue wooden toy train on a short track. Mia watches from the left.",
        "request": "Leo keeps the one blue train. Mia asks with an empty open palm and never touches the train or track.",
        "accept": "Leo stops, lifts the one train and hands it to Mia. End with Mia holding the train and Leo empty-handed.",
        "thanks": "Mia keeps the one blue train and rolls it on the track while Leo watches with empty hands.",
        "decline": "Leo keeps operating the train and raises a calm still-using-it palm. Mia stays empty-handed.",
        "wait": "Mia lowers her hand, moves to a separate waiting cushion, and watches while Leo continues with the train.",
    },
    "wait_calmly": {
        "setup": "On a preschool playground, Mia is safely seated on exactly one swing and gently swinging. Leo waits beside a marked waiting spot, clear of the swing path.",
        "request": "Mia remains on the swing. Leo stays out of the swing path and asks if it is his turn with an empty open palm.",
        "accept": "Mia slows to a stop, steps off, and gestures to the empty swing. Leo takes the seat only after she exits.",
        "thanks": "Leo safely swings while Mia stands well aside at the waiting spot, smiling with empty hands.",
        "decline": "Mia remains safely seated and raises a calm please-wait palm while the swing slows. Leo stays back.",
        "wait": "Leo accepts and sits on a separate waiting bench outside the swing path while Mia continues her turn.",
    },
    "next_turn": {
        "setup": "In a preschool gym, Leo holds exactly one red ball inside a marked turn area. Mia waits behind a clear floor line.",
        "request": "Leo keeps the ball. Mia points from the ball to herself to ask to go next, keeping both hands away from it.",
        "accept": "Leo nods and points from himself toward Mia to promise she is next, but keeps the ball for the current turn. No transfer.",
        "thanks": "Mia smiles and stands ready behind the line with empty hands while Leo still holds the ball.",
        "decline": "Leo keeps the ball, raises one finger to indicate one more turn first, and points to a simple turn marker. Mia does not grab.",
        "wait": "Mia nods and moves behind the turn marker, waiting calmly with empty hands while Leo keeps the ball.",
    },
    "please_stop": {
        "setup": "In a block area, Mia carefully builds one colorful tower while Leo repeatedly reaches toward and wiggles a loose top block, visibly interfering. Mia looks uncomfortable.",
        "request": "Leo's hand remains near the tower. Mia raises a clear stop palm between Leo's hand and the tower; the unwanted reaching is obvious.",
        "accept": "Leo immediately withdraws both hands, stops touching the blocks, and steps one full body width back. The tower stays with Mia.",
        "thanks": "Mia relaxes and continues her tower undisturbed while Leo remains clearly back with hands to himself.",
        "decline": "Leo looks surprised, withdraws his hand, and moves back after realizing Mia disliked it. He does not touch the tower again.",
        "wait": "Mia visibly relaxes with comfortable space and continues building; Leo stays well away with relaxed hands.",
    },
    "personal_space": {
        "setup": "In a reading corner, Mia sits holding one picture book while Leo leans much too close beside her, faces only a short distance apart. Mia looks uncomfortable.",
        "request": "Mia keeps the book and raises an open space-request palm. Leo is still visibly too close but does not touch her or the book.",
        "accept": "Leo nods and steps back at least two full body widths. Mia keeps the book and relaxes.",
        "thanks": "Mia reads comfortably with the book while Leo remains far back in a separate spot.",
        "decline": "Leo moves back only partway, then pauses with an asking expression to check the distance. Mia keeps the book.",
        "wait": "Mia gestures gently for a little more distance while Leo remains at the partial distance; no one moves closer.",
        "next_turn": "Leo takes another clear step backward to a comfortable distance and opens his hands to check again. Mia relaxes with her book.",
    },
    "ask_for_help": {
        "setup": "At a preschool snack table, Mia grips one small closed jar with a tight lid and struggles to twist it. Leo stands nearby with empty hands.",
        "request": "Mia keeps the closed jar and gestures toward its lid to ask Leo for help. Leo listens; the jar remains closed.",
        "accept": "Both children clearly grip the same jar safely: Mia steadies the jar while Leo twists the lid. End with the lid visibly removed and the jar open.",
        "thanks": "Mia holds the open jar and smiles gratefully; the lid rests separately on the table and Leo's hands are empty.",
        "decline": "Leo raises a calm unavailable-now palm. Mia keeps the same jar fully closed; it must not open by itself.",
        "wait": "Mia accepts and independently tries twisting the still-closed lid again while Leo remains back. Show effort without magical opening.",
    },
    "offer_help": {
        "setup": "In a block area, colorful blocks from one fallen tower are scattered on the floor. Mia begins picking them up alone while Leo watches from a respectful distance.",
        "request": "Leo remains outside Mia's work area and offers help with an empty open palm; he does not pick up a block before permission.",
        "accept": "Mia nods yes. Both children then pick up separate blocks and place them together into one basket, visibly cooperating.",
        "thanks": "Both continue collecting the scattered blocks into the basket, each contributing with clear hand contact.",
        "decline": "Mia raises a polite no-thanks palm, then continues picking up blocks independently. Leo keeps empty hands and does not intervene.",
        "wait": "Leo accepts, steps back with relaxed empty hands, and watches while Mia makes visible independent cleanup progress.",
    },
    "apologize": {
        "setup": "In a block area, one tower has just fallen into scattered colorful blocks. Leo sits upset beside the pieces while Mia stands nearby looking concerned.",
        "request": "Mia faces Leo with hands clasped near her chest and a sincere apologetic expression. She does not touch the blocks yet.",
        "accept": "Leo's expression softens and he nods. Both children begin picking up separate blocks to repair the tower together.",
        "thanks": "Mia and Leo visibly rebuild the tower together from scattered to partial, each placing a block.",
        "decline": "Leo remains upset and raises a calm need-a-minute palm. Mia stops, keeps her hands empty, and does not start rebuilding.",
        "wait": "Mia accepts and steps far back to give Leo quiet time. Leo remains alone beside the scattered blocks; no repair begins yet.",
    },
    "invite_friend": {
        "setup": "In a preschool gym, Mia sits on the left with exactly one soft red ball. Leo sits on the right reading one picture book.",
        "request": "Mia keeps the ball and gestures invitingly toward Leo with one open hand. Leo keeps the book and listens.",
        "accept": "Leo closes and sets down the book, moves into the play area, and joins Mia only after saying yes. They begin rolling the one ball between them.",
        "thanks": "Mia and Leo sit several feet apart and clearly roll the one red ball back and forth together.",
        "decline": "Leo raises a polite no-thank-you palm and continues reading his book. Mia keeps the ball and respects the answer.",
        "wait": "Mia accepts and plays gently with the ball by herself on the left while Leo reads separately on the right.",
    },
    "work_together": {
        "setup": "In a block area, Mia and Leo sit on opposite sides of one stable pile of loose colorful blocks with no completed structure yet.",
        "request": "Leo gestures between the loose blocks and Mia with two open hands to ask what they should build together; neither starts yet.",
        "accept": "Mia indicates a bridge shape, then both begin placing blocks from opposite sides. Show loose blocks becoming a partial bridge.",
        "thanks": "Leo builds the right side while Mia builds the left side until one clear colorful bridge connects in the middle.",
        "decline": "On the alternative branch, Mia indicates a tall tower shape and begins stacking the first two blocks upright; no bridge appears.",
        "wait": "Leo agrees with the tower plan and passes one block into Mia's hands while she continues the same tower. End with a taller tower, not a bridge.",
    },
}


def shell(*args: str) -> None:
    subprocess.run(list(args), check=True)


def extract_last(video: Path, output: Path) -> None:
    probe = subprocess.run(
        [
            "ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
            "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", str(video),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    final_index = int(probe.stdout.strip()) - 1
    shell(
        "ffmpeg", "-y", "-loglevel", "error", "-i", str(video),
        "-vf", f"select='eq(n,{final_index})'", "-vsync", "0", "-frames:v", "1", str(output),
    )


def install_input(image: Path, story_id: str, turn_id: str) -> str:
    name = f"minimax_{story_id}_{turn_id}_first.png"
    shutil.copy2(image, INPUT / name)
    return name


def submit(story_id: str, turn_id: str, prompt: str, seed: int, steps: int, first: Path | None) -> tuple[Path, str, float]:
    raw_dir = RAW_ROOT / story_id
    raw_dir.mkdir(parents=True, exist_ok=True)
    output = raw_dir / f"{turn_id}.mp4"
    if output.exists() and output.stat().st_size > 50_000:
        return output, "reused", 0.0
    workflow = json.loads(WORKFLOW.read_text())
    workflow["5"]["inputs"].update({"prompt": COMMON + prompt, "width": 608, "height": 352, "length": 73})
    workflow["7"]["inputs"]["noise_seed"] = seed
    workflow["9"]["inputs"]["steps"] = steps
    workflow["14"]["inputs"]["filename_prefix"] = f"video/KidsEnglish_MiniMax_{story_id}_{turn_id}"
    if first is not None:
        workflow["15"] = {"class_type": "LoadImage", "inputs": {"image": install_input(first, story_id, turn_id)}}
        workflow["5"]["inputs"]["first_frame"] = ["15", 0]
    payload = json.dumps({"prompt": workflow, "client_id": "kids-english-minimax-all"}).encode()
    request = urllib.request.Request(HOST + "/prompt", data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        prompt_id = json.load(response)["prompt_id"]
    print(f"submitted {story_id}/{turn_id} {prompt_id}", flush=True)
    started = time.monotonic()
    while True:
        with urllib.request.urlopen(HOST + f"/history/{prompt_id}", timeout=30) as response:
            history = json.load(response)
        if prompt_id in history:
            record = history[prompt_id]
            if record.get("status", {}).get("status_str") == "error":
                raise RuntimeError(json.dumps(record["status"], indent=2))
            files = []
            for node in record.get("outputs", {}).values():
                files.extend(node.get("videos", []))
                files.extend(item for item in node.get("images", []) if item.get("filename", "").endswith(".mp4"))
            if files:
                info = files[0]
                source = COMFY / "output" / info.get("subfolder", "") / info["filename"]
                shutil.copy2(source, output)
                elapsed = time.monotonic() - started
                print(f"completed {story_id}/{turn_id} in {elapsed:.1f}s", flush=True)
                return output, prompt_id, elapsed
        if time.monotonic() - started > 1200:
            raise TimeoutError(f"{story_id}/{turn_id} exceeded 20 minutes")
        time.sleep(3)


def publish(story_id: str, turn_id: str, raw: Path) -> None:
    video = ROOT / "videos" / "social-dialogues" / story_id / f"{turn_id}.mp4"
    poster = ROOT / "images" / "social-dialogues" / story_id / f"{turn_id}.jpg"
    video.parent.mkdir(parents=True, exist_ok=True)
    poster.parent.mkdir(parents=True, exist_ok=True)
    shell("ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-an", "-vf", "scale=720:480:force_original_aspect_ratio=increase,crop=720:480", "-r", "24", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(video))
    shell("ffmpeg", "-y", "-loglevel", "error", "-ss", "1.5", "-i", str(video), "-frames:v", "1", "-q:v", "2", str(poster))


def update_manifest(story: dict, status: str) -> None:
    manifest = json.loads(MANIFEST_PATH.read_text())
    manifest["stories"][story["id"]] = {
        "renderer": "minimax-h3",
        "model_audio": "stripped",
        "dialogue_audio": "approved-child-tts",
        "source_size": [608, 352],
        "published_size": [720, 480],
        "frame_rate": 24,
        "duration_seconds": 3.04,
        "visual_review": status,
        "turns": [turn["id"] for turn in story["turns"]],
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=8)
    parser.add_argument("--start-story", type=int, default=3)
    args = parser.parse_args()
    INPUT.mkdir(parents=True, exist_ok=True)
    document = json.loads(DATA_PATH.read_text())
    attempts_path = RAW_ROOT / "attempts.jsonl"
    for story_index, story in enumerate(document["stories"], 1):
        if story_index < args.start_story:
            continue
        story_id = story["id"]
        prompts = ACTIONS[story_id]
        ends: dict[str, Path] = {}
        for turn_index, turn in enumerate(story["turns"]):
            turn_id = turn["id"]
            if turn_id == "setup":
                predecessor = None
            elif turn_id == "request":
                predecessor = "setup"
            elif turn_id == "accept":
                predecessor = "request"
            elif turn_id == "thanks":
                predecessor = "accept"
            elif turn_id == "decline":
                predecessor = "request"
            elif turn_id == "wait":
                predecessor = "decline"
            elif turn_id == "next_turn":
                predecessor = "wait"
            else:
                raise ValueError(turn_id)
            first = ends.get(predecessor) if predecessor else None
            seed = 1536197314400747551 + story_index * 100 + turn_index
            raw, prompt_id, elapsed = submit(story_id, turn_id, prompts[turn_id], seed, args.steps, first)
            publish(story_id, turn_id, raw)
            end = RAW_ROOT / story_id / f"{turn_id}_end.png"
            extract_last(raw, end)
            ends[turn_id] = end
            with attempts_path.open("a") as handle:
                handle.write(json.dumps({"story": story_id, "turn": turn_id, "prompt_id": prompt_id, "steps": args.steps, "elapsed": round(elapsed, 1), "status": "rendered"}) + "\n")
        update_manifest(story, "pending")
        print(f"story complete {story_index}/18 {story_id}", flush=True)


if __name__ == "__main__":
    main()
